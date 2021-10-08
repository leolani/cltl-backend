from dataclasses import dataclass
from typing import List

from emissor.representation.scenario import Modality

from cltl.backend.api.storage import AudioParameters


@dataclass
class SignalEvent:
    type: str
    signal_id: str
    timestamp: float
    modality: Modality
    files: List[str]


@dataclass
class SignalStarted(SignalEvent):
    pass


@dataclass
class SignalStopped(SignalEvent):
    pass


@dataclass
class TextSignalEvent(SignalEvent):
    text: str

    @classmethod
    def create(cls, signal_id: str, timestamp: float, text: str, files: List[str] = []):
        return cls(cls.__name__, signal_id, timestamp, Modality.TEXT, files, text)


@dataclass
class AudioSignalStarted(SignalStarted):
    parameters: AudioParameters

    @classmethod
    def create(cls, signal_id: str, timestamp: float, files: List[str], parameters: AudioParameters):
        return cls(cls.__name__, signal_id, timestamp, Modality.AUDIO, files, parameters)


@dataclass
class AudioSignalStopped(SignalStopped):
    length: int

    @classmethod
    def create(cls, signal_id: str, timestamp: float, length: int):
        return cls(cls.__name__, signal_id, timestamp, Modality.AUDIO, None, length)
