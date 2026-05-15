import logging

from cltl.backend.api.storage import AudioStorage, ImageStorage
from cltl.backend.impl.cached_storage import CachedAudioStorage, CachedImageStorage
from cltl.backend.impl.remote_storage import RemoteAudioStorage, RemoteImageStorage
from cltl.combot.infra.container import InfraContainer
from cltl.combot.infra.di_container import singleton
from cltl_service.backend.storage import StorageService

logger = logging.getLogger(__name__)


class StorageContainer(InfraContainer):
    """Container for audio/image storage and the HTTP storage service.

    Can be deployed standalone when a remote storage endpoint is needed without
    running the full hardware backend (microphone, camera, TTS).
    """

    @property
    @singleton
    def audio_storage(self) -> AudioStorage:
        config = self.config_manager.get_config("cltl.backend")
        storage_mode = config.get("audio_storage") if "audio_storage" in config else "local"
        if storage_mode == "remote":
            return RemoteAudioStorage.from_config(self.config_manager)
        elif storage_mode == "local":
            return CachedAudioStorage.from_config(self.config_manager)
        else:
            raise ValueError("Unknown storage mode: " + storage_mode)

    @property
    @singleton
    def image_storage(self) -> ImageStorage:
        config = self.config_manager.get_config("cltl.backend")
        storage_mode = config.get("image_storage") if "image_storage" in config else "local"
        if storage_mode == "remote":
            return RemoteImageStorage.from_config(self.config_manager)
        elif storage_mode == "local":
            return CachedImageStorage.from_config(self.config_manager)
        else:
            raise ValueError("Unknown storage mode: " + storage_mode)

    @property
    @singleton
    def storage_service(self) -> StorageService:
        return StorageService(self.audio_storage, self.image_storage)

    def start(self):
        logger.info("Start Storage")
        super().start()
        self.storage_service.start()

    def stop(self):
        logger.info("Stop Storage")
        self.storage_service.stop()
        super().stop()
