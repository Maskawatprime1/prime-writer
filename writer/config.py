"""User settings stored in %LOCALAPPDATA%\\PrimeWriter\\config.json."""
from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path

APP_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PrimeWriter"
_OLD_APP_DATA = APP_DATA.parent / "LocalWriter"  # name before the rename to Prime Writer
if not APP_DATA.exists() and _OLD_APP_DATA.exists():
    import shutil
    try:  # one-time move of settings, dictionary, snippets and saved drafts
        shutil.copytree(_OLD_APP_DATA, APP_DATA)
    except OSError:
        pass
CONFIG_FILE = APP_DATA / "config.json"

DEFAULTS = {
    "enabled": True,                       # master switch for everything in other apps
    "live": True,                          # underline mistakes while typing in other apps
    "live_ai": True,                       # include AI suggestions in live underlines (uses the GPU)
    "disabled_apps": [],                   # exe names where hotkeys are off, e.g. "code.exe"
    "known_apps": {},                      # exe -> last window title seen
    "hotkeys": {"check": "Ctrl+Alt+G", "paraphrase": "Ctrl+Alt+P"},
    "start_with_windows": False,
    "popup_mode": "standard",
    "language": "en-US",                   # en-US, en-GB, en-CA, en-AU
    "picky": False,                        # LanguageTool picky mode: stricter style rules
    "dictionary": [],                      # words never flagged as spelling mistakes
    "snippets": {},                        # trigger -> text, e.g. ";addr" -> "221B Baker Street"
    "live_readability": False,             # Hemingway-style highlights in other apps
    "synonyms_on_select": True,            # double-click/select one word in other apps -> synonyms card
    "fallback_button": True,               # Prime Writer button in apps that hide their text boxes (WeChat)
    "button_apps": ["weixin.exe", "wechat.exe"],
    "button_pos": {},                      # "win:weixin.exe" / "field:chrome.exe" -> [dx, dy] where the user dragged the button
}

LANGUAGES = {"en-US": "American", "en-GB": "British", "en-CA": "Canadian", "en-AU": "Australian"}


def add_word(word: str) -> list[str]:
    word = word.strip()
    words = get()["dictionary"]
    if word and word.lower() not in (w.lower() for w in words):
        words.append(word)
        update(dictionary=sorted(words, key=str.lower))
    return get()["dictionary"]

_lock = threading.Lock()
_data: dict | None = None


def _load() -> dict:
    data = copy.deepcopy(DEFAULTS)
    try:
        saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        for k, v in saved.items():
            if k in data:
                data[k] = v
        data["hotkeys"] = {**DEFAULTS["hotkeys"], **saved.get("hotkeys", {})}
    except (OSError, ValueError):
        pass
    return data


def get() -> dict:
    global _data
    with _lock:
        if _data is None:
            _data = _load()
        return copy.deepcopy(_data)


def update(**changes) -> dict:
    global _data
    with _lock:
        if _data is None:
            _data = _load()
        for k, v in changes.items():
            if k in DEFAULTS:
                _data[k] = v
        APP_DATA.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_data, indent=2), encoding="utf-8")
        tmp.replace(CONFIG_FILE)
        return copy.deepcopy(_data)


def app_enabled(exe: str) -> bool:
    c = get()
    return c["enabled"] and exe.lower() not in c["disabled_apps"]


def set_app_enabled(exe: str, on: bool) -> dict:
    exe = exe.lower()
    disabled = set(get()["disabled_apps"])
    disabled.discard(exe) if on else disabled.add(exe)
    return update(disabled_apps=sorted(disabled))


def remember_app(exe: str, title: str) -> None:
    known = get()["known_apps"]
    if known.get(exe) != title:
        known[exe] = title[:120]
        update(known_apps=known)
