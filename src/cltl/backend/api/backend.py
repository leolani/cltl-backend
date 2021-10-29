import logging

from cltl.backend.api.microphone import Microphone
from cltl.backend.api.text_to_speech import TextToSpeech

logger = logging.getLogger(__name__)


class Backend:
    """
    Abstract Backend on which all Backends are based

    Exposes
    :class:`~cltl.backend.api.microphone.Microphone`

    Parameters
    ----------
    microphone: Microphone
        Backend :class:`~cltl.backend.api.microphone.Microphone`
    """

    def __init__(self, microphone: Microphone):
        self._microphone = microphone

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        if self._microphone:
            self._microphone.start()

    def stop(self):
        self._stop_safe(self._microphone)

    def _stop_safe(self, component):
        if component:
            try:
                component.stop()
            except:
                logger.exception("Failed to stop " + str(component))

    @property
    def microphone(self) -> Microphone:
        """
        Reference to :class:`~cltl.backend.api.microphone.Microphone`

        Returns
        -------
        Microphone
        """
        return self._microphone

    @property
    def text_to_speech(self) -> TextToSpeech:
        """
        Reference to :class:`~cltl.backend.api.text_to_speech.TextToSpeech`

        Returns
        -------
        TextToSpeech
        """
        return self._text_to_speech
