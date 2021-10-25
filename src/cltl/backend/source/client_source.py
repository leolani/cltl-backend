import logging
from types import SimpleNamespace
from urllib.parse import urljoin

import requests
from cltl.combot.infra.config import ConfigurationManager
from requests.adapters import HTTPAdapter, BaseAdapter

from cltl.backend.api.storage import STORAGE_SCHEME
from cltl.backend.api.util import raw_frames_to_np, bytes_per_frame
from cltl.backend.spi.audio import AudioSource

logger = logging.getLogger(__name__)


CONTENT_TYPE_SEPARATOR = ';'


class CltlAudioAdapter(BaseAdapter):
    """"Transport adapter" to support cltl-audio:// schema."""
    def __init__(self, storage_url):
        self._storage_url = storage_url
        self._http_adapter = HTTPAdapter()

    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        storage_request = request.copy()

        path = storage_request.url.split(f"{STORAGE_SCHEME}:")[1]
        storage_request.url = urljoin(self._storage_url, path)

        logger.debug("Resolve %s to %s", request.url, storage_request.url)

        return self._http_adapter.send(storage_request, stream, timeout, verify, cert, proxies)

    def close(self):
        self._http_adapter.close()


class ClientAudioSource(AudioSource):
    @classmethod
    def from_config(cls, config_manager: ConfigurationManager, url: str = None, offset: int = 0, length: int = -1):
        backend_config = config_manager.get_config("cltl.backend")

        url = url if url else f"{backend_config.get('server_url')}/mic"
        storage_url = backend_config.get('storage_url')

        return cls(url, f"{storage_url}", offset, length)

    def __init__(self, url: str, storage_url: str = None, offset: int = 0, length: int = -1):
        self._url = url
        self._storage_url = storage_url
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

        session = requests.session()
        if self._storage_url:
            session.mount(f"{STORAGE_SCHEME}:", CltlAudioAdapter(self._storage_url))

        has_parameters = self._offset or self._length > 0
        url = self._url
        if has_parameters:
            params = {"offset": self._offset, "length": self._length}
            url += "?" + '&'.join(['%s=%s' % (key, value) for (key, value) in params.items()])
        self._request = session.get(url, stream=True).__enter__()
        if self._request.status_code != 200:
            code = self._request.status_code
            text = self._request.text
            self._request.close()
            self._request = None
            raise ValueError(f"Requests to {self._url} with {params} failed ({code}): {text}")


        content_type = self._request.headers['content-type'].split(CONTENT_TYPE_SEPARATOR)
        if not content_type[0].strip() == 'audio/L16' or len(content_type) != 4:
            # Only support 16bit audio for now
            self._request.close()
            self._request = None
            raise ValueError(f"Unsupported content type {content_type[0]}, "
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
        self._iter = None
        self._request.__exit__(exc_type, exc_val, exc_tb)
        self._request = None

    @property
    def content(self):
        return self._request.iter_content(self._parameters.bytes_per_frame)

    @property
    def audio(self):
        return raw_frames_to_np(self.content, self.frame_size, self.channels, self.depth)

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
