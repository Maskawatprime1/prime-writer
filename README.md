<p align="center"><img src="frontend/public/logo.svg" width="96" alt="Prime Writer logo"></p>

# Prime Writer

**An offline grammar checker, rewriter and paraphraser for Windows that works in every app.** Prime Writer underlines mistakes as you type in Chrome, Word, Notepad, chat apps and more, and rewrites text in 8 styles. Everything runs on your own PC: LanguageTool handles grammar rules and a local AI model (Qwen3 via Ollama) handles suggestions and rewrites. No account, no cloud, and your text never leaves your computer.

Created by **Maskawat Al Sium**. © 2026. Free for personal and non-commercial use ([license](#license)).

## Download

Get **PrimeWriter-Setup-<version>.exe** from this repository's **Releases** page and run it. On first launch Prime Writer helps you install Ollama and download the AI model.

## License

Prime Writer is © 2026 Maskawat Al Sium and released under the **[PolyForm Noncommercial License 1.0.0](LICENSE)**.

- ✅ You may use it, study it and change it for personal, educational and other non-commercial purposes.
- ❌ You may not sell it or use it commercially without written permission.
- 📌 Any copy must keep the `Required Notice` (the author's copyright line) and the license.

Prime Writer builds on open-source software that keeps its own licenses. See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

## Install on another Windows PC

Copy **`PrimeWriter-Setup-<version>.exe`** (about 300 MB; you'll find it in the Releases page, or in `dist\installer` after a build) to the other PC and run it.

- **What it installs:** for the current user only, no admin needed: the app, LanguageTool and its own Java. There's nothing else to install by hand. Options: a desktop shortcut and "Start when I sign in". It installs Microsoft WebView2 if it's missing.
- **First launch:** a setup screen offers **Install Ollama** (about 1 GB) and **Download the AI model**, either Qwen3 8B (5.2 GB, best) or Qwen3 4B (2.5 GB, for weaker PCs), each with a progress bar. If Ollama and a model are already there, it skips straight to the editor. Grammar and spelling checks work even before the AI is set up.
- **Requirements:** Windows 10 (1809+) or 11, 64-bit. 16 GB RAM recommended (8 GB with the 4B model). About 9 GB free disk space. An NVIDIA GPU makes the AI fast; without one it runs on the CPU, slower.
- **"Windows protected your PC":** the installer isn't code-signed, so Windows SmartScreen may warn. Click **More info → Run anyway**.
- **Uninstall:** Settings → Apps → Prime Writer. Your settings in `%LOCALAPPDATA%\PrimeWriter` are kept. Ollama and the model are separate; uninstall Ollama on its own if you want.

Rebuild the installer: `powershell -ExecutionPolicy Bypass -File build_installer.ps1 -Version 1.0.1` (needs Inno Setup 6: `winget install JRSoftware.InnoSetup`).

Mac (.dmg) and Android (.apk) aren't available. The parts that work in every app use Windows-only features.

## The editor

Open it from the tray with "Open Writer", or from the **Prime Writer** desktop shortcut.

- **Toolbar** (Docs-style): undo/redo, text styles, bold, italic, underline, strike, highlight, lists, quote, alignment. On the right: serif/sans font, readability highlights, AI suggestions, Check, and the side panel.
- **Page:** a clean, centered writing area. Click an underlined mistake to get a card with fixes, **Rewrite sentence**, **Add to dictionary** and **Ignore**. Double-click a correct word to see synonyms.
- **Select text** to get an AI menu: **Improve**, **Fix**, **Shorten**, **Paraphrase** (any mode), **Synonyms**. Choose **Replace**, **Insert below** or **Try again**.
- **Side panel:**
  - *Suggestions:* a writing score, filters (Correctness / Clarity / Style), and **Accept all corrections**.
  - *Paraphrase:* modes, a how-much-to-change slider, and freeze words.
  - *Stats:* readability, grade level, reading and speaking time.
- **Top bar:** document title, AI and LanguageTool status, New / Copy all / Download .txt, a light/dark/system theme, and Settings.
- **Status bar:** words, characters, reading time, check status and save status. The document is saved automatically.

## Use it anywhere

Start `dist\PrimeWriter\PrimeWriter.exe` (or use the desktop shortcut). A **P** icon appears in the system tray.

### Live underlines (like Grammarly)

1. Type in any text box: Chrome, Edge, Word, Notepad, Outlook, chat apps…
2. Mistakes are underlined: red for spelling, orange for grammar, blue for style. LanguageTool results appear within about 1 s. AI suggestions follow after you pause.
3. Hover over an underlined word to see a card with fixes. Click a fix to replace the word in place.
4. A round button sits in the text box's corner:
   - a **number** means that many issues were found
   - **✓** means no issues
   - grey means it's still checking

   Click the button to open the full panel for the whole text box: check, AI fix, or paraphrase in 8 modes. **Replace in app** swaps the text box's contents.

### More writing tools

| Feature | Where | How |
|---|---|---|
| Personal dictionary | Any suggestion card, Settings | **Add to dictionary** on a spelling card. Manage the words in Settings. |
| English variety | Settings → Language | American, British, Canadian or Australian English (checks and rewrites follow it) |
| Picky mode | Settings → Language | Stricter LanguageTool style and punctuation rules |
| Word count, reading time, readability score | Writer → Stats tab, popup footer | Flesch score, grade level, sentences, speaking time |
| Snippets | Settings → Snippets | Type a trigger such as `;addr` followed by a space, Enter or punctuation, in any app or the Writer |
| Rewrite unclear sentence | Hover card, Writer cards | **Rewrite sentence**, then **Use this** |
| Synonyms | Any app: select or double-click one word. Writer: double-click a word. | Pick a synonym to replace the word |
| Readability highlights | Writer (Readability checkbox); other apps: Settings switch, off by default | Purple dotted lines: passive voice, wordy phrases, weak qualifiers, adverbs. Yellow: long sentences. |
| Paraphrase slider and freeze words | Writer and popup → Paraphrase | **Changes**: Minimal to Max. **Freeze words**: type a word and press Enter to keep it unchanged. |

### Hotkeys (for selected text)

- **Ctrl+Alt+G**: check grammar
- **Ctrl+Alt+P**: paraphrase

A popup opens next to the mouse. Press **Replace in app** (or **Ctrl+Enter**) to paste the result over your selection. **Esc** closes it.

## On/off controls

- **Tray menu → "On in all apps"**: the master switch. The tray icon turns grey when it's off.
- **Tray menu → Settings**:
  - an on/off switch for each app
  - Start with Windows
  - changing the hotkeys
  - the default paraphrase mode
- **Popup → "Turn off in this app"**: a one-click way to turn it off for the current app.

When it's off for an app, the hotkeys aren't registered while that app is in front, so the keys reach the app normally.

Closing a window hides it to the tray. Use **tray → Quit** to stop the app completely.

## Writer window

Open it from the tray with "Open Writer". It's a full editor with:

- live grammar highlights
- a suggestions sidebar
- 8 paraphrase modes (Fix grammar, Standard, Fluent, Formal, Concise, Casual, Academic, Simple) with the changes highlighted

## How it works

- **Copying the selection:** the hotkey sends Ctrl+C to the active app. Your clipboard is restored right away.
- **Replace:** pastes with Ctrl+V, then restores your clipboard again. Only text on the clipboard is kept; an image on the clipboard is overwritten.
- **Checking:** LanguageTool results show instantly, and the AI results follow a few seconds later.
- **Model:** qwen3:8b is the only model installed. It handles checking, rewriting and synonyms, so only one model sits in the 8 GB of VRAM. Rewrites take about 1 s once the model is loaded; the first load takes about 30 s.

### WeChat (and other apps that hide their text boxes)

WeChat 4 (Qt) hides its message box from Windows accessibility, so no app can draw underlines there. Instead, a round **P** button appears on the WeChat window:

1. Type your message and click **P**. Prime Writer copies the message (Ctrl+A, Ctrl+C; your clipboard is restored) and opens the check/paraphrase panel.
2. **Replace in app** pastes the fixed text back over the message. It never presses Enter, so nothing is sent.

**Drag the button** anywhere and it stays there for that app, even when the window moves or resizes. The live button in other apps can be dragged too. Settings → "Floating button position" → **Reset** puts them back.

You can switch this off in Settings → "Prime Writer button in WeChat". The app list is `button_apps` in the settings file. The hotkeys also work in WeChat on selected text.

## Limits

- **Where underlines work:** live underlines need the app to support Windows UI Automation text. Chrome, Edge, Electron apps (Discord, Slack, VS Code, Claude), Notepad and Office do. Apps that draw their own text, such as games, some Java apps and terminals, don't. The hotkeys still work there.
- **What's skipped:** password fields, and anything beyond 6,000 characters.
- **Grammarly:** if Grammarly is also running, you'll see both sets of underlines. Quit Grammarly or turn it off for that app.
- **Administrator apps:** Windows blocks typing into apps running as administrator unless PrimeWriter is also run as administrator.
- Apps that ignore Ctrl+C/Ctrl+V, or games, won't work.
- Microsoft Store apps may all be listed as `applicationframehost`.

## Settings file

Settings are saved in `%LOCALAPPDATA%\PrimeWriter\config.json`.

## Developer notes

```powershell
# Run without building
.venv\Scripts\python -m writer.desktop        # tray app
.venv\Scripts\python -m writer.server         # browser-only, http://127.0.0.1:8000

# Build from source (needs Python 3.13 + uv, Node.js, a JDK 17+, Inno Setup 6)
powershell -ExecutionPolicy Bypass -File scripts\setup_dev.ps1   # venv, npm, LanguageTool, WebView2 bootstrapper
powershell -ExecutionPolicy Bypass -File build_exe.ps1           # dist\PrimeWriter\PrimeWriter.exe
powershell -ExecutionPolicy Bypass -File build_installer.ps1     # dist\installer\PrimeWriter-Setup-<version>.exe

# Work on the UI with live reload (the app must be running for /api)
cd frontend; npm install; npx vite        # http://localhost:5173
```

The exe finds LanguageTool by searching the exe's folder and its parent folders for `tools\LanguageTool-*`. If you move `dist\PrimeWriter`, copy `tools\` next to it, or set `WRITER_HOME` to this project folder.

Environment variables: `WRITER_CHECK_MODEL`, `WRITER_PARAPHRASE_MODEL`, `OLLAMA_HOST`.

Clash note: in fake-IP mode, `ollama pull` fails with "resolves to non-public 198.18.x.x". Add `+.r2.cloudflarestorage.com` to Clash's `fake-ip-filter`.

## Layout

```
shared/ollama.py        Ollama client
writer/server.py        FastAPI API: check, paraphrase, config, apps
writer/languagetool.py  LanguageTool start/stop and checks
writer/prompts.py       Paraphrase modes and the grammar prompt
writer/config.py        Settings (per-app on/off, hotkeys)
writer/win32.py         Hotkeys, clipboard, active app, key input (ctypes)
writer/overlay.py       Live underlines: UI Automation, background checks, hover card, button, synonyms, snippets
writer/readability.py   Hemingway-style rules (passive, wordy, adverbs, long sentences)
writer/static/textstats.js  Word count, reading time, Flesch score
writer/layered.py       Click-through top-most drawing windows (ctypes + Pillow)
writer/desktop.py       Tray, popup, single instance, start with Windows
frontend/src/            React + Tiptap UI (editor, side panel, AI menu, settings)
writer/static/app/      Built UI (generated by build_exe.ps1)
writer/static/          Quick popup and hover card pages
primewriter.py          Exe entry point
build_exe.ps1           PyInstaller build
tools/                  LanguageTool 6.6
```
