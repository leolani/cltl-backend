"""The image route's status codes, and the client that reads them back.

Two bugs lived here, both on the ``run_server: True`` hardware path and both
invisible to anything that only captures images: ``Response`` takes the *body*
as its first positional argument, so ``Response(200)`` and ``Response(404)``
sent the number as the payload with an implicit 200 status. The HEAD branch is
the one that matters — ``ClientImageSource._query_resolution`` reads the
resolution out of that response's ``Content-Type``, and a 404 that answers 200
tells a caller the camera is live when it is not.

``BackendServer.__init__`` builds a ``PyAudioSource`` and a ``SystemImageSource``
outright, so it wants a sound device, a camera and cv2. None of that is needed
to exercise the routing, so these tests construct the instance through
``__new__`` and fill in only the attributes ``app`` touches. That keeps the test
runnable in the same container as the rest of the suite.
"""
import unittest

import numpy as np

from cltl.backend.api.camera import CameraResolution, Image
from cltl.backend.server import BackendServer

VIEW = (-0.55, 0.55, 0.0, 1.0)


class _StubCamera:
    """Just the surface ``BackendServer.app`` reaches: a resolution and a frame."""

    def __init__(self, resolution=CameraResolution.QQVGA):
        self.resolution = resolution
        self.image = Image(np.zeros((resolution.height, resolution.width, 3), np.uint8), VIEW)

    def capture(self):
        return self.image


def _server(active: bool = True) -> BackendServer:
    """A BackendServer with its hardware left unbuilt.

    ``__new__`` rather than ``__init__``: the real constructor opens a
    microphone and a camera, and the routes under test touch neither.
    """
    from threading import Lock

    server = BackendServer.__new__(BackendServer)
    camera = _StubCamera()

    server._camera = camera
    server._active_cam = camera if active else None
    server._app = None
    server._camera_lock = Lock()
    server._speaker_lock = Lock()

    return server


class TestImageRouteStatus(unittest.TestCase):
    def setUp(self):
        self.resolution = CameraResolution.QQVGA

    def test_head_reports_the_resolution_with_a_200(self):
        """What ClientImageSource._query_resolution parses.

        The status has to be 200 *and* the body empty — a HEAD that answered
        with a payload would be malformed, and one that answered a non-200
        would make the client raise instead of reading the header.
        """
        client = _server().app.test_client()

        response = client.head("/image")

        self.assertEqual(200, response.status_code)
        self.assertEqual(b"", response.get_data())
        self.assertIn(f"resolution={self.resolution.name}",
                      response.headers["Content-Type"])

    def test_capture_without_an_active_camera_is_a_404(self):
        """The regression: this used to answer 200 with b'404' as the body.

        A caller checking the status saw success and then failed to parse the
        number as an image, which is a much harder failure to read than a 404.
        """
        client = _server(active=False).app.test_client()

        response = client.get("/image")

        self.assertEqual(404, response.status_code)

    def test_capture_serves_the_frame_when_the_camera_is_active(self):
        """The happy path still works — the fix touched only the guards."""
        client = _server().app.test_client()

        response = client.get("/image")

        self.assertEqual(200, response.status_code)
        self.assertIn(f"resolution={self.resolution.name}",
                      response.headers["Content-Type"])
        self.assertIn("image", response.get_json())


class TestQueryResolution(unittest.TestCase):
    """The client half, read back off the real route.

    Covers the two fixes together: the HEAD response is well-formed, and
    ``__exit__`` closes the session without passing itself as an extra
    positional argument.
    """

    def test_client_reads_the_resolution_off_a_head_request(self):
        import threading

        from werkzeug.serving import make_server

        from cltl.backend.source.client_source import ClientImageSource

        server = make_server("127.0.0.1", 0, _server().app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            with ClientImageSource(f"http://{host}:{port}/image") as source:
                self.assertEqual(CameraResolution.QQVGA, source.resolution)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_exit_closes_the_session_cleanly(self):
        """``requests.Session.__exit__`` is ``(self, *args)``, so the stray
        ``self`` was absorbed rather than raising — but it was still being
        passed as ``exc_type``. Assert the session is released either way."""
        from cltl.backend.source.client_source import ClientImageSource

        source = ClientImageSource("http://127.0.0.1:1/image")
        source.__enter__()
        self.assertIsNotNone(source._session)

        source.__exit__(None, None, None)

        self.assertIsNone(source._session)


if __name__ == "__main__":
    unittest.main()
