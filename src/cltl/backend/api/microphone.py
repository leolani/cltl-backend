import abc
import logging
from typing import Iterable

import numpy as np

logger = logging.getLogger(__name__)


TOPIC = "cltl.backend.api.microphone.topic"
AUDIO_RESOURCE_NAME = "cltl.backend.api.audio"
"""Resource name to be shared with the speaker to mute the microphone when the speaker is active.
The AbstractMicrophone holds a reader-lock on this resource.
"""
MIC_RESOURCE_NAME = "cltl.backend.api.microphone"
"""Resource name to be shared with application components that allows to retract microphone access from those components.
The AbstractMicrophone holds a writer-lock on this resource.
"""


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

    def mute(self) -> None:
        """
        Mute the microphone.

        This will terminate iterators returned from :meth:`listen`.
        """
        raise NotImplementedError()

    def listen(self) -> Iterable[np.array]:
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