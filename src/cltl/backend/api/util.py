import logging
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Iterable

import numpy as np
import requests

logger = logging.getLogger(__name__)


CONTENT_TYPE_SEPARATOR = ';'


def raw_frames_to_np(audio: Iterable[bytes], frame_size: int, channels: int, sample_depth: int):
    if sample_depth == 2:
        type = np.int16
    else:
        raise ValueError("Only sample_width of 2 is supported")

    return (np.frombuffer(frame, type).reshape((frame_size, channels)) for frame in audio)


def np_to_raw_frames(audio: Iterable[np.array]):
    return (frame.tobytes() for frame in audio)


def bytes_per_frame(frame_size: int, channels: int, sample_depth: int):
    return frame_size * channels * sample_depth
