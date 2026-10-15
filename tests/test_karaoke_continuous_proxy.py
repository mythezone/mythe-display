import io
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlparse

from test_faio_listen_audio_player import SERVER


class ContinuousProxyTest(unittest.TestCase):
    def handler(self, *, address="127.0.0.1", origin="http://localhost:23456"):
        handler = object.__new__(SERVER.MytheDisplayHandler)
        handler.client_address = (address, 123)
        handler.headers = {"Origin": origin, "Host": "localhost:23456"}
        handler.read_json = Mock(return_value={"baseUrl": "http://fixture", "roomId": "room", "cookies": [{"name": "fixture", "value": "test-only"}]})
        handler.proxy_faio_request = Mock()
        handler.send_error = Mock()
        return handler

    @patch.dict(os.environ, {"MYTHE_DISPLAY_ENABLE_KARAOKE_OUTPUT": "1"})
    def test_clock_query_preserves_only_finite_ping(self):
        handler = self.handler()
        handler.handle_karaoke_clock(urlparse("/faio-listen/karaoke/snapshot?ping=12.5&extra=ignored"))
        args = handler.proxy_faio_request.call_args
        self.assertEqual(args.args[1], "/music/rooms/room/karaoke/snapshot?continuous=true&ping=12.5")
        self.assertEqual(args.kwargs, {"head_only": False})
        for ping in ("nan", "inf", "bad", ""):
            handler.proxy_faio_request.reset_mock()
            handler.handle_karaoke_clock(urlparse("/faio-listen/karaoke/snapshot?ping=" + ping))
            handler.proxy_faio_request.assert_not_called()

    @patch.dict(os.environ, {"MYTHE_DISPLAY_ENABLE_KARAOKE_OUTPUT": "1"})
    def test_progress_is_only_a_bounded_observation(self):
        handler = self.handler()
        payload = {"protocol": 2, "client_id": "fixture", "report_seq": 1, "instance": "song", "transport_token": "a" * 64, "position_seconds": 42, "playback_status": "playing"}
        handler.path = "/faio-listen/playback-progress"
        body = json.dumps(payload).encode()
        handler.headers["Content-Length"] = str(len(body))
        handler.rfile = io.BytesIO(body)
        handler.do_POST()
        args = handler.proxy_faio_request.call_args
        self.assertEqual(args.args[1], "/music/rooms/room/playback-progress")
        self.assertEqual(args.kwargs["method"], "POST")
        self.assertEqual(json.loads(args.kwargs["body"]), payload)
        for invalid in ({**payload, "command": "next"}, {"command": "play"}):
            handler.proxy_faio_request.reset_mock()
            handler.rfile = io.BytesIO(json.dumps(invalid).encode())
            handler.do_POST()
            handler.proxy_faio_request.assert_not_called()
        handler.headers["Content-Length"] = "4097"
        handler.rfile = Mock()
        handler.do_POST()
        handler.rfile.read.assert_not_called()

    @patch.dict(os.environ, {"MYTHE_DISPLAY_ENABLE_KARAOKE_OUTPUT": "1"})
    def test_access_checks_precede_session_read(self):
        for address, origin in (("10.0.0.2", "http://localhost:23456"), ("127.0.0.1", "http://evil.invalid"), ("127.0.0.1", "null")):
            handler = self.handler(address=address, origin=origin)
            handler.handle_karaoke_clock(urlparse("/faio-listen/karaoke/snapshot?ping=1"))
            handler.read_json.assert_not_called()
            handler.send_error.assert_called_once_with(403, "Local output session required")
        handler = self.handler()
        with patch.dict(os.environ, {"MYTHE_DISPLAY_ENABLE_KARAOKE_OUTPUT": "0"}):
            handler.handle_karaoke_clock(urlparse("/faio-listen/karaoke/snapshot?ping=1"))
        handler.read_json.assert_not_called()

    @patch.dict(os.environ, {"MYTHE_DISPLAY_ENABLE_KARAOKE_OUTPUT": "1"})
    def test_event_mode_reaches_upstream_without_forced_rollover(self):
        handler = self.handler()
        handler.headers.update({"Upgrade": "websocket", "Sec-WebSocket-Version": "13", "Sec-WebSocket-Key": "fixture"})
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.wfile = Mock()
        handler.connection = object()
        bridge = SimpleNamespace(accept_key=Mock(return_value="accept"), connect_upstream=Mock(), relay=Mock())
        spec = SimpleNamespace(loader=SimpleNamespace(exec_module=Mock()))
        with patch.object(SERVER.importlib.util, "spec_from_file_location", return_value=spec), patch.object(SERVER.importlib.util, "module_from_spec", return_value=bridge):
            handler.handle_karaoke_websocket(urlparse("/faio-listen/karaoke/ws?client_id=fixture&mode=events"))
        self.assertEqual(bridge.connect_upstream.call_args.args[1], "/music/rooms/room/karaoke/ws?client_id=fixture&mode=events")
        self.assertIsNone(bridge.relay.call_args.kwargs["lifetime"])


if __name__ == "__main__":
    unittest.main()
