import logging
import time
import uuid
from threading import Thread, Lock

from cltl.combot.event.emissor import AudioSignalStopped, ImageSignalEvent
from cltl.combot.infra.config import ConfigurationManager
from cltl.combot.infra.event import EventBus, Event
from cltl.combot.infra.resource import ResourceManager
from cltl.combot.infra.time_util import timestamp_now
from cltl.combot.infra.topic_worker import TopicWorker
from cltl.combot.infra.util import ThreadsafeBoolean
from emissor.representation.scenario import AudioSignal, ImageSignal

from cltl.backend.api.backend import Backend
from cltl.backend.api.camera import Image
from cltl.backend.api.microphone import AudioParameters
from cltl.backend.api.storage import AudioStorage, ImageStorage
from cltl_service.backend.schema import BackendAudioSignalStarted

logger = logging.getLogger(__name__)


class BackendService:
    @classmethod
    def from_config(cls, backend: Backend, audio_storage: AudioStorage, image_storage: ImageStorage,
                    event_bus: EventBus, resource_manager: ResourceManager, config_manager: ConfigurationManager):
        config = config_manager.get_config("cltl.backend")
        scenario_topic = config.get("scenario_topic")

        config = config_manager.get_config("cltl.backend.mic")
        mic_topic = config.get('topic')

        config = config_manager.get_config("cltl.backend.image")
        image_topic = config.get('topic')
        image_rate = config.get_float('rate')

        config = config_manager.get_config("cltl.backend.tts")
        tts_topic = config.get('topic')

        return cls(mic_topic, image_topic, tts_topic, scenario_topic, image_rate,
                   backend, audio_storage, image_storage, event_bus, resource_manager)

    def __init__(self, mic_topic: str, image_topic: str, tts_topic: str, scenario_topic: str,
                 image_rate: float,
                 backend: Backend, audio_storage: AudioStorage, image_storage: ImageStorage,
                 event_bus: EventBus, resource_manager: ResourceManager):
        self._mic_topic = mic_topic
        self._image_topic = image_topic
        self._tts_topic = tts_topic
        self._scenario_topic = scenario_topic

        self._image_rate = image_rate

        self._backend = backend
        self._running = ThreadsafeBoolean()

        self._scenario_lock = Lock()
        self._scenario_id = None
        self._require_scenario = bool(self._scenario_topic)

        self._mic_thread = None
        self._image_thread = None
        self._tts_worker = None
        self._scenario_worker = None

        self._audio_storage = audio_storage
        self._image_storage = image_storage
        self._event_bus = event_bus
        self._resource_manager = resource_manager

    @property
    def app(self):
        return None

    def start(self):
        self._scenario_id = None if self._require_scenario else str(uuid.uuid4())

        self._running.value = True

        self._backend.start()
        self._start_scenario()
        self._start_mic()
        self._start_image()
        self._start_tts()

    def stop(self):
        self._scenario_id = None

        self._running.value = False

        self._stop_tts()
        self._stop_image()
        self._stop_mic()
        self._stop_scenario()
        self._backend.stop()

    def _start_scenario(self):
        if not self._require_scenario:
            return

        self._scenario_worker = TopicWorker([self._scenario_topic],
                                            event_bus=self._event_bus,
                                            resource_manager=self._resource_manager,
                                            processor=self._process_scenario,
                                            name=self.__class__.__name__ + "_scenario")
        self._scenario_worker.start().wait()

    def _stop_scenario(self):
        if not self._scenario_worker:
            return

        self._scenario_worker.stop()
        self._scenario_worker.await_stop()
        self._scenario_worker = None

    def _start_tts(self):
        self._tts_worker = TopicWorker([self._tts_topic],
                                       event_bus=self._event_bus,
                                       resource_manager=self._resource_manager,
                                       processor=self._process_tts,
                                       name=self.__class__.__name__ + "_tts")
        self._tts_worker.start().wait()

    def _stop_tts(self):
        if not self._tts_worker:
            return

        self._tts_worker.stop()
        self._tts_worker.await_stop()
        self._tts_worker = None

    def _start_image(self):
        if self._image_thread:
            raise ValueError("Image already started")

        if self._image_rate <= 0:
            return

        def run():
            while self._running:
                if not self.scenario_id:
                    logger.info("No active scenario, waiting to start recording images")
                    time.sleep(1)
                    continue
                try:
                    self._record_images()
                except IOError as e:
                    # ConnectionErrors may occur during start-up
                    logging.warning("Failed to capture to image: %s", e)
                    time.sleep(1)
                except Exception as e:
                    logger.exception("Failed to capture to image: %s", e)
                    time.sleep(1)

        self._image_thread = Thread(name="cltl.backend.image", target=run)
        self._image_thread.start()

    def _stop_image(self):
        if not self._image_thread:
            return

        self._image_thread.join()
        self._image_thread = None

    def _start_mic(self):
        if self._mic_thread:
            raise ValueError("Mic already started")

        def run():
            while self._running:
                if not self.scenario_id:
                    logger.info("No active scenario, waiting to start listening")
                    time.sleep(1)
                    continue
                try:
                    audio_id = str(uuid.uuid4())
                    with self._backend.microphone.listen() as (audio, params):
                        self._audio_storage.store(audio_id,
                                                  self._audio_with_events(audio_id, audio, params),
                                                  params.sampling_rate)
                        logger.info("Stored audio %s", audio_id)
                except IOError as e:
                    # ConnectionErrors may occur during start-up
                    logging.warning("Failed to listen to mic: %s", e)
                    time.sleep(1)
                except Exception as e:
                    logger.exception("Failed to listen to mic: %s", e)
                    time.sleep(1)

        self._mic_thread = Thread(name="cltl.backend.mic", target=run)
        self._mic_thread.start()

    def _stop_mic(self):
        if not self._mic_thread:
            return

        self._mic_thread.join()
        self._mic_thread = None

    @property
    def scenario_id(self):
        with self._scenario_lock:
            return self._scenario_id

    @scenario_id.setter
    def scenario_id(self, scenario_id: str):
        with self._scenario_lock:
            self._scenario_id = scenario_id

    def _record_images(self):
        with self._backend.camera as camera:
            for image in camera.record():
                if not self._running:
                    logger.debug("Stopped recording")
                    return

                image_id = str(uuid.uuid4())
                self._image_storage.store(image_id, image)
                self._publish_image_event(image_id, image)
                logger.info("Stored image %s", image_id)

    def _publish_image_event(self, image_id: str, image: Image):
        image_signal = self._create_image_signal(image_id, image)
        event = ImageSignalEvent.create(image_signal)
        self._event_bus.publish(self._image_topic, Event.for_payload(event))

    def _audio_with_events(self, audio_id, audio, parameters):
        started = False
        samples = 0
        start_time = None
        for frame in audio:
            if not self._running:
                break
            if frame is None:
                continue
            if not started:
                start_time = timestamp_now()
                signal = self._create_audio_signal(audio_id, parameters, start=start_time)
                started = BackendAudioSignalStarted.create_backend_signal(signal, parameters)
                event = Event.for_payload(started)
                self._event_bus.publish(self._mic_topic, event)

            samples += len(frame)
            yield frame

        if started:
            signal = self._create_audio_signal(audio_id, parameters, length=samples,
                                               start=start_time, stop=timestamp_now())
            stopped = AudioSignalStopped.create(signal)
            event = Event.for_payload(stopped)
            self._event_bus.publish(self._mic_topic, event)

    def _process_scenario(self, event: Event):
        logger.debug("Process Scenario event %s", event.payload)
        self.scenario_id = event.payload.scenario.id

    def _process_tts(self, event: Event):
        logger.debug("Process TTS event %s", event.payload)
        self._backend.text_to_speech.say(event.payload.signal.text)

    def _create_audio_signal(self, audio_id: str, parameters: AudioParameters,
                             start: int = None, stop: int = None, length: int = None):
        return AudioSignal.for_scenario(self.scenario_id, start, stop,
                                        f"cltl-storage:audio/{audio_id}",
                                        length, parameters.channels, signal_id=audio_id)

    def _create_image_signal(self, image_id, image):
        return ImageSignal.for_scenario(self.scenario_id, timestamp_now(), timestamp_now(),
                                        f"cltl-storage:image/{image_id}",
                                        image.bounds.to_diagonal(), signal_id=image_id)
