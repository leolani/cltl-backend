import abc
from dataclasses import dataclass
from typing import Iterable, List, Union

import numpy as np


@dataclass
class AudioParameters:
    sampling_rate: int
    channels : int
    frame_size: int
    sample_width: int


class AudioStorage(abc.ABC):
    def store(self, id: str, audio: Union[np.array, List[np.array]], sampling_rate: int):
        raise NotImplementedError()

    def get(self, id: str, offset: int = 0, length: int = -1) -> (Iterable[np.array], AudioParameters):
        """
        Return audio data for the given id, starting from the given offset.

        Parameters
        ----------
        id : str
            The id of the audio data.
        offset : int
            The index of the starting sample in the stored audio data.
        length :
            The number of samples to be returned.

        Returns
        -------
        Iterable[np.array]:
            The audio data, split into chunks.
        AudioParameters
            The :class:`AudioParameters` of the returned audio.
        """
        raise NotImplementedError()
