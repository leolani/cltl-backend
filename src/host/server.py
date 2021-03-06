import logging

import flask
import numpy as np
from emissor.representation.scenario import Modality
from flask import Flask, Response, stream_with_context, json, jsonify
from flask import g as app_context
from flask.json import JSONEncoder

from cltl.backend.api.camera import CameraResolution
from cltl.backend.source.cv2_source import SystemImageSource
from cltl.backend.source.pyaudio_source import PyAudioSource

logger = logging.getLogger(__name__)


# TODO move to common util in combot
class NumpyJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()

        return super().default(obj)


class BackendServer:
    def __init__(self, sampling_rate: int, channels: int, frame_size: int,
                 camera_resolution: CameraResolution, camera_index: int):
        self._mic = PyAudioSource(sampling_rate, channels, frame_size)
        self._camera = SystemImageSource(camera_resolution, camera_index)

        self._sampling_rate = sampling_rate
        self._channels = channels
        self._frame_size = frame_size

        self._app = None

    @property
    def app(self) -> Flask:
        if self._app is not None:
            return self._app

        self._app = Flask(__name__)
        self._app.json_encoder = NumpyJSONEncoder

        @self._app.route(f"/{Modality.VIDEO.name.lower()}")
        def capture():
            mimetype_with_resolution = f"application/json; resolution={self._camera.resolution.name}"

            if flask.request.method == 'HEAD':
                return Response(200, headers={"Content-Type": mimetype_with_resolution})

            with self._camera as camera:
                image = camera.capture()

            response = jsonify(image)
            response.headers["Content-Type"] = mimetype_with_resolution

            return response

        @self._app.route(f"/{Modality.AUDIO.name.lower()}")
        def stream_mic():
            def audio_stream(mic):
                with self._mic as mic_stream:
                    yield from mic_stream

            # Store mic in (thread-local) app-context to be able to close it.
            app_context.mic = self._mic

            mime_type = f"audio/L16; rate={self._sampling_rate}; channels={self._channels}; frame_size={self._frame_size}"
            stream = stream_with_context(audio_stream(self._mic))

            return Response(stream, mimetype=mime_type)

        @self._app.after_request
        def set_cache_control(response):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'

            return response

        @self._app.teardown_request
        def close_mic(_=None):
            if "mic" in app_context:
                app_context.mic.stop()

        return self._app

    def run(self, host: str, port: int):
        self.app.run(host=host, port=port)
