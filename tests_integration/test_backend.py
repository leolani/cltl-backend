import shutil
import tempfile
import threading
import time
import unittest
from threading import Event
from typing import Iterator

import numpy as np
from cltl.combot.infra.event.api import Event as CombotEvent
from cltl.combot.infra.event.memory import SynchronousEventBus
from cltl.combot.infra.util import ThreadsafeBoolean

from cltl.backend.impl.cached_storage import CachedAudioStorage
from cltl.backend.impl.sync_microphone import SimpleMicrophone
from cltl.backend.spi.audio import AudioSource
from cltl_service.backend.backend import AudioBackendService
from cltl_service.backend.schema import AudioSignalStarted, AudioSignalStopped

DEBUG = 0

def wait(lock: threading.Event):
    if not lock.wait(1):
        raise unittest.TestCase.failureException("Latch timed out")


class TestAudioSource(AudioSource):
    def __init__(self, audio):
        self._audio = audio

    def audio(self) -> Iterator[np.array]:
        return self._audio

    @property
    def rate(self):
        return 16000

    @property
    def channels(self):
        return 1

    @property
    def frame_size(self):
        return 480

    @property
    def depth(self):
        return 2


class BackendTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_backend_events(self):
        audio = [np.random.randint(-1000, 1000, (480, 2), dtype=np.int16) for i in range(10)]

        latch = Event()
        latch2 = Event()
        audio_waiting = Event()
        audio_started = Event()
        audio_finished = Event()
        start_event = ThreadsafeBoolean()
        stop_event = ThreadsafeBoolean()

        def audio_generator():
            audio_waiting.set()
            wait(latch)
            yield audio[0]
            audio_started.set()
            wait(latch2)
            yield from audio[1:]
            audio_finished.set()
            yield None

        audio_source = TestAudioSource(audio_generator())

        audio_storage = CachedAudioStorage(self.tmp_dir)
        event_bus = SynchronousEventBus()
        backend_service = AudioBackendService('mic_topic', SimpleMicrophone(audio_source), audio_storage, event_bus)

        audio_storage.store("1", audio, sampling_rate=16000)
        backend_service.start()

        def handle_event(event: CombotEvent):
            if event.payload.type == AudioSignalStarted.__name__:
                start_event.value = True
            if event.payload.type == AudioSignalStopped.__name__:
                stop_event.value = True

        event_bus.subscribe("mic_topic", handle_event)

        wait(audio_waiting)
        self.assertFalse(start_event.value)
        latch.set()
        wait(audio_started)
        self.assertTrue(start_event.value)
        self.assertFalse(stop_event.value)

        latch2.set()
        wait(audio_finished)
        time.sleep(0.01)
        self.assertTrue(stop_event.value)
        backend_service.stop()

