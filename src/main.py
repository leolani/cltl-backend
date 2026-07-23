import logging.config
import os

from cltl.combot.event.emissor import SIG, MEN
from cltl.combot.infra.config.k8config import K8LocalConfigurationContainer
from cltl.combot.infra.di_container import singleton
from cltl.combot.infra.event.api import Event, PAYLOAD
from cltl.combot.infra.event_log import LogWriter
from cltl.combot.infra.event.memory import SynchronousEventBus
from cltl_service.backend.backend_container import BackendContainer
from cltl_service.combot.event_log.service import EventLogService
from emissor.representation.util import marshal, unmarshal, register_type_var, serializer as emissor_serializer
from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

logging.config.fileConfig(os.environ.get('CLTL_LOGGING_CONFIG', 'config/logging.config'),
                          disable_existing_loggers=False)
logger = logging.getLogger(__name__)

register_type_var(PAYLOAD)
register_type_var(SIG)
register_type_var(MEN)


def serializer(obj):
    return marshal(obj, cls=Event)


def deserializer(obj):
    return unmarshal(obj, cls=Event)


class ApplicationContainer(BackendContainer):
    @property
    @singleton
    def event_bus_serializer(self):
        return serializer, deserializer

    @property
    @singleton
    def event_bus(self):
        config = self.config_manager.get_config("cltl.event")
        if config.get("implementation") == "internal":
            return SynchronousEventBus()
        return super().event_bus

    @property
    @singleton
    def log_writer(self) -> LogWriter:
        config = self.config_manager.get_config("cltl.event")
        if "log_dir" in config:
            return LogWriter(config.get("log_dir"), emissor_serializer)

        return False

    @property
    @singleton
    def event_log_service(self) -> EventLogService:
        if self.log_writer:
            return EventLogService.from_config(self.log_writer, self.event_bus, self.config_manager)

        return False

    def start(self):
        logger.info("Start Backend")
        if self.event_log_service:
            self.event_log_service.start()
        super().start()

    def stop(self):
        logger.info("Stop Backend")

        try:
            if hasattr(self.event_bus, 'close'):
                self.event_bus.close()
            if self.event_log_service:
                self.event_log_service.stop()
        finally:
            super().stop()



def main():
    K8LocalConfigurationContainer.load_configuration()
    application = ApplicationContainer()

    with application:
        flask_app = Flask(__name__)

        @flask_app.route('/health')
        def health():
            return 'OK', 200

        routes = {'/storage': application.storage_service.app}
        if application.server:
            routes['/host'] = application.server.app

        web_app = DispatcherMiddleware(flask_app, routes)
        run_simple('0.0.0.0', 8000, web_app, threaded=True, use_reloader=False, use_debugger=False)


if __name__ == '__main__':
    main()
