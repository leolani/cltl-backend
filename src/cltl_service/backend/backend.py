import logging
import time
import uuid
from threading import Thread

from cltl.combot.infra.config import ConfigurationManager
from cltl.combot.infra.event import EventBus, Event
from cltl.combot.infra.resource import ResourceManager
from cltl.combot.infra.topic_worker import TopicWorker
from cltl.combot.infra.util import ThreadsafeBoolean

from cltl.backend.api.backend import Backend
from cltl.backend.api.storage import AudioStorage
from cltl_service.backend.schema import AudioSignalStarted, AudioSignalStopped

logger = logging.getLogger(__name__)


class BackendService:
    @classmethod
    def from_config(cls, backend: Backend, storage: AudioStorage, event_bus: EventBus,
                    resource_manager: ResourceManager, config_manager: ConfigurationManager):
        config = config_manager.get_config("cltl.backend.mic")
        mic_topic = config.get('topic')

        config = config_manager.get_config("cltl.backend.tts")
        tts_topic = config.get('topic')

        return cls(mic_topic, tts_topic, backend, storage, event_bus, resource_manager)

    def __init__(self, mic_topic: str, tts_topic: str, backend: Backend, storage: AudioStorage,
                 event_bus: EventBus, resource_manager: ResourceManager):
        self._mic_topic = mic_topic
        self._tts_topic = tts_topic
        self._backend = backend
        self._running = ThreadsafeBoolean()

        self._thread = None
        self._topic_worker = None

        self._storage = storage
        self._event_bus = event_bus
        self._resource_manager = event_bus

    @property
    def app(self):
        return None

    def start(self):
        self._backend.start()
        self.start_mic()
        self.start_tts()

    def stop(self):
        self.stop_tts()
        self.stop_mic()
        self._backend.stop()

    def start_tts(self):
        self._topic_worker = TopicWorker([self._tts_topic], self._event_bus,
                                         resource_manager=self._resource_manager, processor=self._process_tts)
        self._topic_worker.start().wait()

    def stop_tts(self):
        if not self._topic_worker:
            pass

        self._topic_worker.stop()
        self._topic_worker.await_stop()
        self._topic_worker = None

    def start_mic(self):
        if self._thread:
            raise ValueError("Already started")

        self._running.value = True

        def run():
            while self._running.value:
                try:
                    audio_id = str(uuid.uuid4())
                    with self._backend.microphone.listen() as (audio, params):
                        self._store(audio_id, self._audio_with_events(audio_id, audio, params),
                                    params.sampling_rate)
                        logger.info("Stored audio %s", audio_id)
                except Exception as e:
                    logger.warning("Failed to listen to mic: %s", e)
                    time.sleep(1)

        self._thread = Thread(name="cltl.backend", target=run)
        self._thread.start()

    def stop_mic(self):
        if not self._thread:
            return

        self._running.value = False
        self._thread.join()
        self._thread = None

    def _store(self, audio_id, audio, sampling_rate):
        self._storage.store(audio_id, audio, sampling_rate)

    def _audio_with_events(self, audio_id, audio, parameters):
        started = False
        samples = 0
        for frame in audio:
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
