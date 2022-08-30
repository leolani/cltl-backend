import logging
import sys
import threading
import time
import unittest

import numpy as np

from cltl.backend.api.camera import Image, CameraResolution, Bounds
from cltl.backend.impl.image_camera import ImageCamera
from cltl.backend.spi.image import ImageSource

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(stream=sys.stdout))
logger.setLevel(logging.DEBUG)


def wait(lock: threading.Event):
    if not lock.wait(1):
        raise unittest.TestCase.failureException("Latch timed out")


class TestSource(ImageSource):
    def __init__(self, processing: threading.Event = None,
                 pause_processing: threading.Event = None):
        self.cnt = 0
        self.processing = processing
        self.pause_processing = pause_processing

    @property
    def resolution(self) -> CameraResolution:
        return CameraResolution.QQQQVGA

    def capture(self) -> Image:
        if self.processing:
            self.processing.set()
        if self.pause_processing:
            wait(self.pause_processing)

        self.cnt += 1
        return Image(np.full(self.resolution.value, self.cnt), Bounds(*((0,0) + self.resolution.value)))


class ImageCameraTest(unittest.TestCase):
    def setUp(self):
        self.thread = None
        self.camera = None

    def tearDown(self):
        if self.camera:
            self.camera.stop_recording()
        if self.thread:
            self.thread.join()

    def test_capture(self):
        source = TestSource()
        self.camera = ImageCamera(source, -1)

        with self.camera as camera:
            captured = camera.capture()
            np.testing.assert_array_equal(np.full(self.camera.resolution.value, 1), captured.image)

            captured = camera.capture()
            np.testing.assert_array_equal(np.full(camera.resolution.value, 2), captured.image)

    def test_record(self):
        source = TestSource()
        self.camera = ImageCamera(source, 0)

        with self.camera as cam:
            images = cam.record()
            recorded = [next(images) for i in range(10)]
            cam.stop_recording()

        self.assertEqual(10, len(recorded))
        for cnt, image in enumerate(recorded):
            np.testing.assert_array_equal(np.full(self.camera.resolution.value, cnt + 1), image.image)

    def test_stop_recording(self):
        processing = threading.Event()
        pause_processing = threading.Event()
        pause_processing.set()

        source = TestSource(processing, pause_processing)
        self.camera = ImageCamera(source, 0)

        images = []
        def record():
            with self.camera as cam:
                recording = cam.record()
                for image in recording:
                    images.append(image)

        self.thread = threading.Thread(target=record)
        self.thread.start()

        wait(processing)

        self.assertTrue(self.camera.is_recording)

        pause_processing.clear()
        processing.clear()
        processing.wait(0.1)

        self.camera.stop_recording()

        self.assertTrue(self.camera.is_recording)

        pause_processing.set()

        self.thread.join(1)
        self.assertFalse(self.thread.is_alive())
        self.assertFalse(self.camera.is_recording)


    def test_recording_rate(self):
        processing = threading.Event()
        pause_processing = threading.Event()
        pause_processing.set()

        source = TestSource(processing, pause_processing)
        self.camera = ImageCamera(source, 100)

        images = []
        def record():
            with self.camera as cam:
                recording = cam.record()
                for image in recording:
                    images.append((image, time.time_ns()))

        camera_thread = threading.Thread(target=record)
        camera_thread.start()

        wait(processing)

        while len(images) < 25:
            time.sleep(0.01)

        interval = 0.01 * 1e9
        image_timestamps = [timestamp for timestamp in tuple(zip(*images))[1]]
        intervals = [end - start for start, end in zip(image_timestamps[:-1], image_timestamps[1:])]
        for actual in intervals:
            self.assertAlmostEqual(0, abs(actual - interval)/interval, delta=0.5)
        self.assertAlmostEqual(1, (image_timestamps[-1] - image_timestamps[0])/((len(images) - 1) * interval), delta=0.025)

        self.camera.stop_recording()

        camera_thread.join(1)
        self.assertFalse(camera_thread.is_alive())
        self.assertFalse(self.camera.is_recording)