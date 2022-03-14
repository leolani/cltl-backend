import json
import logging
import os.path
import pickle
from pathlib import Path
from queue import Queue, Empty
from types import SimpleNamespace
from typing import Iterable, Union

import cv2
import numpy as np
import soundfile as sf
from cachetools import LRUCache
from cltl.combot.infra.config import ConfigurationManager
from cltl.combot.infra.time_util import timestamp_now

from cltl.backend.api.camera import Image, Bounds
from cltl.backend.api.storage import AudioStorage, AudioParameters, ImageStorage

logger = logging.getLogger(__name__)


class CachedAudioStorage(AudioStorage):
    @classmethod
    def from_config(cls, config_manager: ConfigurationManager):
        backend_config = config_manager.get_config("cltl.backend")

        return cls(backend_config.get("audio_storage_path"), backend_config.get_int("audio_source_buffer"))

    def __init__(self, storage_path: str, min_buffer: int = 16):
        self._storage_path = Path(storage_path).resolve()
        self._cache = dict()
        self._cache_params = dict()
        self._min_buffer = min_buffer

    def store(self, audio_id: str, audio: Union[np.array, Iterable[np.array]], sampling_rate: int):
        if isinstance(audio, np.ndarray):
            audio = [audio]

        self._cache[audio_id] = Queue()

        for frame in audio:
            if audio_id not in self._cache_params:
                self._cache_params[audio_id] = self._audio_params(frame, sampling_rate)
            self._cache[audio_id].put(frame)

        if not self._cache[audio_id].qsize() == 0:
            self._write(audio_id, self._cache[audio_id].queue, sampling_rate)

        del self._cache[audio_id]
        if audio_id in self._cache_params:
            del self._cache_params[audio_id]

    def _audio_params(self, audio, sampling_rate):
        channels = 1 if audio.ndim == 1 else audio.shape[1]
        if audio.dtype == np.int16:
            sample_wid_th = 2
        else:
            raise ValueError("Only np.int16 is supported, was: ", audio.dtype)

        return AudioParameters(sampling_rate, channels, audio.shape[0], sample_wid_th)

    def _write(self, id_, audio, sampling_rate: int):
        if isinstance(audio, np.ndarray):
            data = audio
        else:
            data = np.concatenate(audio)

        if not data.dtype == np.int16:
            raise ValueError(f"Wrong sample depth: {data.dtype}")

        sf.write(str(self._storage_path / f"{id_}.wav"), data, sampling_rate)

        metadata = {"timestamp": timestamp_now(), "parameters": self._cache_params[id_]}
        with open(self._storage_path / f"{id_}_meta.json", 'w') as f:
            json.dump(metadata, f, default=vars)

        logger.debug("Stored audio files %s", self._storage_path / f"{id_}")

    def get(self, id_: str, offset: int = 0, length: int = -1) -> (Iterable[np.array], AudioParameters):
        try:
            parameters = self._cache_params[id_]
        except KeyError:
            parameters = AudioParameters(**vars(self._read_meta_from_file(id_).parameters))

        def audio_generator():
            try:
                yield from self._get_from_cache(id_, offset, length, parameters.frame_size)
            except _CacheKeyError as e:
                yield from self._get_from_file(id_, e.offset, length)

        return audio_generator(), parameters

    def _get_from_cache(self, id_, offset, length, frame_size):
        current_frame = offset // frame_size
        if current_frame * frame_size != offset:
            raise ValueError(f"Offsets not matching frame borders are not supported (frame_size: {frame_size})")
        cnt = 0
        buffer = Queue()

        while True:
            if length > 0 and cnt >= length:
                return

            try:
                cached = self._cache[id_]
            except KeyError:
                # Continue from file from the current offset
                raise _CacheKeyError(current_frame * frame_size)

            if cached.qsize() < current_frame:
                raise ValueError(f"Offset too large, expected {current_frame}, was {cached.qsize()}")
            if buffer.qsize() < self._min_buffer:
                pulled = list(cached.queue)[current_frame:]
                current_frame += len(pulled)
                [buffer.put(frame) for frame in pulled]

            try:
                get = buffer.get(timeout=0.01)
                cnt += frame_size
                yield get
            except Empty:
                pass

    def _get_from_file(self, id_, offset, length):
        try:
            frame_size = self._read_meta_from_file(id_).parameters.frame_size

            audio, sampling_rate = sf.read(self._storage_path / f"{id_}.wav", dtype=np.int16,
                                           frames=length, start=offset)

            stop = len(audio) if length < 0 else length
            frames = (audio[i:i + frame_size] for i in range(0, stop, frame_size))

            yield from frames
        except FileNotFoundError:
            raise KeyError(f"No audio with id {id_} found in the storage")

    def _read_meta_from_file(self, id_):
        with open(self._storage_path / f"{id_}_meta.json", 'r') as f:
            return json.load(f, object_hook=lambda d: SimpleNamespace(**d))


class _CacheKeyError(Exception):
    def __init__(self, offset):
        self.offset = offset


class CachedImageStorage(ImageStorage):
    @classmethod
    def from_config(cls, config_manager: ConfigurationManager):
        backend_config = config_manager.get_config("cltl.backend")

        return cls(backend_config.get("image_storage_path"), backend_config.get_int("image_cache"))

    def __init__(self, storage_path: str, max_buffer: int = 16):
        self._storage_path = Path(storage_path).resolve()
        self._cache = LRUCache(maxsize=max_buffer)

    def store(self, image_id: str, image: Image):
        if image_id in self._cache:
            logger.warning("Image %s was already stored", image_id)

        self._cache[image_id] = image
        self._write(image_id, image)

    def _write(self, image_id: str, image: Image):
        cv2.imwrite(str(self._storage_path / f"{image_id}.png"),
                    cv2.cvtColor(image.image, cv2.COLOR_RGB2BGR))

        with open(self._storage_path / f"{image_id}_meta.json", 'w') as f:
            json.dump({'bounds': image.bounds.to_diagonal(), 'view': image.view}, f, default=vars)

        if image.depth is not None:
            with open(self._storage_path / f"{image_id}_depth.pkl", 'wb') as f:
                pickle.dump(image.depth, f)

    def get(self, image_id: str) -> Image:
        try:
            return self._cache[image_id]
        except KeyError:
            image = self._read(image_id)
            self._cache[image_id] = image

            return image

    def _read(self, image_id: str):
        if not os.path.isfile(self._storage_path / f"{image_id}.png"):
            raise KeyError(f"No image with id {image_id} found in the storage")

        image = cv2.imread(str(self._storage_path / f"{image_id}.png"))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        with open(self._storage_path / f"{image_id}_meta.json", 'r') as f:
            view = Bounds(**json.load(f)['view'])

        depth = None
        if os.path.isfile(self._storage_path / f"{image_id}_depth.pkl"):
            with open(self._storage_path / f"{image_id}_depth.pkl", 'rb') as f:
                depth = pickle.load(f)

        return Image(image, view, depth)
