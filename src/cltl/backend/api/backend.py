import logging

from cltl.backend.api.camera import Camera
from cltl.backend.api.microphone import Microphone
from cltl.backend.api.text_to_speech import TextToSpeech

logger = logging.getLogger(__name__)


class Backend:
    """
    Central class providing all backend functionality.

    Exposes
    :class:`~cltl.backend.api.microphone.Microphone`
    :class:`~cltl.backend.api.camera.Camera`
    :class:`~cltl.backend.api.text_to_speech.TextToSpeech`

    Parameters
    ----------
    microphone: Microphone
        Backend :class:`~cltl.backend.api.microphone.Microphone`
    camera: Camera
        Backend :class:`~cltl.backend.api.camera.Camera`
    tts: TextToSpeech
        Backend :class:`~cltl.backend.api.tts.TextToSpeech`
    """

    def __init__(self, microphone: Microphone, camera: Camera, tts: TextToSpeech):
        self._microphone = microphone
        self._camera = camera
        self._tts = tts

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        if self._microphone:
            self._microphone.start()
        if self._camera:
            self._camera.start()
        if self._tts:
            self._tts.start()

    def stop(self):
        if self._microphone:
            self._stop_safe(self._microphone)
        if self._camera:
            self._stop_safe(self._camera)
        if self._tts:
            self._stop_safe(self._tts)

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
    def camera(self) -> Camera:
        """
        Reference to :class:`~cltl.backend.api.microphone.Camera`

        Returns
        -------
        Camera
        """
        return self._camera


    @property
    def text_to_speech(self) -> TextToSpeech:
        """
        Reference to :class:`~cltl.backend.api.text_to_speech.TextToSpeech`

        Returns
        -------
        TextToSpeech
        """
        return self._tts
