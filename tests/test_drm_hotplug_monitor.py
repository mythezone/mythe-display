from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "drm-hotplug-monitor.py"
SPEC = importlib.util.spec_from_file_location("drm_hotplug_monitor", SCRIPT)
assert SPEC and SPEC.loader
MONITOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MONITOR
SPEC.loader.exec_module(MONITOR)


class DrmHotplugMonitorTest(unittest.TestCase):
    def test_reads_connected_connector_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, state in {
                "card1-HDMI-A-2": "connected\n",
                "card1-DP-1": "disconnected\n",
            }.items():
                connector = root / name
                connector.mkdir()
                (connector / "status").write_text(state, encoding="utf-8")
            statuses = MONITOR.connector_statuses(root)
        self.assertEqual(MONITOR.connected_signature(statuses), ("card1-HDMI-A-2",))

    def test_only_restarts_after_a_stable_reconnect(self) -> None:
        tracker = MONITOR.HotplugTracker.create(("card0-HDMI-A-2",))
        self.assertFalse(tracker.update((), now=1.0, stable_seconds=3.5))
        self.assertFalse(tracker.update(("card1-HDMI-A-2",), now=2.0, stable_seconds=3.5))
        self.assertFalse(tracker.update(("card1-HDMI-A-2",), now=5.4, stable_seconds=3.5))
        self.assertTrue(tracker.update(("card1-HDMI-A-2",), now=5.5, stable_seconds=3.5))

    def test_identity_change_without_observed_gap_also_recovers(self) -> None:
        tracker = MONITOR.HotplugTracker.create(("card0-HDMI-A-2",))
        self.assertFalse(tracker.update(("card1-HDMI-A-2",), now=1.0, stable_seconds=1.0))
        self.assertTrue(tracker.update(("card1-HDMI-A-2",), now=2.0, stable_seconds=1.0))

    def test_short_flap_that_returns_to_original_output_does_not_restart(self) -> None:
        tracker = MONITOR.HotplugTracker.create(("card1-HDMI-A-2",))
        self.assertFalse(tracker.update(("card1-DP-1",), now=1.0, stable_seconds=3.5))
        self.assertFalse(tracker.update(("card1-HDMI-A-2",), now=1.5, stable_seconds=3.5))
        self.assertFalse(tracker.update(("card1-HDMI-A-2",), now=9.0, stable_seconds=3.5))


if __name__ == "__main__":
    unittest.main()
