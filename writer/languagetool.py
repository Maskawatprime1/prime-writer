"""Local LanguageTool server: auto-start and query."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
LT_PORT = int(os.environ.get("LT_PORT", "8081"))
LT_URL = f"http://127.0.0.1:{LT_PORT}/v2"

_proc: subprocess.Popen | None = None
_client = httpx.Client(trust_env=False)  # bypass system proxy for localhost


def _search_roots() -> list[Path]:
    """Where to look for tools/LanguageTool-*: WRITER_HOME, the exe folder and its parents, the project."""
    roots = []
    if os.environ.get("WRITER_HOME"):
        roots.append(Path(os.environ["WRITER_HOME"]))
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        roots += [exe_dir, *list(exe_dir.parents)[:3]]
    roots.append(ROOT)
    return roots


def find_jar() -> Path | None:
    for root in _search_roots():
        jars = sorted((root / "tools").glob("LanguageTool-*/languagetool-server.jar"))
        if jars:
            return jars[-1]
    return None


def find_java(jar: Path) -> str | None:
    """Prefer the Java runtime shipped next to LanguageTool (tools\\jre), then any installed Java."""
    bundled = jar.parent.parent / "jre" / "bin" / "java.exe"
    return str(bundled) if bundled.is_file() else shutil.which("java")


def is_up() -> bool:
    try:
        return _client.get(f"{LT_URL}/languages", timeout=2.0).status_code == 200
    except httpx.HTTPError:
        return False


def start(wait: float = 60.0) -> bool:
    """Start LanguageTool if installed and not already running."""
    global _proc
    if is_up():
        return True
    jar = find_jar()
    java = find_java(jar) if jar else None
    if not jar or not java:
        return False
    # Java's HTTP server needs a Unix-socket pipe in a temp folder, and on some PCs some folders refuse it
    # ("Invalid argument: connect"). Try short, writable folders in turn; the failing case exits within seconds.
    public = Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
    local = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    candidates = [public / "PrimeWriter", jar.parent / "tmp", local / "PrimeWriter" / "lt-tmp", None]
    deadline = time.time() + wait
    for sock_dir in candidates:
        args = [java, "-Xmx1g"]
        if sock_dir is not None:
            try:
                sock_dir.mkdir(parents=True, exist_ok=True)
                for stale in sock_dir.glob("socket_*"):
                    stale.unlink(missing_ok=True)
            except OSError:
                continue
            args.append(f"-Djdk.net.unixdomain.tmpdir={sock_dir}")
        _proc = subprocess.Popen(
            args + ["-cp", str(jar), "org.languagetool.server.HTTPServer", "--port", str(LT_PORT), "--allow-origin", "*"],
            cwd=jar.parent,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        while time.time() < deadline:
            if is_up():
                return True
            if _proc.poll() is not None:
                break  # this folder didn't work; try the next one
            time.sleep(0.5)
        else:
            return False
    return False


def stop() -> None:
    if _proc and _proc.poll() is None:
        _proc.terminate()


def check(text: str, language: str = "en-US", picky: bool = False) -> list[dict]:
    data = {"text": text, "language": language}
    if picky:
        data["level"] = "picky"
    r = _client.post(f"{LT_URL}/check", data=data, timeout=60.0)
    r.raise_for_status()
    issues = []
    for m in r.json().get("matches", []):
        rule = m.get("rule", {})
        cat = rule.get("category", {}).get("id", "")
        itype = rule.get("issueType", "")
        if itype == "misspelling" or cat == "TYPOS":
            kind = "spelling"
        elif cat in ("STYLE", "REDUNDANCY", "PLAIN_ENGLISH", "TYPOGRAPHY", "CASING") or itype == "style":
            kind = "style"
        else:
            kind = "grammar"
        issues.append({
            "offset": m["offset"],
            "length": m["length"],
            "message": m.get("message", ""),
            "replacements": [x["value"] for x in m.get("replacements", [])[:5]],
            "kind": kind,
            "source": "LanguageTool",
        })
    return issues
