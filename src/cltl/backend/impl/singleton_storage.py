import json
import numpy as np
import soundfile as sf
import time
from pathlib import Path
from queue import Queue, Empty
from typing import Iterable, List, Union


class CachedAudioStorage:
    def __init__(self, storage_path: str, min_buffer: int = 16):
        self._storage_path = Path(storage_path)
        self._cache = dict()
        self._min_buffer = min_buffer

    def store(self, id: str, audio: Union[np.array, List[np.array]], sampling_rate: int):
        if isinstance(audio, np.ndarray):
            audio = [audio]

        self._cache[id] = Queue()
        for frame in audio:
            self._cache[id].put(frame)

        if not self._cache[id].qsize() == 0:
            self._write(id, self._cache[id].queue, sampling_rate)
        del self._cache[id]

    def _write(self, id, audio, sampling_rate: int):
        if isinstance(audio, np.ndarray):
            data = audio
        else:
            data = np.concatenate(audio)

        if not data.dtype == np.int16:
            raise ValueError(f"Wrong sample depth: {data.dtype}")

        sf.write(str(self._storage_path / f"{id}.wav"), data, sampling_rate)

        metadata = {"timestamp": time.time(), "frame_size": audio[0].shape[0]}
        with open(self._storage_path / f"{id}_meta.json", 'w') as f:
            json.dump(metadata, f)

    def get(self, id: str, offset: int = 0, length: int = -1) -> Iterable[np.array]:
        try:
            yield from self._get_from_cache(id, offset, length)
        except _CacheKeyError as e:
            yield from self._get_from_file(id, e.offset, length)

    def _get_from_cache(self, id, offset, length):
        current_offset = offset
        cnt = -1
        buffer = Queue()

        while True:
            try:
                cached = self._cache[id]
            except KeyError:
                # Continue from file from the current offset
                raise _CacheKeyError(current_offset)

            if cached.qsize() < current_offset:
                raise ValueError(f"Offset too large, expected {current_offset}, was {cached.qsize()}")
            if buffer.qsize() < self._min_buffer:
                pulled = list(cached.queue)[current_offset:]
                current_offset += len(pulled)
                [buffer.put(frame) for frame in pulled]

            try:
                get = buffer.get(timeout=0.01)
                cnt += 1
                yield get
            except Empty:
                pass

    def _get_from_file(self, id, offset, length):
        try:
            with open(self._storage_path / f"{id}_meta.json", 'r') as f:
                metadata = json.load(f)
                frame_size = metadata['frame_size']

            raw_offset = offset * frame_size
            raw_length = length * frame_size

            audio, sampling_rate = sf.read(self._storage_path / f"{id}.wav", dtype=np.int16,
                                           frames=raw_length, start=raw_offset)

            stop = len(audio) if length < 0 else raw_length
            frames = (audio[i:i + frame_size] for i in range(0, stop, frame_size))

            yield from frames
        except FileNotFoundError:
            raise KeyError(f"id {id} not found in the storage")


class _CacheKeyError(Exception):
    def __init__(self, offset):
        self.offset = offset
