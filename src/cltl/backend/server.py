import logging
from threading import Lock

import flask
from emissor.representation.scenario import Modality
from flask import Flask, Response, stream_with_context, jsonify
from flask import g as app_context

from cltl.backend.api.camera import CameraResolution
from cltl.backend.api.serialization import BackendJSONEncoder
from cltl.backend.source.cv2_source import SystemImageSource
from cltl.backend.source.pyaudio_source import PyAudioSource

logger = logging.getLogger(__name__)


class BackendServer:
    def __init__(self, sampling_rate: int, channels: int, frame_size: int,
                 camera_resolution: CameraResolution, camera_index: int):
        self._mic = PyAudioSource(sampling_rate, channels, frame_size)
        self._camera = SystemImageSource(camera_resolution, camera_index)

        self._sampling_rate = sampling_rate
        self._channels = channels
        self._frame_size = frame_size

        self._app = None
        self._active_cam = None
        self._camera_lock = Lock()

    @property
    def app(self) -> Flask:
        if self._app is not None:
            return self._app

        self._app = Flask(__name__)
        self._app.json_encoder = BackendJSONEncoder

        @self._app.route(f"/{Modality.IMAGE.name.lower()}")
        def capture():
            mimetype_with_resolution = f"application/json; resolution={self._camera.resolution.name}"

            if flask.request.method == 'HEAD':
                return Response(200, headers={"Content-Type": mimetype_with_resolution})

            if not self._active_cam:
                return Response(404)

            image = self._capture_camera()

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
        self.start()
        self.app.run(host=host, port=port, threaded=True)
        self.stop()

    def start(self):
        with self._camera_lock:
            self._active_cam = self._camera.__enter__()

    def _capture_camera(self):
        with self._camera_lock:
            if self._active_cam:
                return self._active_cam.capture()

    def stop(self):
        with self._camera_lock:
            if self._active_cam:
                self._active_cam.__exit__(None, None, None)
                self._active_cam = None


def main():
    import argparse

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    parser = argparse.ArgumentParser(description='Backend application to serve sensor data from a host machine')
    parser.add_argument('--rate', type=int, choices=[16000, 32000, 44100],
                        default=16000, help="Sampling rate.")
    parser.add_argument('--channels', type=int, choices=[1, 2],
                        default=2, help="Number of audio channels.")
    parser.add_argument('--frame_duration', type=int, choices=[10, 20, 30],
                        default=30, help="Duration of audio frames in milliseconds.")
    parser.add_argument('--resolution', type=str, choices=[res.name for res in CameraResolution],
                        default=CameraResolution.NATIVE.name, help="Camera resolution to use.")
    parser.add_argument('--cam_index', type=int,
                        default=0, help="Camera index of the camera to use.")
    parser.add_argument('--port', type=int,
                        default=8000, help="Web server port")
    args, _ = parser.parse_known_args()

    logger.info("Starting webserver with args: %s", args)

    server = BackendServer(args.rate, args.channels, args.frame_duration * args.rate // 1000,
                           CameraResolution[args.resolution.upper()], args.cam_index)
    server.run(host="0.0.0.0", port=args.port)