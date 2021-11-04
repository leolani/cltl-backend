import shutil
import tempfile
import unittest
from threading import Thread

import numpy as np
from werkzeug.serving import make_server

from cltl.backend.api.storage import STORAGE_SCHEME
from cltl.backend.api.util import raw_frames_to_np
from cltl.backend.impl.cached_storage import CachedAudioStorage
from cltl.backend.source.client_source import ClientAudioSource
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
        storage_service = StorageService(storage=audio_storage)

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
        storage_service = StorageService(storage=audio_storage)

        audio = [np.random.randint(-1000, 1000, (480, 2), dtype=np.int16) for i in range(10)]
        audio_storage.store("1", audio, sampling_rate=16000)

        self.server = ServerThread(storage_service.app)
        self.server.start()

        with ClientAudioSource(f"{STORAGE_SCHEME}:/audio/1", "http://0.0.0.0:9999") as source:
            self.assertEqual(16000, source.rate)

            actual = [frame for frame in source.audio]
            frames = list(raw_frames_to_np(actual, frame_size=480, channels=2, sample_depth=2))
            np.testing.assert_array_equal(audio, frames)
