import logging
import threading
import time
import unittest
from typing import Generator
from unittest.mock import MagicMock

import numpy as np
from cltl.combot.infra.resource.threaded import ThreadedResourceManager

from cltl.backend.impl.sync_microphone import SynchronizedMicrophone
from cltl.backend.impl.sync_tts import SynchronizedTextToSpeech, TextOutputTTS
from cltl.backend.spi.audio import AudioSource
from cltl.backend.spi.text import TextOutput

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)


logger = logging.getLogger(__name__)


def wait(lock: threading.Event):
    if not lock.wait(10):
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
        yield from(np.full((2,), i, dtype=np.int16) for i in range(10000))


class MicTTSIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.consume_start_event = threading.Event()
        self.consume_done_event = threading.Event()

        def consume(*args):
            self.consume_start_event.set()
            wait(self.consume_done_event)

        self.output_mock = MagicMock(spec=TextOutput)
        self.output_mock.consume = MagicMock(side_effect=consume)

        self.audio_running = threading.Event()
        self.muted = threading.Event()
        # source = TestSource(processing=self.audio_running, pause_processing=self.muted)
        source = TestSource(processing=None, pause_processing=None)

        self.resource_manager = ThreadedResourceManager()

        self.mic = SynchronizedMicrophone(source, self.resource_manager)
        self.mic.start()
        self.tts = SynchronizedTextToSpeech(TextOutputTTS(self.output_mock), self.resource_manager)
        self.tts.start()

        self.threads = []
        self.events = [self.consume_start_event, self.consume_done_event]

    def tearDown(self):
        self.mic.stop()
        self.tts.stop()
        for event in self.events:
            event.set()
        for thread in self.threads:
            thread.join()

    def test_synchronization(self):
        tts_thread_start_event = threading.Event()
        tts_start_event = threading.Event()
        tts_done_event = threading.Event()
        self.events.extend([tts_thread_start_event, tts_start_event, tts_done_event])

        def tts(*args):
            tts_thread_start_event.set()
            wait(tts_start_event)
            self.tts.say("Test output")
            tts_done_event.set()

        mic_thread_start_event = threading.Event()
        mic_start_event = threading.Event()
        mic_running_event = threading.Event()
        mic_mute_event = threading.Event()
        mic_stop_event = threading.Event()
        self.events.extend([mic_thread_start_event, mic_start_event, mic_mute_event, mic_stop_event])

        def mic(*args):
            mic_thread_start_event.set()
            wait(mic_start_event)

            while not mic_stop_event.is_set():
                with self.mic.listen() as (mic_audio, params):
                    next(mic_audio)
                    mic_running_event.set()

                    while not mic_stop_event.is_set():
                        time.sleep(0.001)
                        try:
                            next(mic_audio)
                        except StopIteration:
                            break

        mic_thread = threading.Thread(target=mic)
        tts_thread = threading.Thread(target=tts)
        mic_thread.start()
        tts_thread.start()
        self.threads.extend([mic_thread, tts_thread])

        wait(mic_thread_start_event)
        wait(tts_thread_start_event)

        mic_start_event.set()
        wait(mic_running_event)
        mic_running_event.clear()

        self.assertFalse(self.mic.muted)
        self.assertFalse(self.tts.is_talking)

        tts_start_event.set()

        wait(self.consume_start_event)

        self.assertTrue(self.mic.muted)
        self.assertTrue(self.tts.is_talking)

        self.consume_done_event.set()
        wait(mic_running_event)

        self.assertFalse(self.mic.muted)
        self.assertFalse(self.tts.is_talking)