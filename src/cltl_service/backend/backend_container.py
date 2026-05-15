import logging

from cltl.backend.api.backend import Backend
from cltl.backend.api.camera import CameraResolution, Camera
from cltl.backend.api.microphone import Microphone
from cltl.backend.api.text_to_speech import TextToSpeech
from cltl.backend.impl.sync_microphone import SynchronizedMicrophone
from cltl.backend.impl.sync_tts import SynchronizedTextToSpeech, TextOutputTTS
from cltl.backend.server import BackendServer
from cltl.backend.source.client_source import ClientAudioSource
from cltl.backend.source.console_source import ConsoleOutput
from cltl.backend.source.remote_tts import AnimatedRemoteTextOutput
from cltl.backend.spi.audio import AudioSource
from cltl.backend.spi.image import ImageSource
from cltl.backend.spi.text import TextOutput
from cltl.combot.infra.di_container import singleton
from cltl_service.backend.backend import BackendService
from cltl_service.backend.storage_container import StorageContainer
from flask import Flask
from typing import Optional

logger = logging.getLogger(__name__)


class BackendContainer(StorageContainer):
    """Container for the full hardware backend: microphone, camera, TTS, and backend service.

    Extends ``StorageContainer`` so both storage and hardware I/O can be started together,
    or ``StorageContainer`` can be deployed standalone in remote-storage configurations.
    """

    @property
    @singleton
    def audio_source(self) -> AudioSource:
        return ClientAudioSource.from_config(self.config_manager)

    @property
    @singleton
    def image_source(self) -> ImageSource:
        return []

    @property
    @singleton
    def text_output(self) -> TextOutput:
        config = self.config_manager.get_config("cltl.backend.text_output")
        remote_url = config.get("remote_url")
        gestures = config.get("gestures", multi=True) if "gestures" in config else None
        if remote_url:
            return AnimatedRemoteTextOutput(remote_url, gestures)
        else:
            return ConsoleOutput()

    @property
    @singleton
    def microphone(self) -> Microphone:
        return SynchronizedMicrophone(self.audio_source, self.resource_manager)

    @property
    @singleton
    def camera(self) -> Camera:
        return []

    @property
    @singleton
    def tts(self) -> TextToSpeech:
        return SynchronizedTextToSpeech(TextOutputTTS(self.text_output), self.resource_manager)

    @property
    @singleton
    def backend(self) -> Backend:
        return Backend(self.microphone, self.camera, self.tts)

    @property
    @singleton
    def backend_service(self) -> BackendService:
        return BackendService.from_config(self.backend, self.audio_storage, self.image_storage,
                                          self.event_bus, self.resource_manager, self.config_manager)

    @property
    @singleton
    def server(self) -> Optional[Flask]:
        if not self.config_manager.get_config('cltl.backend').get_boolean("run_server"):
            return None

        audio_config = self.config_manager.get_config('cltl.audio')
        video_config = self.config_manager.get_config('cltl.video')

        return BackendServer(audio_config.get_int('sampling_rate'), audio_config.get_int('channels'),
                             audio_config.get_int('frame_size'),
                             video_config.get_enum('resolution', CameraResolution),
                             video_config.get_int('camera_index'))

    def start(self):
        logger.info("Start Backend")
        super().start()
        if self.server:
            self.server.start()
        self.backend_service.start()

    def stop(self):
        logger.info("Stop Backend")
        self.backend_service.stop()
        if self.server:
            self.server.stop()
        super().stop()
