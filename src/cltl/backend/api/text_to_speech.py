import abc
import logging

logger = logging.getLogger(__name__)


class TextToSpeech(abc.ABC):
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def say(self, text: str):
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