import logging
import numpy as np
import sys
import threading
import unittest
from typing import Generator

from cltl.backend.api.microphone import MIC_RESOURCE_NAME, AudioParameters
from cltl.backend.impl.sync_microphone import SynchronizedMicrophone
from cltl.backend.spi.audio import AudioSource
from cltl.combot.infra.resource.threaded import ThreadedResourceManager

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(stream=sys.stdout))
logger.setLevel(logging.DEBUG)


def wait(lock: threading.Event):
    if not lock.wait(1):
        raise unittest.TestCase.failureException("Latch timed out")


class TestSource(AudioSource):
    def __init__(self, processing: threading.Event = None,
                 pause_processing: threading.Event = None,
                 finished: threading.Event = None):
        self.processing = processing
        self.pause_processing = pause_processing
        self.finished = finished

    @property
    def rate(self):
        return 200

    @property
    def channels(self):
        return 1

    @property
    def frame_size(self):
        return 2

    @property
    def depth(self):
        return 2

    @property
    def audio(self) -> Generator[np.array, None, None]:
        for i in range(10):
            if (not self.processing or self.processing.isSet()) and self.pause_processing:
                wait(self.pause_processing)
            if self.processing and i == 4:
                self.processing.set()
            yield np.full((2,), i, dtype=np.int16)

        if self.finished:
            self.finished.set()

        yield None


class SynchronizedMicrophoneTest(unittest.TestCase):
    def setUp(self):
        source = TestSource()
        self.resource_manager = ThreadedResourceManager()
        self.mic = SynchronizedMicrophone(source, self.resource_manager)
        self.mic.start()

    def tearDown(self):
        self.mic.stop()

    def test_listen(self):
        self.assertTrue(self.mic.muted)

        with self.mic.listen() as (mic_audio, params):
            self.assertFalse(self.mic.muted)
            audio = [frame for frame in mic_audio]
            parameters = params

        self.assertEqual(11, len(audio))
        self.assertIsNone(audio[10])
        self.assertTrue(all(frame.shape == (2,) for frame in audio[:-1]))
        self.assertEqual([i for i in range(10)], [frame[0] for frame in audio[:-1]])

        self.assertEqual(AudioParameters(200, 1, 2, 2), parameters)

        self.assertTrue(self.mic.muted)

    def test_mute(self):
        audio_running = threading.Event()
        muted = threading.Event()

        source = TestSource(processing=audio_running, pause_processing=muted)
        self.resource_manager = ThreadedResourceManager()
        self.mic = SynchronizedMicrophone(source, self.resource_manager)

        def mute_mic():
            wait(audio_running)

            self.mic.mute()

            muted.set()

        mute_thread = threading.Thread(name="mute", target=mute_mic)

        self.mic.start()
        mute_thread.start()

        self.assertTrue(self.mic.muted)

        with self.mic.listen() as (mic_audio, params):
            self.assertFalse(self.mic.muted)
            audio = [frame for frame in mic_audio]

        self.assertEqual(7, len(audio))
        self.assertIsNone(audio[6])
        self.assertTrue(all(frame.shape == (2,) for frame in audio[:-1]))
        self.assertEqual([i for i in range(6)], [frame[0] for frame in audio[:-1]])

        self.assertTrue(self.mic.muted)

    def test_mute_with_readers(self):
        """
        Test that mic is only muted when readers are finished.

        * Start audio
        * Wait until audio is processing
        * Start reader and acquire reader lock
        * Delay audio until mute
        * Call mute
        * Test that not muted
        * Wait until audio is finished
        * Test that not muted
        * Release reader lock and stop reader
        * Await muted
        * Test mic is muted
        """
        audio_running = threading.Event()
        audio_finished = threading.Event()
        reader_started = threading.Event()
        reader_finish = threading.Event()
        mute = threading.Event()
        muted = threading.Event()

        def mute_mic():
            wait(reader_started)
            wait(mute)
            mic.mute()
            muted.set()
        mute_thread = threading.Thread(name="mute", target=mute_mic)

        def reader():
            wait(audio_running)
            with resource_manager.get_read_lock(MIC_RESOURCE_NAME):
                reader_started.set()
                wait(reader_finish)
        reader_thread = threading.Thread(name="reader", target=reader)

        source = TestSource(processing=audio_running, pause_processing=mute, finished=audio_finished)
        resource_manager = ThreadedResourceManager()
        mic = SynchronizedMicrophone(source, resource_manager)

        def run_mic():
            mic.start()
            with mic.listen() as (mic_audio, params):
                [frame for frame in mic_audio]
        mic_thread = threading.Thread(name="mic", target=run_mic)

        mic_thread.start()
        reader_thread.start()
        mute_thread.start()

        wait(reader_started)

        self.assertFalse(mic.muted)
        self.assertUnset(audio_finished)

        mute.set()

        self.assertFalse(mic.muted)
        self.assertSet(audio_finished)
        self.assertUnset(muted)
        self.assertFalse(mic.muted)

        reader_finish.set()

        self.assertSet(muted)
        self.assertTrue(mic.muted)

    def assertUnset(self, lock):
        self.assertFalse(lock.wait(0.1))

    def assertSet(self, lock):
        self.assertTrue(lock.wait(0.1))






