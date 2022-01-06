import logging
import time
import uuid
from threading import Thread

from cltl.combot.infra.config import ConfigurationManager
from cltl.combot.infra.event import EventBus, Event
from cltl.combot.infra.resource import ResourceManager
from cltl.combot.infra.topic_worker import TopicWorker
from cltl.combot.infra.util import ThreadsafeBoolean
from emissor.representation.container import MultiIndex
from emissor.representation.scenario import ImageSignal, Modality

from cltl.backend.api.backend import Backend
from cltl.backend.api.camera import Image
from cltl.backend.api.storage import AudioStorage, ImageStorage
from cltl_service.backend.schema import AudioSignalStarted, AudioSignalStopped

logger = logging.getLogger(__name__)


class BackendService:
    @classmethod
    def from_config(cls, backend: Backend, audio_storage: AudioStorage, image_storage: ImageStorage,
                    event_bus: EventBus, resource_manager: ResourceManager, config_manager: ConfigurationManager):
        config = config_manager.get_config("cltl.backend.mic")
        mic_topic = config.get('topic')

        config = config_manager.get_config("cltl.backend.image")
        image_topic = config.get('topic')
        image_rate = config.get_float('rate')

        config = config_manager.get_config("cltl.backend.tts")
        tts_topic = config.get('topic')

        return cls(mic_topic, image_topic, tts_topic, image_rate, backend, audio_storage, image_storage,
                   event_bus, resource_manager)

    def __init__(self, mic_topic: str, image_topic: str, tts_topic: str, image_rate: float,
                 backend: Backend, audio_storage: AudioStorage, image_storage: ImageStorage,
                 event_bus: EventBus, resource_manager: ResourceManager):
        self._mic_topic = mic_topic
        self._image_topic = image_topic
        self._tts_topic = tts_topic
        self._image_rate = image_rate

        self._backend = backend
        self._running = ThreadsafeBoolean()

        self._mic_thread = None
        self._image_thread = None
        self._topic_worker = None

        self._audio_storage = audio_storage
        self._image_storage = image_storage
        self._event_bus = event_bus
        self._resource_manager = resource_manager

    @property
    def app(self):
        return None

    def start(self):
        self._running.value = True

        self._backend.start()
        self._start_mic()
        self._start_image()
        self._start_tts()

    def stop(self):
        self._running.value = False

        self._stop_tts()
        self._stop_image()
        self._stop_mic()
        self._backend.stop()

    def _start_tts(self):
        self._topic_worker = TopicWorker([self._tts_topic],
                                         event_bus=self._event_bus,
                                         resource_manager=self._resource_manager,
                                         processor=self._process_tts)
        self._topic_worker.start().wait()

    def _stop_tts(self):
        if not self._topic_worker:
            pass

        self._topic_worker.stop()
        self._topic_worker.await_stop()
        self._topic_worker = None

    def _start_image(self):
        if self._image_thread:
            raise ValueError("Image already started")

        if self._image_rate <= 0:
            return

        def run():
            while self._running:
                try:
                    self._record_images()
                except Exception as e:
                    logger.warning("Failed to capture to image: %s", e)
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
                try:
                    audio_id = str(uuid.uuid4())
                    with self._backend.microphone.listen() as (audio, params):
                        self._audio_storage.store(audio_id,
                                                  self._audio_with_events(audio_id, audio, params),
                                                  params.sampling_rate)
                        logger.info("Stored audio %s", audio_id)
                except Exception as e:
                    logger.warning("Failed to listen to mic: %s", e)
                    time.sleep(1)

        self._mic_thread = Thread(name="cltl.backend.mic", target=run)
        self._mic_thread.start()

    def _stop_mic(self):
        if not self._mic_thread:
            return

        self._mic_thread.join()
        self._mic_thread = None

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
        image_signal = ImageSignal(image_id, MultiIndex(image_id, image.bounds.to_tuple()),
                                   None, Modality.IMAGE, None, [f"cltl-storage:image/{image_id}"], [])
        event = Event.for_payload(image_signal)
        self._event_bus.publish(self._image_topic, event)

    def _audio_with_events(self, audio_id, audio, parameters):
        started = False
        samples = 0
        for frame in audio:
            if not self._running:
                break
            if frame is None:
                continue
            if not started:
                files = [f"cltl-storage:audio/{audio_id}"]
                started = AudioSignalStarted.create(audio_id, time.time(), files, parameters)
                event = Event.for_payload(started)
                self._event_bus.publish(self._mic_topic, event)

            samples += len(frame)
            yield frame

        if started:
            stopped = AudioSignalStopped.create(audio_id, time.time(), samples)
            event = Event.for_payload(stopped)
            self._event_bus.publish(self._mic_topic, event)

    def _process_tts(self, event: Event):
        logger.info("Process TTS event %s", event.payload)
        self._backend.text_to_speech.say(event.payload.text)
