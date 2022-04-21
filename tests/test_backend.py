import shutil
import tempfile
import threading
import time
import unittest
from threading import Event
from typing import Iterator, Any

import numpy as np
from cltl.combot.event.emissor import AudioSignalStarted, AudioSignalStopped
from cltl.combot.infra.event.api import Event as CombotEvent
from cltl.combot.infra.event.memory import SynchronousEventBus
from cltl.combot.infra.resource.threaded import ThreadedResourceManager

from cltl.backend.api.backend import Backend
from cltl.backend.impl.cached_storage import CachedAudioStorage, CachedImageStorage
from cltl.backend.impl.sync_microphone import SimpleMicrophone
from cltl.backend.spi.audio import AudioSource
from cltl_service.backend.backend import BackendService

DEBUG = 0

def wait(lock: threading.Event):
    if not lock.wait(1):
        raise unittest.TestCase.failureException("Latch timed out")


class ThreadsafeValue:
    def __init__(self, value: Any = None):
        self._value = value
        self._lock = threading.Lock()

    @property
    def value(self):
        with self._lock:
            return self._value

    @value.setter
    def value(self, value):
        with self._lock:
            self._value = value


class TestAudioSource(AudioSource):
    def __init__(self, audio):
        self._audio = audio

    @property
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
        self.backend_service = None
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if self.backend_service:
            self.backend_service.stop()
        shutil.rmtree(self.tmp_dir)

    def test_backend_events(self):
        audio = [np.random.randint(-1000, 1000, (480, 2), dtype=np.int16) for i in range(10)]

        latch = Event()
        latch2 = Event()
        audio_waiting = Event()
        audio_started = Event()
        audio_finished = Event()
        start_event = ThreadsafeValue(0)
        stop_event = ThreadsafeValue(0)

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

        backend = Backend(SimpleMicrophone(audio_source), None, None)
        audio_storage = CachedAudioStorage(self.tmp_dir)
        image_storage = CachedImageStorage(self.tmp_dir)
        event_bus = SynchronousEventBus()
        resource_manager = ThreadedResourceManager()
        self.backend_service = BackendService('mic_topic', 'image_topic', 'tts_topic', '', -1,
                                              backend, audio_storage, image_storage, event_bus, resource_manager)

        audio_storage.store("1", audio, sampling_rate=16000)
        self.backend_service.start()

        def handle_event(event: CombotEvent):
            if event.payload.type == AudioSignalStarted.__name__:
                start_event.value += 1
            if event.payload.type == AudioSignalStopped.__name__:
                stop_event.value += 1

        event_bus.subscribe("mic_topic", handle_event)

        wait(audio_waiting)
        self.assertEqual(0, start_event.value)
        self.assertEqual(0, stop_event.value)
        latch.set()
        wait(audio_started)
        self.assertEqual(1, start_event.value)
        self.assertEqual(0, stop_event.value)

        latch2.set()
        wait(audio_finished)
        time.sleep(0.01)
        self.assertEqual(1, stop_event.value)
        self.assertEqual(1, start_event.value)
