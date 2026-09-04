from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import request


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "faio-listen-audio-player.py"
SPEC = importlib.util.spec_from_file_location("faio_listen_audio_player", SCRIPT)
assert SPEC and SPEC.loader
PLAYER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLAYER)

COLLECTOR_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collect-faio-listen-snapshot.py"
COLLECTOR_SPEC = importlib.util.spec_from_file_location("collect_faio_listen_snapshot", COLLECTOR_SCRIPT)
assert COLLECTOR_SPEC and COLLECTOR_SPEC.loader
COLLECTOR = importlib.util.module_from_spec(COLLECTOR_SPEC)
COLLECTOR_SPEC.loader.exec_module(COLLECTOR)

SERVER_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "serve-web-test.py"
SERVER_SPEC = importlib.util.spec_from_file_location("serve_web_test", SERVER_SCRIPT)
assert SERVER_SPEC and SERVER_SPEC.loader
SERVER = importlib.util.module_from_spec(SERVER_SPEC)
SERVER_SPEC.loader.exec_module(SERVER)


class FaioListenAudioPlayerTest(unittest.TestCase):
    def test_public_pause_blocks_only_the_output_player(self) -> None:
        snapshot = {"status": "connected", "room": {"onlineCount": 4}}
        playback = {"status": "playing", "fileId": "track-1", "revision": 8}
        self.assertTrue(PLAYER.should_play(snapshot, playback, {"playing": True}, "http://local/media"))
        self.assertFalse(PLAYER.should_play(snapshot, playback, {"playing": False}, "http://local/media"))

    def test_playback_key_ignores_unrelated_room_snapshot_changes(self) -> None:
        playback = {"fileId": "track-1", "revision": 8, "title": "Song"}
        first = PLAYER.playback_key(playback, "http://local/media", 70)
        playback["onlineCount"] = 12
        self.assertEqual(PLAYER.playback_key(playback, "http://local/media", 70), first)
        self.assertNotEqual(PLAYER.playback_key(playback, "http://local/media", 40), first)

    def test_ffmpeg_receives_bounded_volume_filter(self) -> None:
        with patch.object(PLAYER.subprocess, "Popen") as popen:
            PLAYER.start_ffmpeg(
                ffmpeg="ffmpeg",
                log_level="warning",
                source_url="http://local/media",
                position=12.5,
                alsa_device="plughw:0,3",
                volume=33,
            )
        command = popen.call_args.args[0]
        self.assertEqual(command[command.index("-af") + 1], "volume=0.33")
        self.assertEqual(command[command.index("-ss") + 1], "12.500")

    def test_resume_public_output_sends_playing_true(self) -> None:
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        with patch.object(PLAYER.request, "urlopen", return_value=response) as urlopen, patch.object(
            PLAYER.json, "load", return_value={"playing": True, "volume": 65}
        ):
            result = PLAYER.resume_public_output("http://127.0.0.1:23456", "/faio-listen/public-output")
        sent: request.Request = urlopen.call_args.args[0]
        self.assertEqual(sent.method, "PUT")
        self.assertEqual(json.loads(sent.data), {"playing": True})
        self.assertTrue(result["playing"])


class FaioOnlineMediaCompatibilityTest(unittest.TestCase):
    def test_online_playback_uses_the_faio_online_proxy(self) -> None:
        payload = COLLECTOR.normalize_snapshot(
            base_url="http://127.0.0.1:4173",
            room_url="http://127.0.0.1:4173/listen/room-1",
            room_id="room-1",
            display_name="MytheNAS Speaker",
            raw={
                "room": {"name": "Room"},
                "playback": {
                    "revision": 12,
                    "status": "playing",
                    "file_id": "online_track-1",
                    "source_type": "online",
                    "media_url": "/music/rooms/room-1/online/online_track-1/media",
                    "cover_url": "/music/rooms/room-1/online/online_track-1/cover",
                    "next_file_id": "online_track-2",
                    "next_source_type": "online",
                },
                "queue": [
                    {"file_id": "online_track-3", "source_type": "online", "title": "Queued"},
                ],
            },
            lyrics=[],
            refresh_ms=10_000,
        )
        self.assertEqual(payload["playback"]["sourceType"], "online")
        self.assertEqual(payload["playback"]["mediaUrl"], "/faio-listen/online/online_track-1/media?v=12")
        self.assertEqual(payload["playback"]["coverUrl"], "/faio-listen/online/online_track-1/cover?v=12")
        self.assertEqual(payload["playback"]["next"]["coverUrl"], "/faio-listen/online/online_track-2/cover?v=12")
        self.assertEqual(payload["queue"][0]["coverUrl"], "/faio-listen/online/online_track-3/cover?v=12")

    def test_legacy_online_id_infers_online_source(self) -> None:
        self.assertEqual(COLLECTOR.normalize_source_type("", file_id="online_abc123"), "online")
        self.assertEqual(COLLECTOR.normalize_source_type("", file_id="library123"), "library")

    def test_plain_external_track_keeps_its_direct_urls(self) -> None:
        payload = COLLECTOR.normalize_snapshot(
            base_url="http://127.0.0.1:4173",
            room_url="http://127.0.0.1:4173/listen/room-1",
            room_id="room-1",
            display_name="MytheNAS Speaker",
            raw={
                "room": {"name": "Room"},
                "playback": {
                    "revision": 2,
                    "file_id": "external-1",
                    "source_type": "external",
                    "media_url": "https://media.example.test/song.mp3",
                    "cover_url": "https://media.example.test/cover.jpg",
                },
            },
            lyrics=[],
            refresh_ms=10_000,
        )
        self.assertEqual(payload["playback"]["mediaUrl"], "https://media.example.test/song.mp3")
        self.assertEqual(payload["playback"]["coverUrl"], "https://media.example.test/cover.jpg")

    def test_online_proxy_routes_to_faio_online_endpoints(self) -> None:
        resolver = SERVER.MytheDisplayHandler.resolve_faio_upstream_path
        self.assertEqual(
            resolver(None, "/faio-listen/online/online_abc/media", {}, "room id"),
            "/music/rooms/room%20id/online/online_abc/media",
        )
        self.assertEqual(
            resolver(None, "/faio-listen/online/online_abc/cover", {}, "room id"),
            "/music/rooms/room%20id/online/online_abc/cover",
        )
        self.assertEqual(resolver(None, "/faio-listen/online/online_abc/unknown", {}, "room id"), "")

    def test_online_lyrics_use_online_endpoint(self) -> None:
        response = {"lyrics": [{"synced": True, "content": "[00:01.00]Line"}]}
        with patch.object(COLLECTOR, "read_json", return_value=response) as read_json:
            lyrics = COLLECTOR.collect_lyrics(
                object(),
                base_url="http://127.0.0.1:4173",
                room_id="room-1",
                playback={"file_id": "online_track-1", "source_type": "online"},
            )
        self.assertEqual(lyrics, [{"time": 1.0, "text": "Line"}])
        self.assertTrue(read_json.call_args.args[1].endswith("/music/rooms/room-1/online/online_track-1/lyrics"))


if __name__ == "__main__":
    unittest.main()
