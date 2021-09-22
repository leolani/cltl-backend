import logging
from types import SimpleNamespace

import requests
from cltl.combot.infra.config import ConfigurationManager

from cltl.backend.spi.audio import AudioSource
from cltl.backend.api.util import raw_frames_to_np, bytes_per_frame

logger = logging.getLogger(__name__)


CONTENT_TYPE_SEPARATOR = ';'


class ClientAudioSource(AudioSource):
    @classmethod
    def from_config(cls, config_manager: ConfigurationManager):
        backend_config = config_manager.get_config("cltl.backend")

        return cls(backend_config.get("server_url"))

    def __init__(self, url: str, offset: int = 0, length: int = -1):
        self._url = url
        self._length = length
        self._offset = offset
        self._request = None
        self._parameters = None
        self._iter = None

    def connect(self):
        self.__enter__()

    def __enter__(self):
        if self._request is not None:
            raise ValueError("Client is already in use")

        has_parameters = self._offset or self._length > 0
        params = {"offset": self._offset, "length": self._length} if has_parameters else None
        request = requests.get(self._url, params=params, stream=True).__enter__()

        content_type = request.headers['content-type'].split(CONTENT_TYPE_SEPARATOR)
        if not content_type[0].strip() == 'audio/L16' or len(content_type) != 4:
            # Only support 16bit audio for now
            raise ValueError("Unsupported content type {content_type[0]}, "
                             "expected audio/L16 with rate, channels and frame_size paramters")

        self._parameters = SimpleNamespace(**{p.split('=')[0].strip(): int(p.split('=')[1].strip())
                                              for p in content_type[1:]})
        self._parameters.depth = 2
        self._parameters.bytes_per_frame = bytes_per_frame(self._parameters.frame_size,
                                                           self._parameters.channels,
                                                           self._parameters.depth)

        logger.debug("Connected to backend at %s (%s, %s)", self._url, content_type[0], self._parameters)

        return self

    def close(self):
        self.__exit__(None, None, None)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._content.close()
        self._content = None
        self._parameters = None
        self._iter = None
        self._request.__exit__(exc_type, exc_val, exc_tb)

    @property
    def content(self):
        return self._request.iter_content(self._parameters.bytes_per_frame)

    @property
    def audio(self):
        return raw_frames_to_np(self.content)

    @property
    def rate(self):
        return self._parameters.rate if self._parameters else None

    @property
    def channels(self):
        return self._parameters.channels if self._parameters else None

    @property
    def frame_size(self):
        return self._parameters.frame_size if self._parameters else None

    @property
    def bytes_per_frame(self):
        return self._parameters.bytes_per_frame if self._parameters else None

    @property
    def depth(self):
        return self._parameters.depth if self._parameters else None
