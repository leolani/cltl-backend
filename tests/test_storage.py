import shutil
import tempfile
import unittest

import numpy as np
from cltl.backend.api.util import raw_frames_to_np

from cltl.backend.impl.cached_storage import CachedAudioStorage
from cltl_service.backend.storage import StorageService


DEBUG = 0


class StorageServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_storage(self):
        audio_storage = CachedAudioStorage(self.tmp_dir)
        storage_service = StorageService(storage_audio=audio_storage, storage_image=None)

        audio = [np.random.randint(-1000, 1000, (480, 2), dtype=np.int16) for i in range(10)]
        audio_storage.store("1", audio, sampling_rate=16000)

        with storage_service.app.test_client() as client:
            rv = client.get('/audio/1')
            self.assertEqual("audio/L16;rate=16000;channels=2;frame_size=480",
                             rv.headers.get("content-type").replace(r' ', ''))

            actual = [frame for frame in rv.iter_encoded()]
            frames = list(raw_frames_to_np(actual, frame_size=480, channels=2, sample_depth=2))
            np.testing.assert_array_equal(audio, frames)

            if DEBUG:
                import soundfile as sf
                sf.write("test.wav", data=np.concatenate(frames), samplerate=16000)
