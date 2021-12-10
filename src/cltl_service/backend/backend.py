import logging
import time
import uuid
from threading import Thread

from cltl.combot.infra.config import ConfigurationManager
from cltl.combot.infra.event import EventBus, Event
from cltl.combot.infra.util import ThreadsafeBoolean

from cltl.backend.api.microphone import Microphone
from cltl.backend.api.storage import AudioStorage
from cltl_service.backend.schema import AudioSignalStarted, AudioSignalStopped

logger = logging.getLogger(__name__)


class AudioBackendService:
    @classmethod
    def from_config(cls, mic: Microphone, storage: AudioStorage, event_bus: EventBus,
                    config_manager: ConfigurationManager):
        config = config_manager.get_config("cltl.backend.mic")

        return cls(config.get('topic'), mic, storage, event_bus)

    def __init__(self, mic_topic: str, mic: Microphone, storage: AudioStorage, event_bus: EventBus):
        self._mic_topic = mic_topic
        self._mic = mic
        self._running = ThreadsafeBoolean()
        self._thread = None
        self._storage = storage
        self._event_bus = event_bus

    @property
    def app(self):
        return None

    def start(self):
        if self._thread:
            raise ValueError("Already started")

        self._mic.start()
        self._running.value = True

        def run():
            while self._running.value:
                try:
                    audio_id = str(uuid.uuid4())
                    with self._mic.listen() as (audio, params):
                        self._store(audio_id, self._audio_with_events(audio_id, audio, params),
                                    params.sampling_rate)
                        logger.info("Stored audio %s", audio_id)
                    self._mic.mute()
                except Exception as e:
                    logger.warning("Failed to listen to mic: %s", e)
                    time.sleep(1)

        self._thread = Thread(name="cltl.backend", target=run)
        self._thread.start()

    def stop(self):
        if not self._thread:
            return

        self._running.value = False
        self._mic.stop()
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
