import abc
import logging
from typing import Any


logger = logging.getLogger(__name__)


class TextToSpeech(abc.ABC):
    def __enter__(self) -> Any:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def start(self) -> Any:
        raise NotImplementedError()

    def stop(self) -> None:
        raise NotImplementedError()

    def say(self, text: str) -> None:
        raise NotImplementedError()

    @property
    def is_talking(self) -> bool:
        raise NotImplementedError()

    @property
    def language(self) -> str:
        """
        Returns
        -------
        str
            `Language Code <https://cloud.google.com/speech/docs/languages>`_
        """
        raise NotImplementedError()