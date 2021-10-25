import numpy as np
from typing import Iterable


class AudioSource:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __iter__(self):
        return iter(self.audio)

    @property
    def audio(self) -> Iterable[np.ndarray]:
        raise NotImplementedError()

    @property
    def rate(self) -> int:
        raise NotImplementedError()

    @property
    def channels(self) -> int:
        raise NotImplementedError()

    @property
    def frame_size(self) -> int:
        raise NotImplementedError()

    @property
    def depth(self) -> int:
        raise NotImplementedError()