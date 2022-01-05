import time
from typing import Iterable

from cltl.combot.infra.util import ThreadsafeBoolean

from cltl.backend.api.camera import Camera, Image, CameraResolution
from cltl.backend.spi.image import ImageSource


class ImageCamera(Camera):
    def __init__(self, image_source: ImageSource, rate: float):
        self._image_source = image_source
        self._rate = rate
        self._recording = ThreadsafeBoolean()
        self._interrupt = ThreadsafeBoolean()

    def start(self):
        self._image_source.__enter__()

    def stop(self):
        self._image_source.__exit__(None, None, None)

    @property
    def rate(self) -> int:
        return self._rate

    @property
    def resolution(self) -> CameraResolution:
        return self._image_source.resolution

    def capture(self) -> Image:
        return self._image_source.capture()

    def record(self) -> Iterable[Image]:
        if self.rate < 0:
            return []

        self._recording.value = True

        def image_generator():
            interval = int(1e9 * self._rate)
            start = time.time_ns()
            self._interrupt.value = False

            while not self._interrupt.value:
                if self._rate > 0:
                    # Quantize images to interval bounds
                    elapsed = (time.time_ns() - start) % interval
                    time.sleep((interval - elapsed) * 1e-9)

                yield self.capture()

            self._recording.value = False

        return image_generator()

    def stop_recording(self):
        self._interrupt.value = True

    @property
    def is_recording(self) -> bool:
        return self._recording.value