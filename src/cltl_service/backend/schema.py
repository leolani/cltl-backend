from dataclasses import dataclass
from typing import TypeVar

from cltl.combot.event.emissor import SignalStarted, SignalStopped, AudioSignalStarted
from emissor.representation.scenario import Modality, AudioSignal, Signal

from cltl.backend.api.storage import AudioParameters

S = TypeVar('S', bound=Signal)


@dataclass
class BackendAudioSignalStarted(AudioSignalStarted):
    parameters: AudioParameters

    @classmethod
    def create_backend_signal(cls, signal: AudioSignal, parameters: AudioParameters):
        return cls(AudioSignalStarted.__name__, Modality.AUDIO, signal, parameters)
