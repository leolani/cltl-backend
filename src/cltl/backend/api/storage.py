import abc
from typing import Iterable, List, Union

import numpy as np


class AudioStorage(abc.ABC):
    def store(self, id: str, audio: Union[np.array, List[np.array]], sampling_rate: int):
        raise NotImplementedError()

    def get(self, id: str, offset: int = 0, length: int = -1) -> Iterable[np.array]:
        raise NotImplementedError()
