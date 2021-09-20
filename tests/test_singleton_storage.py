import shutil
import tempfile
import unittest
from queue import Queue
from threading import Thread, Event

import numpy as np
from cltl.backend.impl.singleton_storage import CachedAudioStorage


def wait(lock: Event):
    passed = lock.wait(600)
    if isinstance(passed, bool) and not passed:
        raise unittest.TestCase.failureException("Latch timed out")


class SynchronizedMicrophoneTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.storage = CachedAudioStorage(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_store_mono(self):
        audio = np.random.randint(-1000, 1000, (8000,), dtype=np.int16)
        self.storage.store("1", audio, 16000)

        actual = next(self.storage.get("1"))
        np.testing.assert_array_equal(actual, audio)

    def test_store_mono_2d(self):
        audio = np.random.randint(-1000, 1000, (8000,), dtype=np.int16).reshape(8000, 1)
        self.storage.store("1", audio, 16000)

        actual = next(self.storage.get("1"))
        np.testing.assert_array_equal(actual, audio.ravel())

    def test_store_stereo(self):
        audio = np.random.randint(-1000, 1000, (4000, 2), dtype=np.int16)
        self.storage.store("1", audio, 16000)

        actual = next(self.storage.get("1"))
        np.testing.assert_array_equal(actual, audio)

    def test_store_mono_frames(self):
        audio = [np.random.randint(-1000, 1000, (800,), dtype=np.int16) for i in range(10)]
        self.storage.store("1", audio, 16000)

        actual = [frame for frame in self.storage.get("1")]
        np.testing.assert_array_equal(actual, audio)

    def test_store_mono_2d_frames(self):
        audio = [np.random.randint(-1000, 1000, (800, 1), dtype=np.int16) for i in range(10)]
        self.storage.store("1", audio, 16000)

        actual = [frame for frame in self.storage.get("1")]
        np.testing.assert_array_equal(actual, [f.ravel() for f in audio])

    def test_store_stereo_frames(self):
        audio = [np.random.randint(-1000, 1000, (400, 2), dtype=np.int16) for i in range(10)]
        self.storage.store("1", audio, 16000)

        actual = [frame for frame in self.storage.get("1")]
        np.testing.assert_array_equal(actual, audio)

    def test_read_write_parallel(self):
        """
        In a synchronized manner:
            * Write a chunk of frames
            * Read a chunk of frames

        The last read should access the persisted audio file.
        """
        started = Event()
        frames_written = Event()
        frames_read = Event()
        write_done = Event()
        read_done = Event()

        actual = Queue()

        audio = [np.random.randint(-1000, 1000, (4, 2), dtype=np.int16) for _ in range(10)]
        chunk = 2
        def audio_generator():
            for i, frame in enumerate(audio):
                yield frame

                if i > 0 and i % chunk == 0:
                    # After a chunk is written, wait until it is read and reset the read latch
                    frames_written.set()
                    started.set()
                    wait(frames_read)
                    frames_read.clear()

            frames_written.set()
            write_done.set()
        write_thread = Thread(name="write", target=lambda: self.storage.store("1", audio_generator(), 16000))

        def read():
            wait(started)

            frames = self.storage.get("1")
            wait(frames_written)
            for i, frame in enumerate(frames):
                actual.put(frame)

                if i > 0 and i % chunk == 0:
                    # After a chunk is read, reset the write latch and wait until the next one is written
                    frames_read.set()
                    if not write_done.isSet():
                        wait(frames_written)
                        frames_written.clear()

            read_done.set()
        read_thread = Thread(name="read", target=read)

        write_thread.start()
        read_thread.start()

        wait(write_done)
        wait(read_done)

        np.testing.assert_array_equal(actual.queue, audio)



