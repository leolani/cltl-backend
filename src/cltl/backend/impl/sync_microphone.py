import contextlib
import logging
from typing import Iterator, Iterable

import numpy as np
from cltl.combot.infra.resource.api import ResourceManager
from cltl.combot.infra.resource.threaded import ThreadedResourceManager
from cltl.combot.infra.util import ThreadsafeBoolean

from cltl.backend.api.microphone import Microphone, AUDIO_RESOURCE_NAME, MIC_RESOURCE_NAME, AudioParameters
from cltl.backend.spi.audio import AudioSource

logger = logging.getLogger(__name__)


class SynchronizedMicrophone(Microphone):
    def __init__(self, source: AudioSource, resource_manager: ResourceManager):
        """
        A SynchronizedMicrophone can be synchronized with other audio activity.

        Parameters
        ----------
        source: AudioSource
            The source of audio data
        resource_manager : ResourceManager
            Resource manager to manage access to the microphone resource
        """
        self._log = logger.getChild(self.__class__.__name__)

        self._resource_manager = resource_manager
        self._processor_scheduler = None

        self._source = source
        # TODO
        self._timeout_interval = 0.5 * source.frame_size / source.rate if source.frame_size and source.rate else 1

        self._source_audio = None
        self._audio_lock = None
        self._mic_lock = None
        self._interrupt = ThreadsafeBoolean(False)

    def start(self):
        """
        Initiate resources for synchronization.
        """
        self._resource_manager.provide_resource(AUDIO_RESOURCE_NAME)
        self._resource_manager.provide_resource(MIC_RESOURCE_NAME)
        self._audio_lock = self._resource_manager.get_read_lock(AUDIO_RESOURCE_NAME)
        self._mic_lock = self._resource_manager.get_write_lock(MIC_RESOURCE_NAME)
        self._mic_lock.acquire()

    def stop(self):
        """
        Tear down resources for synchronization.
        """
        if self._audio_lock.locked:
            self._audio_lock.release()
        if self._mic_lock.locked:
            self._mic_lock.release()

        self._resource_manager.retract_resource(AUDIO_RESOURCE_NAME)
        self._resource_manager.retract_resource(MIC_RESOURCE_NAME)

    @property
    def parameters(self) -> AudioParameters:
        return AudioParameters(self._source.rate, self._source.channels, self._source.frame_size, self._source.depth)

    def mute(self) -> None:
        self._interrupt.value = True
        while not self.muted:
            self._try_mute()

    @property
    def muted(self) -> bool:
        return self._mic_lock.locked

    @contextlib.contextmanager
    def listen(self) -> [Iterable[np.ndarray], AudioParameters]:
        """
        Provide audio input from the microphone.

        To avoid interference with audio output we use the following strategy:

        * Mute the microphone whenever speakers are active
        * Delay speakers until listening stops

        For this we define two resources: AUDIO and MIC
        * Mic and speaker share a Reader-Writer Lock for AUDIO
        * Listeners and mic share a Reader-Writer lock MIC

        and use the following locking strategy:

        * Speaker acquires the AUDIO Writer-lock, signaling interrupt to the AUDIO Reader-lock of the mic
        * Mic acquires the AUDIO Reader-lock, checking for interruption when speakers are not active,
            * if interrupted, mic tries to obtain the MIC write lock (wait for listening to end)
            * when MIC Writer-lock is obtained the mic releases the AUDIO Reader-lock and acquires it again
              (speaker is active, mic is waiting to listen again)
            * when the AUDIO Reader-lock is acquired, it releases the MIC Writer-lock
              (speaker ends, listening starts again)
        """
        while self.muted:
            self._try_unmute()

        with self._source as audio:
            yield self._get_audio(audio), self.parameters

        self._try_mute()

    def _get_audio(self, audio) -> Iterator[np.array]:
        frame = False
        audio_frames = iter(audio)
        while frame is not None:
            if self._audio_lock.interrupted or self._interrupt.value:
                self._try_mute()

            if not self.muted:
                frame = self._next_frame(audio_frames)
                yield frame
            else:
                yield None
                return

    def _next_frame(self, audio):
        try:
            return next(audio)
        except StopIteration:
            logger.warning("AudioSource stopped iteration without sentinel value")
            return None

    def _try_unmute(self):
        logger.debug("Try to unmute microphone (lock interrupted: %s, interrupted: %s)", self._audio_lock.interrupted, self._interrupt.value)
        if self._audio_lock.acquire(blocking=True, timeout=self._timeout_interval):
            self._audio_lock.interrupt_writers(False)
            if self._mic_lock.locked:
                self._mic_lock.release()

            self._interrupt.value = False

            logger.info("Microphone unmuted")

            return True

        self._audio_lock.interrupt_writers()

        return False

    def _try_mute(self):
        logger.debug("Try to mute microphone (lock interrupted: %s, interrupted: %s)", self._audio_lock.interrupted, self._interrupt.value)
        if self._mic_lock.acquire(blocking=True, timeout=self._timeout_interval):
            self._mic_lock.interrupt_readers(False)
            if self._audio_lock.locked:
                self._audio_lock.release()
            self._interrupt.value = False

            logger.info("Microphone muted")

            return True

        self._mic_lock.interrupt_readers()

        return False


class SimpleMicrophone(SynchronizedMicrophone):
    def __init__(self, source: AudioSource):
        super().__init__(source, ThreadedResourceManager())
