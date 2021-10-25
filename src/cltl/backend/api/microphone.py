import abc
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterable

import numpy as np

logger = logging.getLogger(__name__)


AUDIO_RESOURCE_NAME = "cltl.backend.api.audio"
"""Resource name to be shared with the speaker to mute the microphone when the speaker is active.
The AbstractMicrophone holds a reader-lock on this resource.
"""
MIC_RESOURCE_NAME = "cltl.backend.api.microphone"
"""Resource name to be shared with application components that allows to retract microphone access from those components.
The AbstractMicrophone holds a writer-lock on this resource.
"""


@dataclass
class AudioParameters:
    sampling_rate: int
    channels : int
    frame_size: int
    sample_width: int


class AudioFormat:
    L16_MONO_16K_30MS = AudioParameters(16000, 1, 480, 2)


class Microphone(abc.ABC):
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        pass

    def stop(self):
        pass

    @property
    def parameters(self) -> AudioParameters:
        raise NotImplementedError()

    def mute(self) -> None:
        """
        Mute the microphone.

        This will terminate iterators returned from :meth:`listen`.
        """
        raise NotImplementedError()

    @contextmanager
    def listen(self) -> [Iterable[np.ndarray], AudioParameters]:
        """
        Retrieve an audio stream from the microphone.

        This will provide a generator stream of audio input when. If the
        microphone is muted, This method will set the muted flag to False and
        will block until this can be achieved.
        """
        raise NotImplementedError()

    @property
    def muted(self) -> bool:
        """
        Indicate if the microphone is muted.
        """
        raise NotImplementedError()