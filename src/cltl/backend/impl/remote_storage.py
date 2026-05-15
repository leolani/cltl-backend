import itertools
import json
import logging
from typing import Iterable, Union

import numpy as np
import requests
from cltl.combot.infra.config import ConfigurationManager

from cltl.backend.api.camera import Image
from cltl.backend.api.microphone import AudioParameters
from cltl.backend.api.serialization import BackendJSONEncoder, image_hook
from cltl.backend.api.storage import AudioStorage, ImageStorage
from cltl.backend.api.util import bytes_per_frame, np_to_raw_frames, raw_frames_to_np

logger = logging.getLogger(__name__)

_CONTENT_TYPE_SEPARATOR = ";"
_AUDIO_MIME_TYPE = "audio/L16"


class RemoteAudioStorage(AudioStorage):
    """AudioStorage that proxies store/get operations to a remote StorageService over HTTP."""

    @classmethod
    def from_config(cls, config_manager: ConfigurationManager) -> "RemoteAudioStorage":
        config = config_manager.get_config("cltl.backend.remote_storage")
        return cls(config.get("storage_url"), config.get_float("upload_timeout", fallback=30.0))

    def __init__(self, storage_url: str, upload_timeout: float = 30.0):
        self._storage_url = storage_url.rstrip("/")
        self._upload_timeout = upload_timeout

    def store(self, audio_id: str, audio: Union[np.ndarray, Iterable[np.ndarray]], sampling_rate: int):
        frames = [audio] if isinstance(audio, np.ndarray) else audio
        frame_iterator = iter(frames)

        first_frame = next(frame_iterator, None)
        if first_frame is None:
            logger.warning("store() called with empty audio for id %s, nothing to upload", audio_id)
            return

        parameters = self._parameters_from_frame(first_frame, sampling_rate)
        all_frames = itertools.chain([first_frame], frame_iterator)

        url = f"{self._storage_url}/audio/{audio_id}"
        content_type = self._build_content_type(parameters)

        logger.debug("Uploading audio %s to %s", audio_id, url)
        response = requests.put(
            url,
            data=np_to_raw_frames(all_frames),
            headers={"Content-Type": content_type},
            timeout=(self._upload_timeout, None),
            stream=True,
        )

        if not response.ok:
            raise IOError(
                f"Failed to store audio {audio_id} at {url}: {response.status_code} {response.text}"
            )

        logger.debug("Uploaded audio %s", audio_id)

    def get(self, audio_id: str, offset: int = 0, length: int = -1) -> (Iterable[np.ndarray], AudioParameters):
        url = f"{self._storage_url}/audio/{audio_id}"
        params = {"offset": offset, "length": length}

        response = requests.get(url, params=params, stream=True, timeout=(self._upload_timeout, None))
        if not response.ok:
            raise KeyError(f"No audio with id {audio_id} found at {url}: {response.status_code}")

        parameters = self._parse_content_type(response.headers.get("Content-Type", ""), url)
        chunk_size = bytes_per_frame(parameters.frame_size, parameters.channels, parameters.sample_width)
        frames = raw_frames_to_np(response.iter_content(chunk_size), parameters.frame_size,
                                  parameters.channels, parameters.sample_width)

        return frames, parameters

    def _parameters_from_frame(self, frame: np.ndarray, sampling_rate: int) -> AudioParameters:
        if frame.dtype != np.int16:
            raise ValueError(f"Only np.int16 is supported, was: {frame.dtype}")
        channels = 1 if frame.ndim == 1 else frame.shape[1]
        return AudioParameters(sampling_rate, channels, frame.shape[0], sample_width=2)

    def _build_content_type(self, parameters: AudioParameters) -> str:
        return (
            f"{_AUDIO_MIME_TYPE}"
            f"{_CONTENT_TYPE_SEPARATOR} rate={parameters.sampling_rate}"
            f"{_CONTENT_TYPE_SEPARATOR} channels={parameters.channels}"
            f"{_CONTENT_TYPE_SEPARATOR} frame_size={parameters.frame_size}"
        )

    def _parse_content_type(self, content_type: str, url: str) -> AudioParameters:
        parts = [p.strip() for p in content_type.split(_CONTENT_TYPE_SEPARATOR)]
        if parts[0] != _AUDIO_MIME_TYPE or len(parts) != 4:
            raise ValueError(
                f"Unsupported content type from {url}: '{content_type}', "
                f"expected '{_AUDIO_MIME_TYPE}' with rate, channels, frame_size"
            )
        params = {key.strip(): int(value.strip()) for key, value in (p.split("=") for p in parts[1:])}
        return AudioParameters(
            sampling_rate=params["rate"],
            channels=params["channels"],
            frame_size=params["frame_size"],
            sample_width=2,
        )


class RemoteImageStorage(ImageStorage):
    """ImageStorage that proxies store/get operations to a remote StorageService over HTTP."""

    @classmethod
    def from_config(cls, config_manager: ConfigurationManager) -> "RemoteImageStorage":
        config = config_manager.get_config("cltl.backend.remote_storage")
        return cls(config.get("storage_url"), config.get_float("upload_timeout", fallback=30.0))

    def __init__(self, storage_url: str, upload_timeout: float = 30.0):
        self._storage_url = storage_url.rstrip("/")
        self._upload_timeout = upload_timeout

    def store(self, image_id: str, image: Image):
        url = f"{self._storage_url}/image/{image_id}"
        content_type = f"application/json; resolution={image.resolution.name}"
        body = json.dumps(image, cls=BackendJSONEncoder)

        logger.debug("Uploading image %s to %s", image_id, url)
        response = requests.put(
            url,
            data=body,
            headers={"Content-Type": content_type},
            timeout=(self._upload_timeout, None),
        )

        if not response.ok:
            raise IOError(
                f"Failed to store image {image_id} at {url}: {response.status_code} {response.text}"
            )

        logger.debug("Uploaded image %s", image_id)

    def get(self, image_id: str) -> Image:
        url = f"{self._storage_url}/image/{image_id}"

        response = requests.get(url, timeout=(self._upload_timeout, None))
        if not response.ok:
            raise KeyError(f"No image with id {image_id} found at {url}: {response.status_code}")

        return image_hook(response.json())
