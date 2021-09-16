import logging
import pyaudio
import uuid

logger = logging.getLogger(__name__)


class PyAudioMic:
    BUFFER = 8

    def __init__(self, rate, channels, frame_size):
        self.id = str(uuid.uuid4())[:6]

        self._rate = rate
        self._channels = channels
        self._frame_size = frame_size

        self._pyaudio = pyaudio.PyAudio()
        self._active = False
        self._start_time = None
        self._time = None

    @property
    def active(self):
        return self._active

    @property
    def time(self):
        return self._mic_time - self._start_time

    @property
    def _mic_time(self):
        return self._time

    @_mic_time.setter
    def _mic_time(self, stream_time):
        advanced = stream_time - self._time
        if advanced > self._stream.get_input_latency():
            logger.exception("Latency exceeded buffer (%.4fsec) - dropped frames: %.4fsec",
                             self._stream.get_input_latency(), advanced)
        self._time = stream_time

    def stop(self):
        self._active = False
        logger.debug("Stopped microphone (%s)", self.id)

    def __enter__(self):
        self._stream = self._pyaudio.open(self._rate, self._channels, pyaudio.paInt16, input=True,
                                          frames_per_buffer=self.BUFFER * self._frame_size)
        self._active = True
        self._start_time = self._stream.get_time()
        self._time = self._start_time

        logger.debug("Opened microphone (%s) with rate: %s, channels: %s, frame_size: %s",
                     self.id, self._rate, self._channels, self._frame_size)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._active:
            self._active = False
            self._stream.close()
            logger.debug("Closed microphone (%s)", self.id)
        else:
            logger.warning("Ignored close microphone (%s)", self.id)

    def __iter__(self):
        return self

    def __next__(self):
        if not self._active:
            raise StopIteration()

        data = self._stream.read(self._frame_size, exception_on_overflow=False)
        self._mic_time = self._stream.get_time()

        return data