"""Find the current Star Rail process and read its Unity scene marker."""

from dataclasses import dataclass
import os
from pathlib import Path
import stat
import time


MARKER = b"RPG.Client.AdventurePhase:_OnLoadingFinish"
COMPANIES = ("miHoYo", "Cognosphere", "COGNOSPHERE", "HoYoverse")
TITLES = ("崩坏：星穹铁道", "崩壊：スターレイル", "Honkai Star Rail", "Honkai_Star_Rail", "Star Rail")


@dataclass(frozen=True)
class Session:
    process: Path
    start_ticks: int
    start_ns: int
    app_id: int
    prefixes: tuple
    star_rail: bool

    def log_paths(self):
        for prefix in self.prefixes:
            users = prefix / "drive_c/users"
            try:
                profiles = list(users.iterdir())
            except OSError:
                continue
            for profile in sorted(profiles, key=lambda path: (path.name != "steamuser", path.name)):
                base = profile / "AppData/LocalLow"
                for company in COMPANIES:
                    for title in TITLES:
                        yield base / company / title / "Player.log"


def app_id(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    if not -(1 << 31) <= number < (1 << 32):
        return 0
    return number & 0xffffffff


def find_sessions(uid, configured, watch_star_rail, proc=Path("/proc")):
    boot_ns = time.time_ns() - time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    ticks_per_second = os.sysconf("SC_CLK_TCK")
    sessions = {}
    for process in proc.iterdir():
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != uid:
                continue
            is_star_rail = watch_star_rail and (
                (process / "comm").read_bytes().strip().lower() == b"starrail.exe"
            )
            fields = (process / "stat").read_text().rsplit(")", 1)[1].split()
            ticks = int(fields[19])
            env = dict(
                item.split(b"=", 1)
                for item in (process / "environ").read_bytes().split(b"\0")
                if b"=" in item
            )
        except (OSError, IndexError, ValueError):
            continue
        ids = (app_id(env.get(b"SteamAppId")), app_id(env.get(b"SteamGameId")))
        steam_id = next((number for number in ids if number in configured), 0)
        steam_id = steam_id or (ids[0] or ids[1] if is_star_rail else 0)
        if not steam_id:
            continue
        previous = sessions.get(steam_id)
        if previous and (not previous.star_rail, previous.start_ticks) <= (not is_star_rail, ticks):
            continue
        prefixes = []
        for key, suffix in ((b"WINEPREFIX", ""), (b"STEAM_COMPAT_DATA_PATH", "/pfx")):
            raw = env.get(key, b"")
            if raw.startswith(b"/"):
                path = os.fsdecode(raw) + suffix
                prefixes.extend((process / "root" / path.lstrip("/"), Path(path)))
        sessions[steam_id] = Session(
            process, ticks, boot_ns + ticks * 1_000_000_000 // ticks_per_second,
            steam_id, tuple(dict.fromkeys(prefixes)), is_star_rail,
        )
    return sessions.values()


def log_snapshot(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as log:
            info = os.fstat(log.fileno())
            if not stat.S_ISREG(info.st_mode):
                return None
            log.seek(max(0, info.st_size - 64))
            return (info.st_dev, info.st_ino), info.st_size, log.read(64)
    except OSError:
        return None


class SceneMarker:
    def __init__(self, start_ns, marker=MARKER.decode("ascii"), baseline=None, new_only=False):
        self.start_ns = start_ns
        self.marker = marker.encode("utf-8")
        self.file_id = None
        self.offset = 0
        self.overlap = b""
        self.matched = False
        self.path = None
        self.baseline = baseline
        self.new_only = new_only

    def check(self, paths):
        if self.matched:
            return True
        for path in (self.path,) if self.path else paths:
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                with os.fdopen(fd, "rb") as log:
                    info = os.fstat(log.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_mtime_ns < self.start_ns:
                        continue
                    self.path = path
                    identity = (info.st_dev, info.st_ino)
                    if identity != self.file_id or info.st_size < self.offset:
                        self.file_id, self.offset, self.overlap = identity, 0, b""
                        if self.baseline and self.baseline[0] == identity:
                            _, size, suffix = self.baseline
                            if info.st_size >= size:
                                log.seek(max(0, size - len(suffix)))
                                if log.read(len(suffix)) == suffix:
                                    self.offset = size
                        elif self.new_only and self.baseline is None:
                            self.offset = info.st_size
                        self.baseline = None
                        self.new_only = False
                    log.seek(self.offset)
                    stop = min(info.st_size, self.offset + 1024 * 1024)
                    while data := log.read(min(65536, max(0, stop - self.offset))):
                        self.offset += len(data)
                        chunk = self.overlap + data
                        if self.marker in chunk:
                            self.matched = True
                            return True
                        self.overlap = chunk[1 - len(self.marker):] if len(self.marker) > 1 else b""
                    return False
            except OSError:
                self.path = None
        return False
