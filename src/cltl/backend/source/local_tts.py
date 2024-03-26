import os.path
import tempfile
import time
from typing import Optional

from gtts import gTTS
from playsound import playsound

from cltl.backend.spi.text import TextOutput


class LocalTTSOutput(TextOutput):
    def __init__(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self._output_path = None

    def __enter__(self):
        self._output_path = f"{self._temp_dir.name}/{time.time_ns()}.mp3"

    def __exit__(self, exc_type, exc_val, exc_tb):
        if os.path.isfile(self._output_path):
            os.remove(self._output_path)

    def consume(self, text: str, language: Optional[str] = None):
        myobj = gTTS(text=text, lang=language if language else "en", slow=False)
        myobj.save(self._output_path)
        playsound(self._output_path)
