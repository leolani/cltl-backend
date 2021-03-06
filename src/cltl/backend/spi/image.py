from cltl.backend.api.camera import Image, CameraResolution


class ImageSource:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @property
    def resolution(self) -> CameraResolution:
        raise NotImplementedError()

    def capture(self) -> Image:
        raise NotImplementedError()
