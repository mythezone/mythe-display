import importlib.util
import json
import os
from pathlib import Path
import tempfile
import textwrap
import time
from types import SimpleNamespace
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("codex_agents", Path(__file__).resolve().parents[1] / "scripts/collect-codex-agents-snapshot.py")
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)
ACCOUNT = {"type": "chatgpt", "planType": "pro", "email": "private@example.test", "accessToken": "DO_NOT_EXPORT"}
WEEK = {"usedPercent": 42, "windowDurationMins": 10080, "resetsAt": 1900000000}


class WeeklyUsageTests(unittest.TestCase):
    def test_week_can_be_either_window(self):
        for name in ("primary", "secondary"):
            result = collector.normalize_usage(ACCOUNT, {"rateLimits": {name: WEEK}})
            self.assertTrue(result["available"])
            self.assertEqual(result["usedPercent"], 42)
            self.assertEqual(result["windowMinutes"], 10080)
            self.assertNotIn("DO_NOT_EXPORT", json.dumps(result))
            self.assertNotIn("private@example.test", json.dumps(result))

    def test_codex_bucket_takes_precedence(self):
        limits = {"rateLimits": {"primary": {**WEEK, "usedPercent": 99}}, "rateLimitsByLimitId": {
            "codex_other": {"primary": {**WEEK, "usedPercent": 90}},
            "codex": {"primary": {**WEEK, "usedPercent": 12.5}}}}
        self.assertEqual(collector.normalize_usage(ACCOUNT, limits)["usedPercent"], 12.5)
        self.assertFalse(collector.normalize_usage(ACCOUNT, {"rateLimits": {"limitId": "codex_other", "primary": WEEK}})["available"])

    def test_unknown_short_and_malformed_windows_are_unavailable(self):
        for data in ({}, {"rateLimits": []}, {"rateLimits": {"primary": [1]}},
                     {"rateLimits": {"primary": {**WEEK, "windowDurationMins": 300}}}):
            self.assertFalse(collector.normalize_usage(ACCOUNT, data)["available"])
        for percent in (None, "42", True, float("nan"), float("inf"), -1, 101):
            self.assertFalse(collector.normalize_usage(ACCOUNT, {"rateLimits": {"primary": {**WEEK, "usedPercent": percent}}})["available"])
        for reset in (None, True, float("inf"), -1, 253402300800):
            self.assertFalse(collector.normalize_usage(ACCOUNT, {"rateLimits": {"primary": {**WEEK, "resetsAt": reset}}})["available"])

    def test_api_keys_do_not_claim_chatgpt_quota(self):
        self.assertEqual(collector.normalize_usage({"type": "apiKey"}, {})["status"], "not-signed-in")
        self.assertFalse(collector.normalize_usage(None, None)["available"])
        result = collector.normalize_usage({**ACCOUNT, "planType": "private@example.test"}, {"rateLimits": {"primary": WEEK}})
        self.assertNotIn("private@example.test", json.dumps(result))

    def test_root_infers_checkout_owner_and_keeps_explicit_home(self):
        owner = SimpleNamespace(pw_dir="/home/display-user")
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(collector.os, "geteuid", return_value=0), \
                mock.patch.object(collector.Path, "stat", return_value=SimpleNamespace(st_uid=12345)), \
                mock.patch.object(collector.pwd, "getpwuid", return_value=owner):
            self.assertEqual(collector.default_codex_home(), Path("/home/display-user/.codex"))
            with mock.patch.dict(os.environ, {"CODEX_HOME": "/configured/codex"}):
                self.assertEqual(collector.default_codex_home(), Path("/configured/codex"))

    def run_fake_codex(self, mode="ready", timeout=2):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            home = root / ".codex"
            home.mkdir()
            executable = root / ".local/bin/codex"
            executable.parent.mkdir(parents=True)
            executable.write_text("#!/usr/bin/env python3\n" + textwrap.dedent('''
                import json, os, sys, time
                from pathlib import Path
                root = Path(os.environ["HOME"])
                mode = (root / "mode").read_text()
                (root / "pid").write_text(str(os.getpid()))
                if mode == "timeout": time.sleep(10)
                if mode == "exit": sys.exit(0)
                for line in sys.stdin:
                    request = json.loads(line)
                    method = request["method"]
                    with (root / "requests").open("a") as log: log.write(method + "\\n")
                    if method == "initialized": continue
                    if mode == "malformed": print("[]", flush=True); continue
                    result = {}
                    if method == "account/read":
                        assert request["params"] == {"refreshToken": False}
                        result = {"account": None if mode == "signed-out" else {"type":"chatgpt", "planType":"pro", "email":"DO_NOT_EXPORT"}}
                    if method == "account/rateLimits/read":
                        result = {"rateLimits": {"secondary": {"usedPercent":42,"windowDurationMins":10080,"resetsAt":1900000000}}, "accountId":"DO_NOT_EXPORT", "credits":"DO_NOT_EXPORT"}
                    print(json.dumps({"method":"account/updated", "params":{}}))
                    print(json.dumps({"id":request["id"], "result":result}), flush=True)
            '''))
            executable.chmod(0o755)
            (root / "mode").write_text(mode)
            owner = SimpleNamespace(pw_dir=folder, pw_uid=os.getuid(), pw_gid=os.getgid())
            with mock.patch.object(collector.pwd, "getpwuid", return_value=owner):
                result = collector.collect_usage(home, timeout=timeout)
            requests = (root / "requests").read_text().splitlines() if (root / "requests").exists() else []
            if (root / "pid").exists():
                with self.assertRaises(ProcessLookupError):
                    os.kill(int((root / "pid").read_text()), 0)
            return result, requests

    def test_rpc_handshake_and_usage_without_model_requests_or_private_data(self):
        result, requests = self.run_fake_codex()
        self.assertEqual(result["usedPercent"], 42)
        self.assertEqual(requests, ["initialize", "initialized", "account/read", "account/rateLimits/read"])
        self.assertNotIn("DO_NOT_EXPORT", json.dumps(result))

    def test_signed_out_stops_before_limits(self):
        result, requests = self.run_fake_codex("signed-out")
        self.assertEqual(result["status"], "not-signed-in")
        self.assertNotIn("account/rateLimits/read", requests)

    def test_timeout_malformed_output_and_early_exit_are_bounded(self):
        for mode in ("timeout", "malformed", "exit"):
            start = time.monotonic()
            result, _ = self.run_fake_codex(mode, timeout=0.2)
            self.assertFalse(result["available"])
            self.assertLess(time.monotonic() - start, 3)


if __name__ == "__main__":
    unittest.main()
