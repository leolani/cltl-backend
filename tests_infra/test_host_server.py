import json
import logging
import unittest

import numpy as np
from emissor.representation.scenario import Modality

from cltl.backend.api.camera import CameraResolution
from cltl.backend.api.util import raw_frames_to_np
from cltl.backend.source.cv2_source import SYSTEM_BOUNDS
from cltl.backend.server import BackendServer


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)


DEBUG = 0


class HostServerTest(unittest.TestCase):
    def test_mic(self):
        server = BackendServer(sampling_rate=16000, channels=1, frame_size=480,
                               camera_resolution=CameraResolution.NATIVE, camera_index=0)
        with server.app.test_client() as client:
            rv = client.get(f"/{Modality.AUDIO.name.lower()}")
            self.assertEqual("audio/L16;rate=16000;channels=1;frame_size=480",
                             rv.headers.get("content-type").replace(r' ', ''))

            num_frames = DEBUG if DEBUG else 10
            audio = [next(rv.iter_encoded()) for i in range(num_frames)]
            frames = list(raw_frames_to_np(audio, frame_size=480, channels=1, sample_depth=2))
            self.assertEqual([(480, 1)] * num_frames, [frame.shape for frame in frames])

            if DEBUG:
                import soundfile as sf
                sf.write("test.wav", data=np.concatenate(frames), samplerate=16000)

    def test_cam(self):
        resolution = CameraResolution.VGA
        server = BackendServer(sampling_rate=16000, channels=1, frame_size=480,
                               camera_resolution=resolution, camera_index=0)
        with server.app.test_client() as client:
            rv = client.get(f"/{Modality.VIDEO.name.lower()}")
            self.assertEqual("application/json", rv.headers.get("content-type").split(";")[0], rv.status)
            self.assertRegex(rv.headers.get("content-type"), f"resolution\\s*=\\s*{resolution.name}\\s*[;]?", rv.status)

            image = json.loads(rv.data)

            self.assertEqual(None, image['depth'])
            self.assertEqual(vars(SYSTEM_BOUNDS), image['bounds'])
            self.assertEqual((resolution.height, resolution.width, 3), np.array(image['image']).shape)
            self.assertTrue(all(isinstance(i, np.integer) for i in np.array(image['image']).flatten()))
