import logging

from cltl.combot.infra.resource.api import ResourceManager
from cltl.combot.infra.util import ThreadsafeBoolean

from cltl.backend.api.microphone import AUDIO_RESOURCE_NAME
from cltl.backend.api.text_to_speech import TextToSpeech
from cltl.backend.spi.audio import AudioSource
from cltl.backend.spi.text import TextOutput

logger = logging.getLogger(__name__)


class TextOutputTTS(TextToSpeech):
    def __init__(self, text_output: TextOutput, language: str = None):
        self._text_output = text_output
        self._language = language

        self. _is_talking = ThreadsafeBoolean()

    def start(self):
        return self._text_output.__enter__()

    def stop(self):
        self._text_output.__exit__(None, None, None)

    def say(self, text: str):
        self._is_talking.value = True
        try:
            self._text_output.consume(text, self.language)
        finally:
            self._is_talking.value = False

    @property
    def is_talking(self) -> bool:
        return self._is_talking.value

    @property
    def language(self) -> str:
        return self._language



class SynchronizedTextToSpeech(TextToSpeech):
    def __init__(self, tts: TextToSpeech, resource_manager: ResourceManager):
        """
        A SynchronizedMicrophone can be synchronized with other audio activity.

        Parameters
        ----------
        source: AudioSource
            The source of audio data
        resource_manager : ResourceManager
            Resource manager to manage access to the microphone resource
        """
        self._tts = tts
        self._resource_manager = resource_manager

    def start(self):
        return self._tts.start()

    def stop(self):
        self._tts.stop()

    def say(self, text: str):
        try:
            logger.debug("Await talking")
            with self._resource_manager.get_write_lock(AUDIO_RESOURCE_NAME):
                logger.debug("Talking")
                self._tts.say(text)
        except:
            logger.exception("Failed to convert text to speech")

    @property
    def is_talking(self) -> bool:
        return self._tts.is_talking

    @property
    def language(self) -> str:
        return self._tts.language
