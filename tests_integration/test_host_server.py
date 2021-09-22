import unittest

import numpy as np
from cltl.combot.backend.utils.audio import raw_frames_to_np

from host.server import backend_server

DEBUG = 0


class HostServerTest(unittest.TestCase):
    def test_mic(self):
        app = backend_server(sampling_rate=16000, channels=1, frame_size=480)
        with app.test_client() as client:
            rv = client.get('/mic')
            self.assertEqual("audio/L16;rate=16000;channels=1;frame_size=480",
                             rv.headers.get("content-type").replace(r' ', ''))

            num_frames = DEBUG if DEBUG else 10
            audio = [next(rv.iter_encoded()) for i in range(num_frames)]
            frames = list(raw_frames_to_np(audio, frame_size=480, channels=1, sample_depth=2))
            self.assertEqual([(480, 1)] * num_frames, [frame.shape for frame in frames])

            if DEBUG:
                import soundfile as sf
                sf.write("test.wav", data=np.concatenate(frames), samplerate=16000)
