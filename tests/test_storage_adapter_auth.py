import unittest
from unittest import mock

import requests

from cltl.backend.api.storage import STORAGE_SCHEME
from cltl.backend.source.client_source import CltlAudioAdapter


class CltlAudioAdapterAuthTest(unittest.TestCase):
    def _send(self, storage_url):
        adapter = CltlAudioAdapter(storage_url)
        request = requests.Request("GET", f"{STORAGE_SCHEME}:audio/a1").prepare()
        with mock.patch.object(adapter._http_adapter, "send") as send:
            adapter.send(request)

        return send.call_args.args[0]

    def test_userinfo_becomes_basic_auth_header(self):
        sent = self._send("https://cltl:s%40cret@server.example.org/storage/")

        self.assertEqual("https://server.example.org/storage/audio/a1", sent.url)
        self.assertEqual(requests.auth._basic_auth_str("cltl", "s@cret"), sent.headers["Authorization"])

    def test_port_is_kept(self):
        sent = self._send("http://u:p@localhost:8001/storage/")

        self.assertEqual("http://localhost:8001/storage/audio/a1", sent.url)

    def test_no_userinfo_no_header(self):
        sent = self._send("http://localhost:8001/storage/")

        self.assertEqual("http://localhost:8001/storage/audio/a1", sent.url)
        self.assertNotIn("Authorization", sent.headers)
