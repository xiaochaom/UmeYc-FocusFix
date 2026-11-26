"""Briefly switch the Gamescope base layer to Steam and restore it."""

from contextlib import contextmanager
import ctypes as c
import os
from pathlib import Path
import pwd
import re
import subprocess
import time


STEAM = 769
CARDINAL = 6
BASE_APP = "GAMESCOPECTRL_BASELAYER_APPID"
BASE_WINDOW = "GAMESCOPECTRL_BASELAYER_WINDOW"
FOCUSED_APP = "GAMESCOPE_FOCUSED_APP"
FOCUSED_GFX = "GAMESCOPE_FOCUSED_APP_GFX"
FOCUSED_WINDOW = "GAMESCOPE_FOCUSED_WINDOW"
FOCUSABLE = "GAMESCOPE_FOCUSABLE_APPS"
FOCUSABLE_WINDOWS = "GAMESCOPE_FOCUSABLE_WINDOWS"
BRIDGE = Path(__file__).resolve().parent / "bin/focus-bridge.exe"


class X11:
    def __init__(self):
        lib = c.CDLL("libX11.so.6")
        pointer, ulong, integer = c.c_void_p, c.c_ulong, c.c_int
        signatures = {
            "XOpenDisplay": (pointer, c.c_char_p),
            "XCloseDisplay": (integer, pointer),
            "XDefaultRootWindow": (ulong, pointer),
            "XInternAtom": (ulong, pointer, c.c_char_p, integer),
            "XGetWindowProperty": (
                integer, pointer, ulong, ulong, c.c_long, c.c_long, integer,
                ulong, c.POINTER(ulong), c.POINTER(integer), c.POINTER(ulong),
                c.POINTER(ulong), c.POINTER(pointer),
            ),
            "XChangeProperty": (
                integer, pointer, ulong, ulong, ulong, integer, integer, pointer, integer,
            ),
            "XDeleteProperty": (integer, pointer, ulong, ulong),
            "XGrabServer": (integer, pointer),
            "XUngrabServer": (integer, pointer),
            "XFlush": (integer, pointer),
            "XFree": (integer, pointer),
        }
        for name, (result, *arguments) in signatures.items():
            function = getattr(lib, name)
            function.restype = result
            function.argtypes = arguments
        self.lib = lib

    @contextmanager
    def display(self, address):
        handle = self.lib.XOpenDisplay(address.encode("ascii"))
        try:
            yield Root(self.lib, handle) if handle else None
        finally:
            if handle:
                self.lib.XCloseDisplay(handle)


class Root:
    def __init__(self, lib, display):
        self.lib = lib
        self.display = display
        self.window = lib.XDefaultRootWindow(display)
        self.atoms = {}

    def atom(self, name):
        if name not in self.atoms:
            self.atoms[name] = self.lib.XInternAtom(self.display, name.encode("ascii"), 1)
        return self.atoms[name]

    def get(self, name):
        atom = self.atom(name)
        if not atom:
            return None
        kind, count, remaining = c.c_ulong(), c.c_ulong(), c.c_ulong()
        width, data = c.c_int(), c.c_void_p()
        result = self.lib.XGetWindowProperty(
            self.display, self.window, atom, 0, 65536, 0, CARDINAL,
            c.byref(kind), c.byref(width), c.byref(count), c.byref(remaining), c.byref(data),
        )
        try:
            if result or kind.value != CARDINAL or width.value != 32 or remaining.value:
                return None
            values = c.cast(data, c.POINTER(c.c_ulong))
            return tuple(values[index] & 0xffffffff for index in range(count.value))
        finally:
            if data:
                self.lib.XFree(data)

    def set(self, name, values):
        if values is None:
            self.lib.XDeleteProperty(self.display, self.window, self.atom(name))
            return
        data = (c.c_ulong * len(values))(*values)
        self.lib.XChangeProperty(
            self.display, self.window, self.atom(name), CARDINAL, 32, 0, data, len(values),
        )

    @contextmanager
    def transaction(self):
        self.lib.XGrabServer(self.display)
        try:
            yield
        finally:
            self.lib.XUngrabServer(self.display)
            self.lib.XFlush(self.display)


def wait_for(check, seconds):
    deadline = time.monotonic() + seconds
    while True:
        if check():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.025)


def cycle(root, app_id, still_wanted):
    """Return a status after observing focus move away and back."""
    with root.transaction():
        if root.get(FOCUSED_APP) != (app_id,) or root.get(FOCUSED_GFX) != (app_id,):
            return "not_foreground"
        window = root.get(FOCUSED_WINDOW)
        apps = root.get(BASE_APP)
        pin = root.get(BASE_WINDOW)
        if not window or not apps or STEAM not in (root.get(FOCUSABLE) or ()):
            return "unavailable"
        if not still_wanted():
            return "cancelled"
        temporary = {BASE_APP: ((STEAM, *(item for item in apps if item != STEAM)), apps)}
        if pin and pin != (0,):
            temporary[BASE_WINDOW] = ((0,), pin)
        for key, (value, _) in temporary.items():
            root.set(key, value)

    try:
        def switched_to_steam():
            return root.get(FOCUSED_APP) == (STEAM,) and root.get(FOCUSED_GFX) == (STEAM,)

        lost = wait_for(switched_to_steam, 0.45)
    finally:
        with root.transaction():
            for key, (value, original) in temporary.items():
                if root.get(key) == value:
                    root.set(key, original)

    def restored_game():
        return (
            root.get(FOCUSED_APP) == (app_id,)
            and root.get(FOCUSED_GFX) == (app_id,)
            and root.get(FOCUSED_WINDOW) == window
        )

    restored = wait_for(restored_game, 0.65)
    return "success" if lost and restored else "unconfirmed"


def _wine_window(root, app_id, uid):
    window = root.get(FOCUSED_WINDOW)
    values = root.get(FOCUSABLE_WINDOWS) or ()
    for window_id, owner, pid in zip(values[::3], values[1::3], values[2::3]):
        if owner != app_id or (window_id,) != window or not pid:
            continue
        process = Path("/proc") / str(pid)
        try:
            if process.stat().st_uid != uid:
                return None
            settings = dict(
                field.split(b"=", 1) for field in (process / "environ").read_bytes().split(b"\0")
                if b"=" in field
            )
        except OSError:
            return None
        if b"WINEPREFIX" in settings:
            return window, settings
    return None


def _wine_bridge(root, app_id, window, settings, username, still_wanted):
    account = pwd.getpwnam(username)
    prefix = Path(os.fsdecode(settings[b"WINEPREFIX"]))
    display = os.fsdecode(settings.get(b"DISPLAY", b""))
    wine = None
    for value in settings.get(b"STEAM_COMPAT_TOOL_PATHS", b"").split(b":"):
        tool = Path(os.fsdecode(value))
        candidate = tool / "files/bin/wine"
        if tool.is_absolute() and candidate.is_file():
            wine = candidate
            break
    if (
        not BRIDGE.is_file() or wine is None or not prefix.is_absolute() or not prefix.is_dir()
        or not re.fullmatch(r":\d+(?:\.\d+)?", display)
    ):
        return "unavailable"
    if not still_wanted():
        return "cancelled"
    if root.get(FOCUSED_APP) != (app_id,) or root.get(FOCUSED_WINDOW) != window:
        return "not_foreground"

    environment = {
        "HOME": account.pw_dir,
        "USER": username,
        "LOGNAME": username,
        "PATH": os.defpath,
        "WINEPREFIX": str(prefix),
        "DISPLAY": display,
        "WINEDEBUG": "-all",
    }
    for key in ("SteamAppId", "SteamGameId"):
        value = settings.get(key.encode(), b"")
        if re.fullmatch(rb"-?\d+", value):
            environment[key] = value.decode("ascii")
    credentials = {}
    if os.geteuid() == 0:
        credentials = {
            "user": account.pw_uid, "group": account.pw_gid,
            "extra_groups": os.getgrouplist(username, account.pw_gid),
        }
    elif os.geteuid() != account.pw_uid:
        return "unavailable"
    try:
        result = subprocess.run(
            [wine, BRIDGE], cwd=account.pw_dir, env=environment, timeout=5,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            **credentials,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unconfirmed"
    returned = wait_for(lambda: (
        root.get(FOCUSED_APP) == (app_id,) and root.get(FOCUSED_WINDOW) == window
    ), 0.65)
    return "success" if result.returncode == 0 and returned else "unconfirmed"


def refocus(app_id, still_wanted, wait_for_menu=False, username=None):
    try:
        x11 = X11()
    except OSError:
        return "unavailable"

    for socket in sorted(Path("/tmp/.X11-unix").glob("X*")):
        if not socket.name[1:].isdigit():
            continue
        with x11.display(":" + socket.name[1:]) as root:
            if root is None or root.get(FOCUSED_GFX) != (app_id,):
                continue
            if wait_for_menu:
                wait_for(lambda: root.get(FOCUSED_APP) == (app_id,), 0.6)
            if username and root.get(FOCUSED_APP) == (app_id,):
                match = _wine_window(root, app_id, pwd.getpwnam(username).pw_uid)
                if match:
                    return _wine_bridge(root, app_id, *match, username, still_wanted)
            return cycle(root, app_id, still_wanted)
    return "not_foreground"
