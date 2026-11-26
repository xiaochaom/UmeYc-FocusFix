"""Decky backend for automatic and manual focus cycling."""

import asyncio
import json
from pathlib import Path
import pwd
import sys

import decky

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gamescope import refocus
from star_rail import SceneMarker, app_id, find_sessions, log_snapshot


class Plugin:
    async def _main(self):
        self.settings_path = Path(decky.DECKY_PLUGIN_SETTINGS_DIR) / "settings.json"
        self.home = Path(decky.DECKY_USER_HOME).resolve()
        self.username = decky.DECKY_USER
        self.uid = pwd.getpwnam(self.username).pw_uid
        self.log_roots = (
            self.home, Path("/run/media") / decky.DECKY_USER, Path("/mnt"),
        )
        self.boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        try:
            stored = json.loads(self.settings_path.read_text())
        except (OSError, ValueError):
            stored = {}
        self.settings = stored if isinstance(stored, dict) else {}
        self.baselines = {}
        self.stopping = asyncio.Event()
        self.focus_lock = asyncio.Lock()
        self.task = asyncio.create_task(self._watch())

    def _save(self, next_settings):
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        pending = self.settings_path.with_suffix(".tmp")
        pending.write_text(json.dumps(next_settings) + "\n")
        pending.replace(self.settings_path)
        self.settings = next_settings

    def _configs(self):
        return self.settings.get("configs", {})

    async def get_settings(self):
        return {
            "enabled": self.settings.get("star_rail") is True,
            "configs": self._configs(),
            "home": str(self.home),
        }

    async def set_star_rail(self, enabled):
        if type(enabled) is not bool:
            raise ValueError("Expected a boolean")
        self._save({**self.settings, "star_rail": enabled})
        return {"enabled": enabled}

    def _log_path(self, name):
        try:
            path = Path(name).resolve()
        except (OSError, RuntimeError, TypeError, ValueError):
            return None
        if path.suffix.lower() in (".log", ".txt") and any(
            root in path.parents for root in self.log_roots
        ):
            return path
        return None

    async def save_game_config(self, identifier, name, log_path, marker):
        number = app_id(identifier)
        path = self._log_path(log_path)
        if not number or not isinstance(name, str) or not name or len(name) > 256:
            raise ValueError("Choose a Steam game")
        if path is None or log_snapshot(path) is None:
            raise ValueError("Choose an existing .log or .txt file in your game library")
        if (
            not isinstance(marker, str) or not marker.strip() or len(marker) > 512
            or any(char in marker for char in ("\0", "\n", "\r"))
        ):
            raise ValueError("Enter a single marker of 1 to 512 characters")
        key = str(number)
        configs = dict(self._configs())
        configs[key] = {
            "name": name, "log_path": str(path), "marker": marker,
            "enabled": configs.get(key, {}).get("enabled", True),
        }
        self.baselines.pop(key, None)
        self._save({**self.settings, "configs": configs})
        return configs

    async def set_game_config(self, identifier, enabled):
        if type(enabled) is not bool:
            raise ValueError("Expected a boolean")
        key = str(app_id(identifier))
        configs = dict(self._configs())
        configs[key] = {**configs[key], "enabled": enabled}
        self._save({**self.settings, "configs": configs})
        return configs

    async def delete_game_config(self, identifier):
        key = str(app_id(identifier))
        configs = dict(self._configs())
        configs.pop(key, None)
        self.baselines.pop(key, None)
        self._save({**self.settings, "configs": configs})
        return configs

    async def focus_current_game(self, current_app):
        number = app_id(current_app)
        if not number or self.stopping.is_set():
            return "not_foreground"
        await asyncio.sleep(0.15)
        async with self.focus_lock:
            return await asyncio.to_thread(
                refocus, number, lambda: not self.stopping.is_set(), True, self.username,
            )

    async def _watch(self):
        readers = {}
        attempted = {}
        while not self.stopping.is_set():
            preset = self.settings.get("star_rail") is True
            configs = self._configs()
            active = {key: config for key, config in configs.items() if config["enabled"]}
            if preset or active:
                try:
                    await self._scan(preset, active, readers, attempted)
                except Exception:
                    decky.logger.exception("Focus watcher failed")
            else:
                readers.clear()
            try:
                await asyncio.wait_for(self.stopping.wait(), timeout=0.65)
            except asyncio.TimeoutError:
                pass

    async def _scan(self, preset, configs, readers, attempted):
        sessions = await asyncio.to_thread(
            find_sessions, self.uid, {int(key) for key in configs}, preset,
        )
        running = {str(session.app_id) for session in sessions}
        for key, config in configs.items():
            if key not in running:
                path = self._log_path(config["log_path"])
                self.baselines[key] = log_snapshot(path) if path else None

        for key in readers.keys() - running:
            del readers[key]
        for session in sessions:
            key = str(session.app_id)
            config = configs.get(key)
            path = self._log_path(config["log_path"]) if config else None
            if config and path is None:
                continue
            token = f"{self.boot_id}:{session.start_ticks}:{session.process.name}"
            if attempted.get(key) == token or self.settings.get("last_automatic", {}).get(key) == token:
                continue
            marker = config["marker"] if config else "RPG.Client.AdventurePhase:_OnLoadingFinish"
            signature = (token, marker, path)
            previous, reader = readers.get(key, (None, None))
            if previous != signature:
                reader = SceneMarker(
                    session.start_ns, marker, self.baselines.get(key),
                    new_only=bool(config and key not in self.baselines),
                )
                readers[key] = (signature, reader)
            if not await asyncio.to_thread(reader.check, (path,) if path else session.log_paths()):
                continue

            def still_wanted():
                current = self._configs().get(key)
                enabled = current == config if config else (
                    self.settings.get("star_rail") is True and not (current and current["enabled"])
                )
                return enabled and not self.stopping.is_set() and session.process.exists()

            async with self.focus_lock:
                result = await asyncio.to_thread(
                    refocus, session.app_id, still_wanted, username=self.username,
                )
            if result not in ("success", "unconfirmed"):
                continue
            attempted[key] = token
            completed = {**self.settings.get("last_automatic", {}), key: token}
            self._save({**self.settings, "last_automatic": completed})
            decky.logger.info("Automatic focus cycle for %s: %s", key, result)

    async def _unload(self):
        self.stopping.set()
        await self.task
        async with self.focus_lock:
            pass
