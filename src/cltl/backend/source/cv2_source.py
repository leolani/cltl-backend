import cv2
import numpy as np

from cltl.backend.api.camera import Image, Bounds, CameraResolution
from cltl.backend.spi.image import ImageSource

SYSTEM_VIEW = Bounds(-0.55, -0.41 + np.pi / 2, 0.55, 0.41 + np.pi / 2)


class SystemImageSource(ImageSource):
    def __init__(self, resolution: CameraResolution, index=0):
        """
        Initialize SystemImageSource.

        Parameters
        ----------
        resolution: CameraResolution
            Camera resolution
        index: int
            Which system camera to use
        """
        self._resolution = resolution
        self._index = index
        self._camera = None

    def __enter__(self):
        self._camera = cv2.VideoCapture(self._index)

        if not self._resolution == CameraResolution.NATIVE:
            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution.width)
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution.height)

        if not self._camera.isOpened():
            raise RuntimeError("{} could not be opened".format(self.__class__.__name__))

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._camera.release()
        self._camera = None

    @property
    def resolution(self) -> CameraResolution:
        return self._resolution

    def capture(self) -> Image:
        # Sometimes the camera fails on the first image. We introduce a three trial policy to initialize the camera
        attempts = (self._camera.read() for _ in range(3))
        try:
            image = next(image for success, image in attempts if success)
        except StopIteration:
            raise RuntimeError("{} could not fetch image".format(self.__class__.__name__))

        if not self.resolution == CameraResolution.NATIVE:
            image = cv2.resize(image, (self.resolution.width, self.resolution.height))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        return Image(image, SYSTEM_VIEW)
