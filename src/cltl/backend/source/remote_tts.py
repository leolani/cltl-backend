import logging
import random
from typing import List, Optional

import requests

from cltl.backend.api.gestures import GestureType
from cltl.backend.spi.text import TextOutput

logger = logging.getLogger(__name__)


class AnimatedRemoteTextOutput(TextOutput):
    """
    Sends text to a remote TTS system. Text is annotated with random gestures
    following the syntax in:

    http://doc.aldebaran.com/2-8/naoqi/audio/alanimatedspeech.html?highlight=animated
    """

    def __init__(self, remote_url: str, gestures: List[GestureType] = None):
        self._remote_url = remote_url
        self._gestures = gestures if gestures is not None else list(GestureType)

    def consume(self, text: str, language: Optional[str] = None):
        tts_headers = {'Content-type': 'text/plain'}

        if self._gestures:
            animation = f"{random.choice(self._gestures).name.lower()}"
            response = f"^startTag({animation}) {text} ^stopTag({animation})"
        else:
            response = text
        logger.debug("Remote text output: %s", response)

        requests.post(f"{self._remote_url}/text", data=response.encode('utf-8'), headers=tts_headers)
