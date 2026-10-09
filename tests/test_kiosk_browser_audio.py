from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class KioskBrowserAudioTest(unittest.TestCase):
    def run_kiosk(self, pulse: str | None, *, enabled: bool = True) -> tuple[subprocess.CompletedProcess, dict, dict]:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            binaries = fixture / "bin"
            binaries.mkdir()
            for name in ("bash", "dirname", "id", "install", "mkdir", "date", "sleep", "cat"):
                (binaries / name).symlink_to(shutil.which(name))

            def executable(name: str, code: str) -> Path:
                target = binaries / name
                target.write_text(f"#!{sys.executable}\n" + code)
                target.chmod(0o755)
                return target

            executable("python3", "import time\ntime.sleep(30)\n")
            executable("dbus-run-session", "import os, sys\na=sys.argv[1:]\na=a[1:] if a[0]=='--' else a\nos.execvp(a[0], a)\n")
            executable("cage", "import os, sys\na=sys.argv[1:]\na=a[a.index('--')+1:]\nos.execvp(a[0], a)\n")
            browser = executable("browser", "import json, os, sys\nfrom pathlib import Path\n"
                "Path(os.environ['BROWSER_RESULT']).write_text(json.dumps({'args':sys.argv[1:],"
                "'server':os.environ.get('PULSE_SERVER'),'sink':os.environ.get('PULSE_SINK')}))\n")
            if pulse is not None:
                executable("pulseaudio", pulse)
            environment = os.environ.copy()
            for name in ("PULSE_SERVER", "PULSE_SINK"):
                environment.pop(name, None)
            environment.update({
                "PATH": str(binaries), "XDG_RUNTIME_DIR": str(fixture),
                "MYTHE_DISPLAY_BROWSER": str(browser),
                "MYTHE_DISPLAY_BROWSER_PROFILE": str(fixture / "profile"),
                "MYTHE_DISPLAY_ALLOW_REMOTE_KIOSK": "1", "MYTHE_DISPLAY_SKIP_GROUP_CHECK": "1",
                "MYTHE_DISPLAY_WAIT_FOR_DRM_READY": "0", "MYTHE_DISPLAY_DRM_DEVICE": str(browser),
                "MYTHE_DISPLAY_DRM_DEVICE_STRICT": "1", "MYTHE_DISPLAY_DISABLE_RUNTIME_COLLECTOR": "1",
                "MYTHE_DISPLAY_DISABLE_FAIO_LISTEN": "0", "MYTHE_DISPLAY_DISABLE_FAIO_AUDIO_PLAYER": "0",
                "MYTHE_DISPLAY_ENABLE_KARAOKE_OUTPUT": "1" if enabled else "0",
                "MYTHE_DISPLAY_ALSA_OUTPUT_DEVICE": "plughw:0,3",
                "MYTHE_DISPLAY_FAIO_BROWSER_AUDIO": "0",
                "BROWSER_RESULT": str(fixture / "browser.json"), "PULSE_RESULT": str(fixture / "pulse.json"),
            })
            result = subprocess.run(["/bin/bash", str(ROOT / "scripts/run-kiosk-web-test.sh")],
                cwd=ROOT, env=environment, text=True, capture_output=True, timeout=12)
            def read(name: str) -> dict:
                target = fixture / name
                return json.loads(target.read_text()) if target.exists() else {}
            return result, read("browser.json"), read("pulse.json")

    def test_karaoke_routes_browser_audio_to_hdmi_and_cleans_up(self) -> None:
        result, browser, pulse = self.run_kiosk(
            "import json, os, signal, socket, sys, time\nfrom pathlib import Path\n"
            "result=Path(os.environ['PULSE_RESULT'])\n"
            "result.write_text(json.dumps({'args':sys.argv[1:],'stopped':False}))\n"
            "def stop(*args):\n data=json.loads(result.read_text());data['stopped']=True\n"
            " result.write_text(json.dumps(data));sys.exit(0)\n"
            "signal.signal(signal.SIGTERM,stop)\n"
            "sock=socket.socket(socket.AF_UNIX);sock.bind(os.environ['PULSE_SERVER'][5:]);sock.listen()\n"
            "while True: time.sleep(1)\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(browser["server"].endswith("/pulse/native"))
        self.assertEqual(browser["sink"], "mythe_display")
        self.assertIn("module-alsa-sink device=plughw:0,3 sink_name=mythe_display rate=48000 channels=2 format=s16le", pulse["args"])
        self.assertIn("--fail=yes", pulse["args"])
        self.assertTrue(pulse["stopped"], "Owned audio service must stop with the kiosk")

    def test_missing_audio_service_explains_installation_before_browser_launch(self) -> None:
        result, browser, _ = self.run_kiosk(None)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("apt-get install --no-install-recommends pulseaudio", result.stderr)
        self.assertFalse(browser)

    def test_failed_hdmi_sink_does_not_launch_a_silent_browser(self) -> None:
        result, browser, _ = self.run_kiosk("import sys\nsys.exit(1)\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HDMI 音频服务启动失败", result.stderr)
        self.assertFalse(browser)

    def test_default_alsa_playback_needs_no_browser_audio_service(self) -> None:
        result, browser, _ = self.run_kiosk(None, enabled=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(browser["server"])
        self.assertIn("browserAudio=0", browser["args"][1])
        self.assertNotIn("karaokeAudio", browser["args"][1])


if __name__ == "__main__":
    unittest.main()
