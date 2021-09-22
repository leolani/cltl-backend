from dataclasses import dataclass

from emissor.representation.scenario import Modality

from cltl.backend.api.storage import AudioParameters


@dataclass
class SignalEvent:
    type: str
    signal_id: str
    timestamp: float
    modality: Modality


@dataclass
class SignalStarted(SignalEvent):
    pass


@dataclass
class SignalStopped(SignalEvent):
    pass


@dataclass
class AudioSignalStarted(SignalStarted):
    parameters: AudioParameters

    @classmethod
    def create(cls, audio_id: str, timestamp: float, parameters: AudioParameters):
        return cls(cls.__name__, audio_id, timestamp, Modality.AUDIO, parameters)


@dataclass
class AudioSignalStopped(SignalStopped):
    length: int

    @classmethod
    def create(cls, audio_id: str, timestamp: float, length: int):
        return cls(cls.__name__, audio_id, timestamp, Modality.AUDIO, length)
