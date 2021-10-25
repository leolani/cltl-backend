from typing import Iterable

import numpy as np


def raw_frames_to_np(audio: Iterable[bytes], frame_size: int, channels: int, sample_depth: int) -> Iterable[np.ndarray]:
    if sample_depth == 2:
        dtype = np.int16
    else:
        raise ValueError("Only sample_width of 2 is supported")

    return (np.frombuffer(frame, dtype).reshape((frame_size, channels)) for frame in audio)


def np_to_raw_frames(audio: Iterable[np.array]) -> Iterable[bytes]:
    return (frame.tobytes() for frame in audio)


def bytes_per_frame(frame_size: int, channels: int, sample_depth: int) -> int:
    return frame_size * channels * sample_depth
