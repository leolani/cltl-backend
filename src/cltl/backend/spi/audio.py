import numpy as np
from typing import Generator, Iterator


class AudioSource:
    def __enter__(self):
        return iter(self)

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __iter__(self):
        return self.audio()

    def audio(self) -> Iterator[np.array]:
        raise NotImplementedError()

    @property
    def rate(self):
        raise NotImplementedError()

    @property
    def channels(self):
        raise NotImplementedError()

    @property
    def frame_size(self):
        raise NotImplementedError()

    @property
    def depth(self):
        raise NotImplementedError()