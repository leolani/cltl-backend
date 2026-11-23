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


class RefusingWriteLock:
    """Write lock that refuses the first `refusals` acquire calls, like the lock does while the mic flags writers as interrupted."""
    def __init__(self, refusals):
        self.refusals = refusals
        self.held = False
        self.events = []

    def acquire(self, blocking=True, timeout=-1):
        if self.refusals > 0:
            self.refusals -= 1
            return False
        self.held = True
        self.events.append("acquire")
        return True

    def release(self):
        if not self.held:
            raise RuntimeError("release unlocked lock")
        self.held = False
        self.events.append("release")

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class WriteLockRefusedTest(unittest.TestCase):
    """
    Regression: WriteLock.acquire() returns False immediately while the mic has flagged the
    writers as interrupted, which happens after each failed attempt to unmute while the previous
    utterance was playing. `with lock:` ignored that result, so an utterance following another
    immediately was spoken without muting the microphone (and failed on release).
    """
    def test_speaks_only_while_holding_lock(self):
        lock = RefusingWriteLock(refusals=3)
        resource_manager = MagicMock()
        resource_manager.get_write_lock.return_value = lock

        held_while_speaking = []
        output = MagicMock(spec=TextOutput)
        output.consume = MagicMock(side_effect=lambda *args: held_while_speaking.append(lock.held))

        SynchronizedTextToSpeech(TextOutputTTS(output), resource_manager).say("Test output")

        self.assertEqual([True], held_while_speaking)
        self.assertEqual(["acquire", "release"], lock.events)


class RealtimeSource(AudioSource):
    """16kHz source delivering a 30ms frame every 30ms, like the host's microphone."""
    rate = 16000
    channels = 1
    frame_size = 480
    depth = 2

    @property
    def audio(self) -> Generator[np.array, None, None]:
        while True:
            time.sleep(0.03)
            yield np.zeros((480,), dtype=np.int16)


class BackToBackUtterancesTest(unittest.TestCase):
    """Utterances that follow each other without a pause must all be spoken with a muted microphone."""
    def test_microphone_stays_muted_while_speaking(self):
        resource_manager = ThreadedResourceManager()
        mic = SynchronizedMicrophone(RealtimeSource(), resource_manager)
        mic.start()

        spoken = []

        class Output(TextOutput):
            def consume(self, text, language=None):
                open_at_start = not mic.muted
                time.sleep(0.5)
                spoken.append((text, open_at_start, not mic.muted))

        tts = SynchronizedTextToSpeech(TextOutputTTS(Output()), resource_manager)
        tts.start()

        stop = threading.Event()

        def listen():
            while not stop.is_set():
                with mic.listen() as (audio, _):
                    for frame in audio:
                        if frame is None or stop.is_set():
                            break

        thread = threading.Thread(target=listen, daemon=True)
        thread.start()
        try:
            time.sleep(0.5)
            for i in range(6):
                tts.say(f"Utterance {i}")
        finally:
            stop.set()
            thread.join(10)
            mic.stop()
            tts.stop()

        self.assertFalse(thread.is_alive(), "Deadlock in microphone")
        self.assertEqual(6, len(spoken))
        self.assertEqual([], [text for text, start, end in spoken if start or end])
