"""First-run setup on a new PC: install Ollama and download the AI model, with progress for the UI."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import httpx

from shared import ollama

MODELS = {
    "qwen3:8b": {"label": "Qwen3 8B", "note": "Best quality. Needs 16 GB RAM; fast with an 8 GB NVIDIA GPU.", "gb": 5.2},
    "qwen3:4b": {"label": "Qwen3 4B", "note": "Lighter and faster. For PCs with 8 GB RAM or no GPU.", "gb": 2.5},
}
OLLAMA_SETUP_URL = "https://ollama.com/download/OllamaSetup.exe"
REGISTRY = "https://registry.ollama.ai/v2/library"

_lock = threading.Lock()
_task: dict = {"name": "", "phase": "", "done": 0, "total": 0, "error": "", "running": False}


def _set(**kw) -> None:
    with _lock:
        _task.update(kw)


def ollama_exe() -> Path | None:
    for p in (Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
              Path(shutil.which("ollama") or "")):
        if p.is_file():
            return p
    return None


def status() -> dict:
    models = ollama.list_models()
    with _lock:
        task = dict(_task)
    return {
        "ollama_installed": ollama_exe() is not None,
        "ollama_running": ollama.is_up(),
        "models": models,
        "ready": bool(models),
        "choices": [{"id": k, **v} for k, v in MODELS.items()],
        "task": task,
    }


def _start_ollama() -> bool:
    if ollama.is_up():
        return True
    exe = ollama_exe()
    if not exe:
        return False
    subprocess.Popen([str(exe), "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(60):
        if ollama.is_up():
            return True
        time.sleep(0.5)
    return False


def _run(name: str, fn) -> bool:
    with _lock:
        if _task["running"]:
            return False
        _task.update(name=name, phase="Starting…", done=0, total=0, error="", running=True)

    def wrap():
        try:
            fn()
            _set(phase="Done", running=False)
        except Exception as e:  # noqa: BLE001
            _set(error=str(e) or e.__class__.__name__, running=False)

    threading.Thread(target=wrap, daemon=True).start()
    return True


# ---------- Ollama ----------
def install_ollama() -> bool:
    def work():
        if ollama_exe() is None:
            dest = Path(tempfile.gettempdir()) / "OllamaSetup.exe"
            _download(OLLAMA_SETUP_URL, dest, "Downloading Ollama")
            _set(phase="Installing Ollama (this takes a minute)…", done=0, total=0)
            subprocess.run([str(dest), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], check=True)
            dest.unlink(missing_ok=True)
        _set(phase="Starting Ollama…")
        if not _start_ollama():
            raise RuntimeError("Ollama was installed but did not start. Restart the PC and open Prime Writer again.")
    return _run("ollama", work)


def _download(url: str, dest: Path, label: str) -> None:
    part = dest.with_suffix(dest.suffix + ".partial")
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(60, connect=20)) as c:
        with c.stream("GET", url) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done = 0
            _set(phase=label, done=0, total=total)
            with open(part, "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    _set(done=done)
    part.replace(dest)


# ---------- model ----------
def pull_model(model: str) -> bool:
    if model not in MODELS:
        raise ValueError("Unknown model")

    def work():
        if not _start_ollama():
            raise RuntimeError("Ollama is not running. Install it first.")
        try:
            _pull_via_ollama(model)
        except Exception as first:  # noqa: BLE001  (e.g. a proxy/VPN that breaks Ollama's own download)
            _set(phase=f"Ollama's download failed ({first}). Trying a direct download…", done=0, total=0)
            _pull_direct(model)
        if model not in ollama.list_models():
            raise RuntimeError("The model was downloaded but Ollama doesn't list it. Restart Ollama and try again.")
    return _run("model", work)


def _pull_via_ollama(model: str) -> None:
    with httpx.Client(trust_env=False, timeout=httpx.Timeout(None, connect=10)) as c:
        with c.stream("POST", f"{ollama.OLLAMA_URL}/api/pull", json={"model": model, "stream": True}) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line.strip():
                    continue
                msg = json.loads(line)
                if msg.get("error"):
                    raise RuntimeError(msg["error"])
                st = msg.get("status", "")
                if msg.get("total"):
                    _set(phase=f"Downloading {model}", done=msg.get("completed", 0), total=msg["total"])
                else:
                    _set(phase=st.capitalize() + "…")
                if st == "success":
                    return
    raise RuntimeError("Download stopped unexpectedly")


def _models_dir() -> Path:
    return Path(os.environ.get("OLLAMA_MODELS") or Path.home() / ".ollama" / "models")


def _pull_direct(model: str) -> None:
    """Download blobs straight from Ollama's registry (uses the system proxy), verify hashes, write the manifest."""
    name, tag = model.split(":")
    root = _models_dir()
    (root / "blobs").mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(60, connect=20)) as c:
        r = c.get(f"{REGISTRY}/{name}/manifests/{tag}",
                  headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"})
        r.raise_for_status()
        manifest_text = r.text
        manifest = r.json()
        layers = [manifest["config"], *manifest["layers"]]
        total = sum(l["size"] for l in layers)
        done = 0
        for layer in layers:
            digest = layer["digest"]
            dest = root / "blobs" / digest.replace(":", "-")
            if dest.is_file() and dest.stat().st_size == layer["size"]:
                done += layer["size"]
                continue
            part = dest.with_name(dest.name + "-pw-partial")
            have = part.stat().st_size if part.is_file() else 0
            headers = {"Range": f"bytes={have}-"} if have else {}
            with c.stream("GET", f"{REGISTRY}/{name}/blobs/{digest}", headers=headers) as br:
                br.raise_for_status()
                if have and br.status_code != 206:
                    have = 0
                with open(part, "ab" if have else "wb") as f:
                    got = have
                    for chunk in br.iter_bytes(1 << 20):
                        f.write(chunk)
                        got += len(chunk)
                        _set(phase=f"Downloading {model}", done=done + got, total=total)
            h = hashlib.sha256()
            with open(part, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 22), b""):
                    h.update(chunk)
            if "sha256:" + h.hexdigest() != digest:
                part.unlink(missing_ok=True)
                raise RuntimeError("Downloaded file was corrupted. Please try again.")
            part.replace(dest)
            done += layer["size"]
    mdir = root / "manifests" / "registry.ollama.ai" / "library" / name
    mdir.mkdir(parents=True, exist_ok=True)
    (mdir / tag).write_text(manifest_text, encoding="utf-8")
