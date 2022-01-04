import argparse
import logging

from cltl.combot.infra.config.k8config import K8LocalConfigurationContainer
from cltl.combot.infra.di_container import singleton
from cltl.combot.infra.event.kombu import KombuEventBusContainer
from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

from cltl.backend.api.backend import Backend
from cltl.backend.api.microphone import Microphone
from cltl.backend.api.storage import AudioStorage
from cltl.backend.impl.cached_storage import CachedAudioStorage
from cltl.backend.impl.sync_microphone import SimpleMicrophone
from cltl.backend.source.client_source import ClientAudioSource
from cltl.backend.spi.audio import AudioSource
from cltl_service.backend.backend import BackendService
from cltl_service.backend.storage import StorageService

logger = logging.getLogger(__name__)


app = Flask(__name__)


K8LocalConfigurationContainer.load_configuration()


class ApplicationContainer(KombuEventBusContainer, K8LocalConfigurationContainer):
    @property
    @singleton
    def audio_storage(self) -> AudioStorage:
        return CachedAudioStorage.from_config(self.config_manager)

    @property
    @singleton
    def audio_source(self) -> AudioSource:
        return ClientAudioSource.from_config(self.config_manager)

    @property
    @singleton
    def microphone(self) -> Microphone:
        return SimpleMicrophone(self.audio_source)

    @property
    @singleton
    def backend_service(self) -> Backend:
        return Backend(self.microphone, self.camera, self.tts)

    @property
    @singleton
    def backend_service(self) -> BackendService:
        return BackendService(self.microphone, self.audio_storage, self.event_bus)

    @property
    @singleton
    def storage_service(self) -> StorageService:
        return StorageService(self.audio_storage)

    def start(self):
        self.storage_service.start()
        self.backend_service.start()

    def stop(self):
        self.storage_service.start()
        self.backend_service.start()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    parser = argparse.ArgumentParser(description='EMISSOR data processing')
    parser.add_argument('--rate', type=int, choices=[16000, 32000, 44100], default=16000, help="Sampling rate.")
    parser.add_argument('--channels', type=int, choices=[1, 2], default=2, help="Number of audio channels.")
    parser.add_argument('--frame_duration', type=int, choices=[10, 20, 30], default=30,
                        help="Duration of audio frames in milliseconds.")
    parser.add_argument('--port', type=int, default=8000, help="Web server port")
    args, _ = parser.parse_known_args()

    logger.info("Starting webserver with args: %s", args)

    application = ApplicationContainer()
    web_application = DispatcherMiddleware(app, {'/storage': application.storage_service.app})

    application.start()
    run_simple('0.0.0.0', 8000, web_application, threaded=True, use_reloader=True, use_debugger=True, use_evalex=True)
    application.stop()
