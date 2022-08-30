from typing import Iterable, Iterator

import numpy as np


class AudioSource:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __iter__(self) -> Iterator[bytes]:
        return self

    def __next__(self) -> bytes:
        raise NotImplementedError()

    @property
    def audio(self) -> Iterable[np.ndarray]:
        raise NotImplementedError()

    @property
    def raw(self) -> Iterable[bytes]:
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