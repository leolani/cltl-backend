import logging

from flask import Flask, Response, stream_with_context
from flask import g as app_context

from cltl.backend.source.pyaudio_source import PyAudioMic

logger = logging.getLogger(__name__)


def backend_server(sampling_rate, channels, frame_size):
    app = Flask(__name__)

    @app.route('/mic')
    def stream_mic():
        mic = PyAudioMic(sampling_rate, channels, frame_size)

        def audio_stream(mic):
            with mic as mic_stream:
                yield from mic_stream

        # Store mic in (thread-local) app-context to be able to close it.
        app_context.mic = mic

        mime_type = f"audio/L16; rate={sampling_rate}; channels={channels}; frame_size={frame_size}"
        stream = stream_with_context(audio_stream(mic))

        return Response(stream, mimetype=mime_type)

    @app.after_request
    def set_cache_control(response):
      response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
      response.headers['Pragma'] = 'no-cache'
      response.headers['Expires'] = '0'

      return response

    @app.teardown_request
    def close_mic(_=None):
        if "mic" in app_context:
            app_context.mic.stop()

    return app
