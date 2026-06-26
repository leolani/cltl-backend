import io
import logging
import os.path
import re
import tempfile
import time
from typing import Optional

import requests
from gtts import gTTS
from playsound import playsound
from pydub import AudioSegment

from cltl.backend.spi.text import TextOutput

logger = logging.getLogger(__name__)


class LocalTTSOutput(TextOutput):
    def __init__(self, sound_url: str = None):
        self._temp_dir = tempfile.TemporaryDirectory()
        self._output_path = None
        self._sound_url = sound_url

    def __enter__(self):
        self._output_path = f"{self._temp_dir.name}/{time.time_ns()}.mp3"

    def __exit__(self, exc_type, exc_val, exc_tb):
        if os.path.isfile(self._output_path):
            os.remove(self._output_path)

    def consume(self, text: str, language: Optional[str] = None):
        text = re.sub(r'[\\]pau\s*=\s*\d*[\\]', '', text)
        tts = gTTS(text=text, lang=language if language else "en", slow=False)
        tts.save(self._output_path)

        if self._sound_url:
            self._play_remote()
        else:
            playsound(self._output_path)

    def _play_remote(self):
        mp3_audio = AudioSegment.from_mp3(self._output_path)
        wav_buf = io.BytesIO()
        mp3_audio.export(wav_buf, format="wav")
        wav_bytes = wav_buf.getvalue()

        response = requests.post(
            f"{self._sound_url}/sound",
            data=wav_bytes,
            headers={"Content-Type": "audio/wav"},
        )
        if response.status_code != 200:
            logger.warning("Remote /sound returned %s: %s", response.status_code, response.text)
