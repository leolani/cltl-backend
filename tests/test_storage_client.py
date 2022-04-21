import shutil
import tempfile
import unittest
from threading import Thread

import numpy as np
from werkzeug.serving import make_server

from cltl.backend.api.camera import CameraResolution, Image
from cltl.backend.api.storage import STORAGE_SCHEME
from cltl.backend.api.util import raw_frames_to_np
from cltl.backend.impl.cached_storage import CachedAudioStorage, CachedImageStorage
from cltl.backend.source.client_source import ClientAudioSource, ClientImageSource
from cltl.backend.source.cv2_source import SYSTEM_VIEW
from cltl_service.backend.storage import StorageService

DEBUG = 0


class ServerThread(Thread):
    def __init__(self, app):
        Thread.__init__(self)
        self.server = make_server('0.0.0.0', 9999, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


class StorageServiceTest(unittest.TestCase):
    def setUp(self):
        self.server = None
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if self.server:
            self.server.shutdown()
            self.server.join()

        shutil.rmtree(self.tmp_dir)

    def test_audio_client(self):
        audio_storage = CachedAudioStorage(self.tmp_dir)
        storage_service = StorageService(storage_audio=audio_storage, storage_image=None)

        audio = [np.random.randint(-1000, 1000, (480, 2), dtype=np.int16) for i in range(10)]
        audio_storage.store("1", audio, sampling_rate=16000)

        self.server = ServerThread(storage_service.app)
        self.server.start()

        with ClientAudioSource("http://0.0.0.0:9999/audio/1") as source:
            self.assertEqual(16000, source.rate)

            actual = [frame for frame in source.audio]
            frames = list(raw_frames_to_np(actual, frame_size=480, channels=2, sample_depth=2))
            np.testing.assert_array_equal(audio, frames)

    def test_audio_client_with_custom_schema(self):
        audio_storage = CachedAudioStorage(self.tmp_dir)
        storage_service = StorageService(storage_audio=audio_storage, storage_image=None)

        audio = [np.random.randint(-1000, 1000, (480, 2), dtype=np.int16) for i in range(10)]
        audio_storage.store("1", audio, sampling_rate=16000)

        self.server = ServerThread(storage_service.app)
        self.server.start()

        with ClientAudioSource(f"{STORAGE_SCHEME}:/audio/1", "http://0.0.0.0:9999") as source:
            self.assertEqual(16000, source.rate)

            actual = [frame for frame in source.audio]
            frames = list(raw_frames_to_np(actual, frame_size=480, channels=2, sample_depth=2))
            np.testing.assert_array_equal(audio, frames)

    def test_image_client(self):
        image_storage = CachedImageStorage(self.tmp_dir)
        storage_service = StorageService(storage_audio=None, storage_image=image_storage)

        resolution = CameraResolution.QQQVGA
        image_array = np.zeros((resolution.height, resolution.width, 3),
                                        dtype=np.uint8)
        depth_array = np.random.randint(0, 256, (resolution.height, resolution.width),
                                        dtype=np.uint8)
        image = Image(image_array, SYSTEM_VIEW, depth_array)
        image_storage.store("1", image)

        self.server = ServerThread(storage_service.app)
        self.server.start()

        with ClientImageSource("http://0.0.0.0:9999/image/1") as source:
            capture = source.capture()
            source_resolution = source.resolution

        self.assertEqual(resolution, source_resolution)
        np.testing.assert_array_equal(image_array, capture.image)
        self.assertEqual(SYSTEM_VIEW, capture.view)
        np.testing.assert_array_equal(depth_array, capture.depth)

    def test_image_client_with_custom_schema(self):
        image_storage = CachedImageStorage(self.tmp_dir)
        storage_service = StorageService(storage_audio=None, storage_image=image_storage)

        resolution = CameraResolution.QQQVGA
        image_array = np.zeros((resolution.height, resolution.width, 3),
                               dtype=np.uint8)
        depth_array = np.random.randint(0, 256, (resolution.height, resolution.width),
                                        dtype=np.uint8)
        image = Image(image_array, SYSTEM_VIEW, depth_array)
        image_storage.store("1", image)

        self.server = ServerThread(storage_service.app)
        self.server.start()

        with ClientImageSource(f"{STORAGE_SCHEME}:/image/1", "http://0.0.0.0:9999") as source:
            image = source.capture()
            source_resolution = source.resolution

        self.assertEqual(resolution, source_resolution)
        np.testing.assert_array_equal(image_array, image.image)
        self.assertEqual(SYSTEM_VIEW, image.view)
        np.testing.assert_array_equal(depth_array, image.depth)

    def test_image_client_capture_first(self):
        image_storage = CachedImageStorage(self.tmp_dir)
        storage_service = StorageService(storage_audio=None, storage_image=image_storage)

        resolution = CameraResolution.QQQVGA
        image_array = np.zeros((resolution.height, resolution.width, 3),
                               dtype=np.uint8)
        depth_array = np.random.randint(0, 256, (resolution.height, resolution.width),
                                        dtype=np.uint8)
        image = Image(image_array, SYSTEM_VIEW, depth_array)
        image_storage.store("1", image)

        self.server = ServerThread(storage_service.app)
        self.server.start()

        with ClientImageSource(f"{STORAGE_SCHEME}:/image/1", "http://0.0.0.0:9999") as source:
            source_resolution = source.resolution
            self.assertEqual(resolution, source_resolution)

            image = source.capture()

            source_resolution = source.resolution
            self.assertEqual(resolution, source_resolution)

        np.testing.assert_array_equal(image_array, image.image)
        self.assertEqual(SYSTEM_VIEW, image.view)
        np.testing.assert_array_equal(depth_array, image.depth)

