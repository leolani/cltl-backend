import logging

from emissor.representation.scenario import Modality
from flask import Flask, Response, stream_with_context
from flask import g as app_context
from flask import request

from cltl.backend.api.storage import AudioStorage
from cltl.backend.api.util import np_to_raw_frames


class StorageService:
    def __init__(self, storage: AudioStorage):
        self._storage = storage
        self._app = None

    def start(self):
        pass

    def stop(self):
        pass

    @property
    def app(self):
        if self._app:
            return self._app

        self._app = Flask("audio_storage")

        @self._app.route(f"/{Modality.AUDIO.name.lower()}/<id>", methods=['PUT'])
        def store_audio(id: str):
            return Response("Currently only storing audio directly from the microphone is supported", status=501)

        @self._app.route(f"/{Modality.AUDIO.name.lower()}/<id>")
        def get_audio(id: str):
            """
            Get the audio data for the requested id.

            The request can have `offset` and `length` as parameters.
            * `offset` must be the start sample of the audio
            * `length` must be the number of samples returned

            Parameters
            ----------
            id : The id of the audio data

            Returns
            -------
            Response
                Response with the audio data, eventually chunked. Contains sample rate and chunk size in the headers.
            """
            offset = request.args.get("offset", default=0, type=int)
            length = request.args.get("length", default=-1, type=int)

            audio, parameters = self._storage.get(id, offset=offset, length=length)

            # Store audio in (thread-local) app-context to be able to close it.
            app_context.audio = audio

            mime_type = f"audio/L16;" \
                        f"rate={parameters.sampling_rate};" \
                        f"channels={parameters.channels};" \
                        f"frame_size={parameters.frame_size}"

            stream = stream_with_context(np_to_raw_frames(audio))

            return self._app.response_class(stream, mimetype=mime_type)

        @self._app.after_request
        def set_cache_control(response):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'

            return response

        @self._app.teardown_request
        def close_audio(_=None):
            if "audio" in app_context:
                try:
                    app_context.audio.close()
                except:
                    pass

        return self._app