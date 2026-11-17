"""Local writing assistant: grammar check + paraphrase.

Run from the project root:  .venv\\Scripts\\python -m writer.server
"""
from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from shared import ollama
from writer import config
from writer import languagetool as lt
from writer import readability
from writer.prompts import (EXTRA_MODES, GRAMMAR_SCHEMA, GRAMMAR_SYSTEM, MODES, SYNONYM_SCHEMA,
                            SYNONYM_SYSTEM, VARIETY, paraphrase_messages)

STATIC = Path(__file__).parent / "static"
# One model for both jobs: two models don't fit in 8 GB VRAM together, and swapping costs seconds.
CHECK_MODEL = os.environ.get("WRITER_CHECK_MODEL", "qwen3:8b")
PARAPHRASE_MODEL = os.environ.get("WRITER_PARAPHRASE_MODEL", "qwen3:8b")
MAX_CHARS = 20_000


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("WRITER_NO_LT") != "1":
        print("Starting LanguageTool..." if lt.find_jar() else "LanguageTool not installed; LLM-only checks.")
        print("LanguageTool ready." if lt.start() else "LanguageTool unavailable.")
    yield
    lt.stop()


app = FastAPI(title="Prime Writer", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
APP = STATIC / "app"  # React UI built from frontend/ (npm run build)
if (APP / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=APP / "assets"), name="assets")
if (APP / "brand").is_dir():
    app.mount("/brand", StaticFiles(directory=APP / "brand"), name="brand")


@app.middleware("http")
async def no_cache(request, call_next):
    # The desktop WebView keeps a disk cache; without this, a rebuilt exe can show stale UI files.
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


class CheckIn(BaseModel):
    text: str = Field(max_length=MAX_CHARS)
    language: str | None = None   # default: Settings
    picky: bool | None = None     # default: Settings
    use_lt: bool = True
    use_llm: bool = True
    readability: bool = False
    model: str | None = None


class ParaIn(BaseModel):
    text: str = Field(max_length=MAX_CHARS)
    mode: str = "standard"
    model: str | None = None
    strength: int = 3              # 1 = few changes ... 5 = many
    freeze: list[str] = []         # words/phrases to keep unchanged


@app.get("/")
def index():
    return FileResponse(APP / "index.html")


def _pick(preferred: str, models: list[str]) -> str:
    return preferred if preferred in models or not models else models[-1]


@app.get("/api/status")
def status():
    models = ollama.list_models()
    return {
        "ollama": ollama.is_up(),
        "models": models,
        "languagetool": lt.is_up(),
        "check_model": _pick(CHECK_MODEL, models),
        "paraphrase_model": _pick(PARAPHRASE_MODEL, models),
        "modes": list(MODES),
    }


# ---------- desktop integration (set by writer.desktop when running as the app) ----------
DESKTOP = None  # object with: set_startup(bool)->str|None, reload_hotkeys(), show_main(), hotkey_errors()->list


@app.get("/settings")
def settings_page():
    return FileResponse(APP / "index.html")  # the React app shows Settings for this path


@app.get("/popup")
def popup_page():
    return FileResponse(STATIC / "popup.html")


def _doc_path(name: str) -> Path:
    import sys as _sys
    base = Path(getattr(_sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / name


@app.get("/api/about")
def about():
    from writer import APP_NAME, COPYRIGHT, LICENSE_NAME, __author__, __version__
    return {"name": APP_NAME, "version": __version__, "author": __author__, "copyright": COPYRIGHT, "license": LICENSE_NAME}


@app.get("/license")
def license_text():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(_doc_path("LICENSE").read_text(encoding="utf-8"))


@app.get("/notices")
def notices_text():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(_doc_path("THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8"))


@app.get("/api/setup")
def setup_status():
    from writer import setup
    return setup.status()


@app.post("/api/setup/ollama")
def setup_ollama():
    from writer import setup
    if not setup.install_ollama():
        raise HTTPException(409, "Another setup step is still running")
    return setup.status()


class ModelIn(BaseModel):
    model: str


@app.post("/api/setup/model")
def setup_model(body: ModelIn):
    from writer import setup
    try:
        started = setup.pull_model(body.model)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not started:
        raise HTTPException(409, "Another setup step is still running")
    return setup.status()


@app.get("/favicon.ico")
def favicon():
    return FileResponse(APP / "brand" / "logo-mark.png", media_type="image/png")


@app.get("/card")
def card_page():
    return FileResponse(STATIC / "card.html")


@app.get("/api/config")
def get_config():
    c = config.get()
    c["desktop"] = DESKTOP is not None
    c["hotkey_errors"] = DESKTOP.hotkey_errors() if DESKTOP else []
    return c


class ConfigIn(BaseModel):
    enabled: bool | None = None
    language: str | None = None
    picky: bool | None = None
    live_readability: bool | None = None
    synonyms_on_select: bool | None = None
    fallback_button: bool | None = None
    button_apps: list[str] | None = None
    button_pos: dict[str, list[int]] | None = None
    snippets: dict[str, str] | None = None
    live: bool | None = None
    live_ai: bool | None = None
    start_with_windows: bool | None = None
    hotkeys: dict[str, str] | None = None
    popup_mode: str | None = None


@app.post("/api/config")
def set_config(body: ConfigIn):
    changes = body.model_dump(exclude_none=True)
    if "hotkeys" in changes:
        from writer.win32 import parse_hotkey
        hk = {**config.get()["hotkeys"], **changes["hotkeys"]}
        try:
            for spec in hk.values():
                mods, _ = parse_hotkey(spec)
                if not mods & 0x7:
                    raise ValueError(f"{spec}: add Ctrl, Alt or Shift")
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        if len(set(hk.values())) != len(hk):
            raise HTTPException(400, "Hotkeys must be different")
        changes["hotkeys"] = hk
    if "start_with_windows" in changes:
        if not DESKTOP:
            raise HTTPException(400, "Only available in the desktop app")
        err = DESKTOP.set_startup(changes["start_with_windows"])
        if err:
            raise HTTPException(500, err)
    if "language" in changes and changes["language"] not in config.LANGUAGES:
        raise HTTPException(400, "Unknown language")
    if "snippets" in changes:
        clean = {}
        for k, v in changes["snippets"].items():
            k = k.strip()
            if not k or any(c.isspace() for c in k) or len(k) > 30:
                raise HTTPException(400, f"Bad trigger '{k}': no spaces, max 30 characters")
            clean[k] = v[:5000]
        changes["snippets"] = clean
    if changes.get("popup_mode") and changes["popup_mode"] not in MODES:
        raise HTTPException(400, "Unknown mode")
    config.update(**changes)
    if "hotkeys" in changes and DESKTOP:
        DESKTOP.reload_hotkeys()
    return get_config()


@app.get("/api/apps")
def list_apps():
    c = config.get()
    try:
        from writer.win32 import list_window_apps
        running = list_window_apps()
    except Exception:  # noqa: BLE001  (non-Windows)
        running = {}
    names = set(running) | set(c["known_apps"]) | set(c["disabled_apps"])
    apps = [{
        "exe": n,
        "title": running.get(n) or c["known_apps"].get(n, ""),
        "running": n in running,
        "used": n in c["known_apps"],
        "enabled": n not in c["disabled_apps"],
    } for n in names]
    apps.sort(key=lambda a: (not a["running"], a["exe"]))
    return {"apps": apps}


class AppToggle(BaseModel):
    exe: str = Field(min_length=1, max_length=260)
    enabled: bool


@app.post("/api/apps")
def toggle_app(body: AppToggle):
    config.set_app_enabled(body.exe, body.enabled)
    return {"ok": True}


if os.environ.get("LW_DEBUG") == "1":
    @app.get("/api/debug/overlay")
    def debug_overlay():
        ov = DESKTOP.overlay if DESKTOP else None
        f = ov.field if ov else None
        return {
            "field": f.exe if f else None,
            "text_len": len(f.text) if f else 0,
            "checked": {k: (v == f.text) for k, v in f.checked.items()} if f else None,
            "issues": [{"original": i["original"], "kind": i["kind"], "source": i["source"], "rects": i["rects"],
                        "replacements": i["replacements"][:2]} for i in (f.issues if f else [])],
            "lines_visible": ov.lines.visible if ov else None,
            "badge_visible": ov.badge.visible if ov else None,
            "card_issue": ov.card_issue["original"] if ov and ov.card_issue else None,
            "card_kind": ov.card_issue.get("kind") if ov and ov.card_issue else None,
            "card_replacements": ov.card_issue.get("replacements") if ov and ov.card_issue else None,
            "rewrite": ov.rewrite["text"] if ov and ov.rewrite else None,
            "selected": ov.sel[0] if ov else None,
        }

    @app.post("/api/debug/apply")
    def debug_apply(i: int = 0):
        DESKTOP.overlay.post(DESKTOP.overlay.apply_fix, i)
        return {"ok": True}

    @app.post("/api/debug/card")
    def debug_card(action: str, i: int = 0):
        from writer.desktop import CardApi
        api = CardApi(DESKTOP)
        getattr(api, action)(*([i] if action == "apply" else []))
        return {"ok": True}

    @app.post("/api/debug/badge")
    def debug_badge():
        DESKTOP.overlay.post(DESKTOP.overlay.open_panel)
        return {"ok": True}


@app.post("/api/show")
def show_main():
    if DESKTOP:
        DESKTOP.show_main()
    return {"ok": True}


def _locate(text: str, needle: str, taken: list[tuple[int, int]]) -> int:
    """Find needle in text, skipping spans already claimed. Prefer whole-word hits."""
    if not needle:
        return -1
    pattern = re.compile(r"(?<!\w)" + re.escape(needle) + r"(?!\w)") if needle[0].isalnum() and needle[-1].isalnum() else re.compile(re.escape(needle))
    for m in pattern.finditer(text):
        s, e = m.start(), m.end()
        if not any(s < te and ts < e for ts, te in taken):
            return s
    return -1


def llm_check(text: str, model: str, language: str = "en-US") -> list[dict]:
    system = GRAMMAR_SYSTEM + f" The text is {VARIETY.get(language, 'American')} English: use that spelling."
    data = ollama.chat_json(model, system, text, GRAMMAR_SCHEMA, num_ctx=8192)
    issues, taken = [], []
    for it in data.get("issues", []):
        orig, rep = it.get("original", ""), it.get("replacement", "")
        if not orig or orig == rep:
            continue
        pos = _locate(text, orig, taken)
        if pos < 0:
            continue  # hallucinated span: drop it
        taken.append((pos, pos + len(orig)))
        issues.append({
            "offset": pos,
            "length": len(orig),
            "message": it.get("explanation", ""),
            "replacements": [rep],
            "kind": it.get("kind", "grammar"),
            "source": "AI",
        })
    return issues


def _overlaps(a: dict, b: dict) -> bool:
    return a["offset"] < b["offset"] + b["length"] and b["offset"] < a["offset"] + a["length"]


@app.post("/api/check")
def check(body: CheckIn):
    text = body.text
    if not text.strip():
        return {"issues": [], "errors": []}
    cfg = config.get()
    language = body.language or cfg["language"]
    picky = cfg["picky"] if body.picky is None else body.picky
    issues, errors = [], []
    if body.use_lt and lt.is_up():
        try:
            issues += lt.check(text, language, picky)
        except Exception as e:  # noqa: BLE001
            errors.append(f"LanguageTool: {e}")
    if body.use_llm:
        try:
            for it in llm_check(text, body.model or _pick(CHECK_MODEL, ollama.list_models()), language):
                if not any(_overlaps(it, x) for x in issues):
                    issues.append(it)
        except ollama.OllamaError as e:
            errors.append(str(e))
    sentence_level = []
    if body.readability:
        found = readability.analyze(text)
        issues += [i for i in found if i["scope"] == "word" and not any(_overlaps(i, x) for x in issues)]
        sentence_level = [i for i in found if i["scope"] == "sentence"]
    # personal dictionary: never flag these words as misspelled
    words = {w.lower() for w in cfg["dictionary"]}
    if words:
        issues = [i for i in issues
                  if not (i["kind"] == "spelling" and text[i["offset"]:i["offset"] + i["length"]].lower() in words)]
    for i in issues:
        i.setdefault("scope", "word")
    issues.sort(key=lambda x: x["offset"])
    return {"issues": issues + sentence_level, "errors": errors}


@app.post("/api/paraphrase")
def paraphrase(body: ParaIn):
    if body.mode not in MODES and body.mode not in EXTRA_MODES:
        raise HTTPException(400, f"Unknown mode. Use one of: {', '.join(MODES)}")
    if not body.text.strip():
        return {"text": ""}
    model = body.model or _pick(PARAPHRASE_MODEL, ollama.list_models())
    strength = min(5, max(1, body.strength))
    temp = 0.2 if body.mode == "fix" else (0.3, 0.5, 0.7, 0.85, 1.0)[strength - 1]
    freeze = [f.strip() for f in body.freeze if f.strip()][:20]
    try:
        system, user = paraphrase_messages(body.mode, body.text, strength, freeze, config.get()["language"])
        out = ollama.chat(model, system, user, temperature=temp, num_ctx=8192)
    except ollama.OllamaError as e:
        raise HTTPException(502, str(e)) from e
    out = re.sub(r"^<think>.*?</think>\s*", "", out, flags=re.S)
    out = out.strip().removeprefix("<<<").removesuffix(">>>").strip()
    missing = [f for f in freeze if f.lower() in body.text.lower() and f.lower() not in out.lower()]
    return {"text": out, "model": model, "missing_frozen": missing}


class SynIn(BaseModel):
    word: str = Field(min_length=1, max_length=60)
    context: str = Field(default="", max_length=600)


_syn_cache: dict[tuple[str, str], list[str]] = {}


@app.post("/api/synonyms")
def synonyms(body: SynIn):
    word = body.word.strip()
    key = (word.lower(), body.context[-200:])
    if key in _syn_cache:
        return {"word": word, "synonyms": _syn_cache[key]}
    user = f'Target word: "{word}"\nSentence: {body.context or word}'
    try:
        data = ollama.chat_json(_pick(CHECK_MODEL, ollama.list_models()), SYNONYM_SYSTEM, user, SYNONYM_SCHEMA,
                                num_ctx=2048)
    except ollama.OllamaError as e:
        raise HTTPException(502, str(e)) from e
    out, seen = [], {word.lower()}
    for syn in data.get("synonyms", []):
        syn = str(syn).strip()
        if syn and syn.lower() not in seen and len(syn) < 40:
            seen.add(syn.lower())
            out.append(syn[:1].upper() + syn[1:] if word[:1].isupper() else syn)
    _syn_cache[key] = out[:8]
    return {"word": word, "synonyms": out[:8]}


class WordIn(BaseModel):
    word: str = Field(min_length=1, max_length=60)


@app.post("/api/dictionary")
def dictionary_add(body: WordIn):
    return {"dictionary": config.add_word(body.word)}


@app.post("/api/dictionary/remove")
def dictionary_remove(body: WordIn):
    words = [w for w in config.get()["dictionary"] if w.lower() != body.word.strip().lower()]
    config.update(dictionary=words)
    return {"dictionary": words}


if __name__ == "__main__":
    port = int(os.environ.get("WRITER_PORT", "8000"))
    print(f"Writer UI: http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
