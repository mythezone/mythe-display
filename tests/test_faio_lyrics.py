import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse

from test_faio_listen_audio_player import SERVER


class LyricsTest(unittest.TestCase):
    def handler(self):
        handler = object.__new__(SERVER.MytheDisplayHandler)
        handler.read_json = Mock(return_value={
            "baseUrl": "http://fixture", "roomId": "room-a",
            "cookies": [{"name": "fixture", "value": "test-only"}],
        })
        handler.send_error = Mock()
        handler.send_json = Mock()
        return handler

    def query(self, **overrides):
        return urlparse("/faio-listen/lyrics?" + urlencode({
            "roomId": "room-a", "fileId": "song-a", "sourceType": "library", "mode": "normal", **overrides,
        }))

    def test_direct_lyrics_use_existing_session_and_shared_lrc_parser(self):
        for query, suffix in (
            ({}, "/lyrics/song-a"),
            ({"sourceType": "online", "fileId": "online_song"}, "/online/online_song/lyrics"),
            ({"mode": "karaoke"}, "/karaoke/lyrics/song-a"),
        ):
            with self.subTest(query=query):
                handler = self.handler()
                response = io.StringIO(json.dumps({"lyrics": [
                    {"content": "plain text"},
                    {"synced": True, "content": "[00:01.50]First\n[00:02.00]Second"},
                ]}))
                with patch.object(SERVER.request, "urlopen", return_value=response) as get:
                    handler.handle_faio_lyrics(self.query(**query))
                upstream = get.call_args.args[0]
                self.assertEqual(upstream.full_url, "http://fixture/music/rooms/room-a" + suffix)
                self.assertEqual(upstream.get_method(), "GET")
                self.assertEqual(upstream.get_header("Cookie"), "fixture=test-only")
                self.assertEqual(get.call_args.kwargs["timeout"], 5)
                self.assertEqual(handler.read_json.call_count, 1, "lyrics must not wait for a runtime snapshot")
                self.assertEqual(handler.send_json.call_args.args[0], {
                    "roomId": "room-a", "fileId": query.get("fileId", "song-a"),
                    "lyrics": [{"time": 1.5, "text": "First"}, {"time": 2.0, "text": "Second"}],
                })

    def test_invalid_requests_never_reach_upstream(self):
        for query in ({"fileId": "../secret"}, {"fileId": "a/b"}, {"fileId": ""},
                      {"sourceType": "external"}, {"mode": "invalid"}, {"roomId": "another-room"}):
            with self.subTest(query=query):
                handler = self.handler()
                with patch.object(SERVER.request, "urlopen") as get:
                    handler.handle_faio_lyrics(self.query(**query))
                get.assert_not_called()
                handler.send_error.assert_called_once()

    def test_absent_session_and_upstream_errors_are_reported(self):
        for failure in (FileNotFoundError(), TimeoutError(), HTTPError("http://fixture", 403, "denied", {}, None)):
            with self.subTest(failure=type(failure).__name__):
                handler = self.handler()
                with patch.object(SERVER.request, "urlopen", side_effect=failure):
                    handler.handle_faio_lyrics(self.query())
                handler.send_error.assert_called_once()
                handler.send_json.assert_not_called()
        handler = self.handler()
        handler.read_json.return_value["cookies"] = []
        with patch.object(SERVER.request, "urlopen") as get:
            handler.handle_faio_lyrics(self.query())
        get.assert_not_called()
        handler.send_error.assert_called_once_with(503, "Existing room session unavailable")

    def test_missing_or_malformed_lyrics_return_an_empty_list(self):
        for payload in ({}, {"lyrics": None}, {"lyrics": [None, "invalid"]}):
            handler = self.handler()
            with patch.object(SERVER.request, "urlopen", return_value=io.StringIO(json.dumps(payload))):
                handler.handle_faio_lyrics(self.query())
            self.assertEqual(handler.send_json.call_args.args[0]["lyrics"], [])


if __name__ == "__main__":
    unittest.main()
