from contextlib import nullcontext
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from gamescope import (
    BASE_APP, BASE_WINDOW, FOCUSABLE, FOCUSED_APP, FOCUSED_GFX, FOCUSED_WINDOW,
    STEAM, cycle,
)
from star_rail import MARKER, SceneMarker, app_id, find_sessions, log_snapshot


class FakeRoot:
    def __init__(self):
        self.original_apps = (2450901161, STEAM, 12345)
        self.original_window = (70001,)
        self.properties = {
            BASE_APP: self.original_apps,
            BASE_WINDOW: self.original_window,
            FOCUSABLE: (STEAM, 2450901161),
            FOCUSED_APP: (2450901161,),
            FOCUSED_GFX: (2450901161,),
            FOCUSED_WINDOW: self.original_window,
        }
        self.changes = []

    def transaction(self):
        return nullcontext()

    def get(self, key):
        return self.properties.get(key)

    def set(self, key, value):
        self.changes.append((key, value))
        self.properties[key] = value
        if key == BASE_APP:
            self.properties[FOCUSED_APP] = (value[0],)
            self.properties[FOCUSED_GFX] = (value[0],)
            self.properties[FOCUSED_WINDOW] = (
                (12,) if value[0] == STEAM else self.original_window
            )


class FocusTests(unittest.TestCase):
    def test_cycle_moves_to_steam_and_restores_original_values(self):
        root = FakeRoot()
        self.assertEqual(cycle(root, 2450901161, lambda: True), "success")
        self.assertEqual(root.changes[0], (BASE_APP, (STEAM, 2450901161, 12345)))
        self.assertEqual(root.get(BASE_APP), root.original_apps)
        self.assertEqual(root.get(BASE_WINDOW), root.original_window)

    def test_wrong_app_and_cancellation_leave_focus_alone(self):
        root = FakeRoot()
        self.assertEqual(cycle(root, 12345, lambda: True), "not_foreground")
        self.assertEqual(cycle(root, 2450901161, lambda: False), "cancelled")
        self.assertEqual(root.changes, [])

    def test_proton_game_uses_win32_bridge(self):
        from gamescope import refocus

        root = FakeRoot()
        settings = {b"WINEPREFIX": b"/home/deck/prefix"}
        still_wanted = lambda: True
        with (
            patch("gamescope.Path.glob", return_value=[Path("/tmp/.X11-unix/X0")]),
            patch("gamescope.X11") as x11,
            patch("gamescope.pwd.getpwnam"),
            patch("gamescope._wine_window", return_value=(root.original_window, settings)),
            patch("gamescope._wine_bridge", return_value="success") as bridge,
        ):
            x11.return_value.display.return_value = nullcontext(root)
            self.assertEqual(refocus(2450901161, still_wanted, username="deck"), "success")
            bridge.assert_called_once_with(
                root, 2450901161, root.original_window, settings, "deck", still_wanted,
            )
        self.assertEqual(root.changes, [])

    def test_steam_updates_take_priority_during_cycle(self):
        root = FakeRoot()

        def switch_despite_plugin(check, _seconds):
            observed = check()
            root.set(BASE_APP, (12345, STEAM))
            root.set(BASE_WINDOW, (9000,))
            return observed

        with patch("gamescope.wait_for", side_effect=switch_despite_plugin):
            self.assertEqual(cycle(root, 2450901161, lambda: True), "unconfirmed")
        self.assertEqual(root.get(BASE_APP), (12345, STEAM))
        self.assertEqual(root.get(BASE_WINDOW), (9000,))


class LogTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.log = Path(temporary.name) / "Player.log"

    def test_preset_ignores_previous_launch_and_matches_split_marker(self):
        self.log.write_bytes(MARKER)
        start = time.time_ns() + 1
        reader = SceneMarker(start)
        self.assertFalse(reader.check([self.log]))
        self.log.write_bytes(MARKER[:16])
        os.utime(self.log, ns=(start + 1_000_000, start + 1_000_000))
        self.assertFalse(reader.check([self.log]))
        with self.log.open("ab") as stream:
            stream.write(MARKER[16:])
        os.utime(self.log, ns=(start + 2_000_000, start + 2_000_000))
        self.assertTrue(reader.check([self.log]))

    def test_custom_rule_ignores_old_marker_in_append_only_logs(self):
        self.log.write_text("进图\n", encoding="utf-8")
        baseline = log_snapshot(self.log)
        start = time.time_ns()
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write("starting\n")
        reader = SceneMarker(start, "进图", baseline)
        self.assertFalse(reader.check([self.log]))
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write("进图\n")
        self.assertTrue(reader.check([self.log]))

    def test_custom_rule_detects_truncate_and_regrow(self):
        self.log.write_bytes(b"old\n")
        baseline = log_snapshot(self.log)
        start = time.time_ns()
        self.log.write_bytes(b"new marker\n")
        self.assertTrue(SceneMarker(start, "new", baseline).check([self.log]))

    def test_custom_rule_created_during_game_ignores_existing_lines(self):
        self.log.write_bytes(b"trigger\n")
        reader = SceneMarker(0, "trigger", new_only=True)
        self.assertFalse(reader.check([self.log]))
        self.log.write_bytes(b"trigger\nnew trigger\n")
        self.assertTrue(reader.check([self.log]))


class SessionTests(unittest.TestCase):
    def test_steam_shortcut_unsigned_and_signed_ids_match(self):
        self.assertEqual(app_id("-1844066135"), 2450901161)
        self.assertEqual(app_id("2450901161"), 2450901161)
        self.assertEqual(app_id("10526996499386212352"), 0)

    def test_prefers_star_rail_process_and_uses_wine_prefix(self):
        with TemporaryDirectory() as directory, patch.object(
            time, "CLOCK_BOOTTIME", 7, create=True,
        ), patch.object(time, "clock_gettime_ns", return_value=0):
            proc = Path(directory)
            for pid, name, tick in (
                ("101", "StarRail.exe", 104), ("100", "launcher", 100),
                ("102", "helper", 106),
            ):
                process = proc / pid
                process.mkdir()
                (process / "comm").write_text(name)
                stat_fields = " ".join(["0"] * 19 + [str(tick)])
                (process / "stat").write_text(f"{pid} ({name}) {stat_fields}")
                (process / "environ").write_bytes(
                    b"SteamAppId=-1844066135\0WINEPREFIX=/example/prefix\0"
                )
            session, = find_sessions(os.getuid(), {2450901161}, True, proc)
            self.assertEqual(session.process.name, "101")
            self.assertIn(Path("/example/prefix"), session.prefixes)
            self.assertTrue(session.star_rail)


if __name__ == "__main__":
    unittest.main()
