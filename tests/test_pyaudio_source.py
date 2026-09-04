import threading
import unittest
from unittest.mock import MagicMock, patch

from cltl.backend.source import pyaudio_source
from cltl.backend.source.pyaudio_source import PyAudioSource


class PyAudioSourceTest(unittest.TestCase):
    """Regression tests for the race where a second /audio request's session
    is torn down by the first request's delayed teardown, since both requests
    share a single PyAudioSource instance (see BackendServer._mic)."""

    def setUp(self):
        self.pyaudio_mock = MagicMock()
        self.pyaudio_mock.paInt16 = 8

        self.patcher = patch.object(pyaudio_source, "pyaudio", self.pyaudio_mock)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def _make_stream(self):
        stream = MagicMock()
        stream.get_time.return_value = 0
        stream.get_input_latency.return_value = 1000
        stream.read.return_value = b"\x00" * (2 * 480)
        return stream

    def _wait(self, event):
        if not event.wait(1):
            raise self.failureException("Latch timed out")

    def test_stale_teardown_from_first_request_does_not_stop_second(self):
        """Simulates: request 1 opens the mic, disconnects; request 2 opens a
        new session on a different thread before request 1's teardown thread
        gets around to calling stop(). Request 2's stream must keep working."""
        source = PyAudioSource(16000, 1, 480)
        stream1 = self._make_stream()
        stream2 = self._make_stream()
        self.pyaudio_mock.PyAudio.return_value.open.side_effect = [stream1, stream2]

        first_entered = threading.Event()
        second_entered = threading.Event()
        first_session = {}

        def request_one():
            with source as mic:
                first_session["generation"] = mic.session
                first_entered.set()
                self._wait(second_entered)
            # Simulates the teardown_request callback for request 1 racing
            # in after request 2 has already started its own session.
            source.stop(first_session["generation"])

        def request_two():
            self._wait(first_entered)
            with source as mic:
                second_entered.set()
                data = next(mic)
                self.assertEqual(stream2.read.return_value, data)

        t1 = threading.Thread(target=request_one)
        t2 = threading.Thread(target=request_two)
        t1.start()
        t2.start()
        t1.join(1)
        t2.join(1)

        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())
        stream2.close.assert_called_once()
        stream1.close.assert_not_called()

    def test_stop_without_generation_stops_current_session(self):
        source = PyAudioSource(16000, 1, 480)
        self.pyaudio_mock.PyAudio.return_value.open.return_value = self._make_stream()

        source.__enter__()
        source.stop()

        self.assertFalse(source.active)
        with self.assertRaises(StopIteration):
            next(source)

    def test_exit_closes_current_session(self):
        source = PyAudioSource(16000, 1, 480)
        stream = self._make_stream()
        self.pyaudio_mock.PyAudio.return_value.open.return_value = stream

        with source as mic:
            next(mic)

        stream.close.assert_called_once()
        self.assertFalse(source.active)


if __name__ == "__main__":
    unittest.main()
