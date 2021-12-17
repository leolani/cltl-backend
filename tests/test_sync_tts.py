import logging
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock

from cltl.combot.infra.resource.threaded import ThreadedResourceManager
from cltl.combot.test.util import await_predicate

from cltl.backend.api.microphone import AUDIO_RESOURCE_NAME
from cltl.backend.impl.sync_tts import SynchronizedTextToSpeech, TextOutputTTS
from cltl.backend.spi.text import TextOutput

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(stream=sys.stdout))
logger.setLevel(logging.DEBUG)


def wait(lock: threading.Event):
    if not lock.wait(0.5):
        raise unittest.TestCase.failureException("Latch timed out")


class SynchronizedTTSTest(unittest.TestCase):
    def setUp(self):
        self.consume_start_event = threading.Event()
        self.consume_done_event = threading.Event()

        def consume(*args):
            self.consume_start_event.set()
            wait(self.consume_done_event)

        self.output_mock = MagicMock(spec=TextOutput)
        self.output_mock.consume = MagicMock(side_effect=consume)

        self.resource_manager = ThreadedResourceManager()
        self.resource_manager.provide_resource(AUDIO_RESOURCE_NAME)

        self.tts = SynchronizedTextToSpeech(TextOutputTTS(self.output_mock), self.resource_manager)
        self.tts.start()

        self.thread = None
        self.events = [self.consume_start_event, self.consume_done_event]

    def tearDown(self):
        self.tts.stop()
        for event in self.events:
            event.set()
        if self.thread:
            self.thread.join()

    def test_say(self):
        thread_start_event = threading.Event()
        tts_start_event = threading.Event()
        tts_done_event = threading.Event()
        self.events.extend([thread_start_event, tts_start_event, tts_done_event])

        def tts(*args):
            thread_start_event.set()
            wait(tts_start_event)
            self.tts.say("Test output")
            tts_done_event.set()

        self.thread = threading.Thread(target=tts)
        self.thread.start()
        wait(thread_start_event)

        self.assertFalse(self.tts.is_talking)
        tts_start_event.set()

        wait(self.consume_start_event)
        self.assertTrue(self.tts.is_talking)
        self.consume_done_event.set()

        wait(tts_done_event)

        self.output_mock.consume.assert_called_once_with("Test output", None)
        self.assertFalse(self.tts.is_talking)

    def test_synchronization(self):
        thread_start_event = threading.Event()
        tts_start_event = threading.Event()
        tts_done_event = threading.Event()
        self.events.extend([thread_start_event, tts_start_event, tts_done_event])

        def tts(*args):
            thread_start_event.set()
            wait(tts_start_event)
            self.tts.say("Test output")
            tts_done_event.set()

        audio_lock = self.resource_manager.get_read_lock(AUDIO_RESOURCE_NAME)

        with audio_lock:
            self.thread = threading.Thread(target=tts)
            self.thread.start()
            wait(thread_start_event)

            self.assertFalse(self.tts.is_talking)
            tts_start_event.set()

            await_predicate(lambda: audio_lock.interrupted)

            time.sleep(0.1)
            self.assertFalse(self.consume_start_event.is_set())
            self.assertFalse(self.tts.is_talking)

        wait(self.consume_start_event)

        self.assertTrue(self.tts.is_talking)
        self.assertFalse(audio_lock.acquire(blocking=False))

        self.consume_done_event.set()

        wait(tts_done_event)

        self.assertTrue(audio_lock.acquire(blocking=False))
        self.output_mock.consume.assert_called_once_with("Test output", None)
        self.assertFalse(self.tts.is_talking)