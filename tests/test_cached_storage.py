import shutil
import tempfile
import unittest
from queue import Queue
from threading import Thread, Event

import numpy as np

from cltl.backend.api.camera import Image, CameraResolution, Bounds
from cltl.backend.api.storage import AudioParameters
from cltl.backend.impl.cached_storage import CachedAudioStorage, CachedImageStorage


def wait(lock: Event):
    passed = lock.wait(1)
    if isinstance(passed, bool) and not passed:
        raise unittest.TestCase.failureException("Latch timed out")


class CachedAudioStorageTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.storage = CachedAudioStorage(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_store_mono(self):
        audio = np.random.randint(-1000, 1000, (8000,), dtype=np.int16)
        self.storage.store("1", audio, 16000)

        data, params = self.storage.get("1")
        actual = next(data)

        np.testing.assert_array_equal(actual, audio)

    def test_store_mono_2d(self):
        audio = np.random.randint(-1000, 1000, (8000,), dtype=np.int16).reshape(8000, 1)
        self.storage.store("1", audio, 16000)

        data, params = self.storage.get("1")
        actual = next(data)

        np.testing.assert_array_equal(actual, audio.ravel())

    def test_store_stereo(self):
        audio = np.random.randint(-1000, 1000, (4000, 2), dtype=np.int16)
        self.storage.store("1", audio, 16000)

        data, params = self.storage.get("1")
        actual = next(data)

        np.testing.assert_array_equal(actual, audio)

    def test_store_mono_frames(self):
        audio = [np.random.randint(-1000, 1000, (800,), dtype=np.int16) for i in range(10)]
        self.storage.store("1", audio, 16000)

        data, params = self.storage.get("1")
        actual = [frame for frame in data]

        np.testing.assert_array_equal(actual, audio)

    def test_store_mono_2d_frames(self):
        audio = [np.random.randint(-1000, 1000, (800, 1), dtype=np.int16) for i in range(10)]
        self.storage.store("1", audio, 16000)

        data, params = self.storage.get("1")
        actual = [frame for frame in data]

        np.testing.assert_array_equal(actual, [f.ravel() for f in audio])

    def test_store_stereo_frames(self):
        audio = [np.random.randint(-1000, 1000, (400, 2), dtype=np.int16) for i in range(10)]
        self.storage.store("1", audio, 16000)

        data, params = self.storage.get("1")
        actual = [frame for frame in data]

        np.testing.assert_array_equal(actual, audio)

    def test_read_with_offset(self):
        audio = [np.random.randint(-1000, 1000, (400, 2), dtype=np.int16) for i in range(10)]
        self.storage.store("1", audio, 16000)

        data, params = self.storage.get("1", offset=800)
        actual = [frame for frame in data]

        np.testing.assert_array_equal(actual, audio[2:])

    def test_read_with_length(self):
        audio = [np.random.randint(-1000, 1000, (400, 2), dtype=np.int16) for i in range(10)]
        self.storage.store("1", audio, 16000)

        data, params = self.storage.get("1", length=800)
        actual = [frame for frame in data]

        np.testing.assert_array_equal(actual, audio[:2])

    def test_read_with_offset_and_length(self):
        audio = [np.random.randint(-1000, 1000, (400, 2), dtype=np.int16) for i in range(10)]
        self.storage.store("1", audio, 16000)

        data, params = self.storage.get("1", offset=800, length=800)
        actual = [frame for frame in data]

        np.testing.assert_array_equal(actual, audio[2:4])

    def test_read_with_offset_not_matching_original_frames_not_supported(self):
        audio = [np.random.randint(-1000, 1000, (400, 2), dtype=np.int16) for i in range(10)]
        self.storage.store("1", audio, 16000)

        with self.assertRaisesRegex(ValueError, "400"):
            data, params = self.storage.get("1", offset=600, length=500)
            [frame for frame in data]

    def test_read_with_offset_from_cache(self):
        audio = [np.random.randint(-1000, 1000, (400, 2), dtype=np.int16) for i in range(10)]

        write_finished = Event()
        data_read = Event()

        def audio_generator():
            yield from audio
            write_finished.set()
            wait(data_read)

        write_thread = Thread(name="write", target=lambda: self.storage.store("1", audio_generator(), 16000))
        write_thread.start()
        wait(write_finished)

        data, params = self.storage.get("1", offset=800, length=400)
        actual = [frame for frame in data]

        data_read.set()

        np.testing.assert_array_equal(actual, audio[2:3])

        write_thread.join(timeout=1)

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

            frames, params = self.storage.get("1")
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

        write_thread.join(timeout=1)
        read_thread.join(timeout=1)

    def test_close_read_iterator_from_cache(self):
        audio = [np.random.randint(-1000, 1000, (400, 2), dtype=np.int16) for i in range(10)]

        write_finished = Event()
        data_read = Event()

        def audio_generator():
            yield from audio
            write_finished.set()
            wait(data_read)

        write_thread = Thread(name="write", target=lambda: self.storage.store("1", audio_generator(), 16000))
        write_thread.start()
        wait(write_finished)

        data, params = self.storage.get("1")
        actual = next(data)
        data.close()

        data_read.set()

        np.testing.assert_array_equal([actual], audio[:1])

        write_thread.join(timeout=1)

    def test_close_read_iterator(self):
        audio = [np.random.randint(-1000, 1000, (400, 2), dtype=np.int16) for i in range(10)]
        self.storage.store("1", audio, 16000)

        data, params = self.storage.get("1")
        actual = next(data)
        data.close()

        np.testing.assert_array_equal([actual], audio[:1])


    def test_parameters(self):
        audio = np.random.randint(-1000, 1000, (400, 2), dtype=np.int16)
        self.storage.store("1", audio, 16000)

        data, params = self.storage.get("1")

        self.assertEqual(AudioParameters(16000, 2, 400, 2), params)

    def test_parameters(self):
        audio = [np.random.randint(-1000, 1000, (400, 2), dtype=np.int16) for i in range(10)]
        self.storage.store("1", audio, 16000)

        data, params = self.storage.get("1")

        self.assertEqual(AudioParameters(16000, 2, 400, 2), params)

    def test_parameters_from_cache(self):
        audio = [np.random.randint(-1000, 1000, (400, 2), dtype=np.int16) for i in range(10)]

        write_finished = Event()
        data_read = Event()

        def audio_generator():
            yield from audio
            write_finished.set()
            wait(data_read)

        write_thread = Thread(name="write", target=lambda: self.storage.store("1", audio_generator(), 16000))
        write_thread.start()
        wait(write_finished)

        data, params = self.storage.get("1")
        data_read.set()

        self.assertEqual(AudioParameters(16000, 2, 400, 2), params)

        write_thread.join(timeout=1)


class CachedImageStorageTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.storage = CachedImageStorage(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_parameters_from_cache(self):
        bounds = Bounds(-0.55, -0.41 + np.pi / 2, 0.55, 0.41 + np.pi / 2)
        resolution = CameraResolution.QQQVGA

        image_array = np.random.randint(0, 256, (resolution.height, resolution.width, 3), dtype=np.uint8)
        depth_array = np.random.randint(0, 256, (resolution.height, resolution.width), dtype=np.uint8)
        image = Image(image_array, bounds, depth_array)

        self.storage.store("image1", image)
        stored = self.storage.get("image1")

        np.testing.assert_array_equal(image_array, stored.image)
        np.testing.assert_array_equal(bounds, stored.view)
        np.testing.assert_array_equal(depth_array, stored.depth)