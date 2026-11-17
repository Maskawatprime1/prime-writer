"""Regenerate THIRD-PARTY-NOTICES.md from the packages actually shipped in Prime Writer.

Run from the project folder:  .venv\\Scripts\\python scripts\\gen_notices.py
"""
from __future__ import annotations

import json
import re
import subprocess
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Python packages bundled into PrimeWriter.exe (and everything they depend on)
PY_ROOTS = ["fastapi", "uvicorn", "httptools", "websockets", "watchfiles", "python-dotenv", "pyyaml", "httpx",
            "python-multipart", "pywebview", "pystray", "pillow", "comtypes"]
SKIP = {"pyinstaller", "pyinstaller-hooks-contrib", "setuptools", "pip"}
KNOWN = {"clr-loader": "MIT", "pywebview": "BSD-3-Clause", "pystray": "LGPL-3.0"}


def _norm(n: str) -> str:
    return re.sub(r"[-_.]+", "-", n).lower()


def _license(d) -> str:
    m = d.metadata
    if KNOWN.get(_norm(m["Name"])):
        return KNOWN[_norm(m["Name"])]
    if m.get("License-Expression"):
        return m["License-Expression"]
    text = (m.get("License") or "").strip()
    if text and len(text) < 60 and "\n" not in text:
        return text
    cls = [c.split("::")[-1].strip() for c in (m.get_all("Classifier") or []) if c.startswith("License ::")]
    return ", ".join(cls) or "see package"


def _url(d) -> str:
    m = d.metadata
    if m.get("Home-page"):
        return m["Home-page"]
    urls = [u.partition(",") for u in (m.get_all("Project-URL") or [])]
    for k, _, v in urls:
        if k.strip().lower() in ("homepage", "source", "repository", "source code", "home"):
            return v.strip()
    return urls[0][2].strip() if urls else ""


def python_packages() -> list[dict]:
    seen, stack, rows = set(), list(PY_ROOTS), []
    while stack:
        n = _norm(stack.pop())
        if n in seen or n in SKIP:
            continue
        try:
            d = metadata.distribution(n)
        except metadata.PackageNotFoundError:
            continue
        seen.add(n)
        rows.append({"name": d.metadata["Name"], "version": d.version, "license": _license(d), "url": _url(d)})
        for req in d.requires or []:
            if "extra ==" in req and not (n == "uvicorn" and "standard" in req):
                continue
            stack.append(re.split(r"[ ;<>=!\[~(]", req, maxsplit=1)[0])
    return sorted(rows, key=lambda r: r["name"].lower())


def npm_packages() -> list[dict]:
    fe = ROOT / "frontend"
    tree = json.loads(subprocess.run("npm ls --omit=dev --all --json", cwd=fe, capture_output=True, text=True, shell=True).stdout)
    out: dict[str, dict] = {}

    def walk(deps):
        for name, info in (deps or {}).items():
            key = f"{name}@{info.get('version')}"
            if key in out:
                continue
            pj = json.loads((fe / "node_modules" / name / "package.json").read_text(encoding="utf-8"))
            lic = pj.get("license") if isinstance(pj.get("license"), str) else (pj.get("license") or {}).get("type", "")
            repo = pj.get("repository")
            repo = repo.get("url") if isinstance(repo, dict) else (repo or pj.get("homepage", ""))
            out[key] = {"name": name, "version": info.get("version"), "license": lic or "see package",
                        "url": (repo or "").replace("git+", "").removesuffix(".git")}
            walk(info.get("dependencies"))

    walk(tree.get("dependencies"))
    return sorted(out.values(), key=lambda r: r["name"])


def table(rows: list[dict]) -> str:
    lines = ["| Component | Version | License | Source |", "|---|---|---|---|"]
    lines += [f"| {r['name']} | {r['version']} | {r['license']} | {r['url']} |" for r in rows]
    return "\n".join(lines)


HEADER = """# Third-party notices

Prime Writer is © 2026 Maskawat Al Sium and licensed under the PolyForm Noncommercial License 1.0.0 (see `LICENSE`).

It is built with, ships with, or downloads the open-source software below. Each component stays under its own
license and belongs to its respective authors; Prime Writer's license does not apply to them.

## Shipped with the installer

| Component | License | Notes |
|---|---|---|
| LanguageTool 6.6 | LGPL-2.1-or-later | Grammar engine, shipped unmodified in `tools\\LanguageTool-6.6` with its own `COPYING.txt` and `third-party-licenses`. Source: https://github.com/languagetool-org/languagetool. You may replace or modify this component. |
| OpenJDK runtime 21 (Microsoft Build of OpenJDK) | GPL-2.0 with Classpath Exception | Trimmed Java runtime in `tools\\jre` (made with `jlink`); full license texts in `tools\\jre\\legal`. Source: https://github.com/microsoft/openjdk |
| Python 3.13 | PSF-2.0 | Runtime embedded in `PrimeWriter.exe`. https://www.python.org |
| PyInstaller bootloader | GPL-2.0 with bootloader exception | Starts `PrimeWriter.exe`. https://github.com/pyinstaller/pyinstaller |
| Microsoft Edge WebView2 bootstrapper | Microsoft redistributable | Installs the WebView2 runtime only if missing. https://developer.microsoft.com/microsoft-edge/webview2 |

## Downloaded on first launch (not included in the installer)

| Component | License | Source |
|---|---|---|
| Ollama | MIT | https://github.com/ollama/ollama |
| Qwen3 language models (8B / 4B) | Apache-2.0 | https://huggingface.co/Qwen |
"""


def main() -> None:
    text = HEADER
    text += "\n## Python packages inside PrimeWriter.exe\n\n" + table(python_packages()) + "\n"
    text += ("\npystray is LGPL-3.0: it is used unmodified, and you may replace it "
             "(source: https://github.com/moses-palmer/pystray).\n")
    text += "\n## JavaScript packages in the user interface\n\n" + table(npm_packages()) + "\n"
    (ROOT / "THIRD-PARTY-NOTICES.md").write_text(text, encoding="utf-8")
    print("wrote THIRD-PARTY-NOTICES.md")


if __name__ == "__main__":
    main()
