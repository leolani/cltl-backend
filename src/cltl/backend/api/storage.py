import abc
from typing import Iterable, List, Union

import numpy as np

from cltl.backend.api.camera import Image
from cltl.backend.api.microphone import AudioParameters

STORAGE_SCHEME = "cltl-storage"


# TODO rename id to identifier
class AudioStorage(abc.ABC):
    def store(self, id: str, audio: Union[np.ndarray, Iterable[np.ndarray]], sampling_rate: int):
        raise NotImplementedError()

    def get(self, id: str, offset: int = 0, length: int = -1) -> (Iterable[np.ndarray], AudioParameters):
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
            The :class:`~cltl.backend.api.microphone.AudioParameters` of the returned audio.
        """
        raise NotImplementedError()


class ImageStorage(abc.ABC):
    def store(self, id: str, image: Image):
        raise NotImplementedError()

    def get(self, id: str) -> Image:
        """
        Return image data for the given id.

        Parameters
        ----------
        id : str
            The id of the audio data.

        Returns
        -------
        Image:
            The image data.
        """
        raise NotImplementedError()
