<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="frontend/public/brand/logo-full-light.png">
    <img src="frontend/public/brand/logo-full.png" width="340" alt="Prime Writer">
  </picture>
</p>

# Prime Writer

Prime Writer is a grammar checker and paraphraser for Windows that runs entirely on your own computer. It underlines mistakes while you type in most apps (Word, Notepad, web browsers and others), and it can rewrite text in eight different styles.

Grammar and spelling rules come from LanguageTool. The suggestions and rewrites come from a local AI model (Qwen3, run through Ollama). You don't need an account, and your text never leaves your PC.

I built it because I wanted something like Grammarly and QuillBot that works offline. It's free to use, but not for selling. See the license section below.

## Download

Download `PrimeWriter-Setup-1.0.0.exe` from the [latest release](https://github.com/Maskawatprime1/prime-writer/releases/latest) and run it.

The installer isn't code-signed yet, so Windows may show "Windows protected your PC". Click More info, then Run anyway.

The first time you open Prime Writer, it asks to install Ollama (about 1 GB) and download an AI model. You can pick Qwen3 8B (5.2 GB, better results) or Qwen3 4B (2.5 GB, for slower PCs). Grammar and spelling checks work before the AI is set up.

### What you need

- Windows 10 (version 1809 or later) or Windows 11, 64-bit
- 16 GB of RAM, or 8 GB if you use the 4B model
- About 9 GB of free disk space
- An NVIDIA GPU makes the AI much faster, but it also runs on the CPU

The installer doesn't need admin rights. It includes LanguageTool and its own Java runtime, so there's nothing else to install by hand. If Microsoft WebView2 is missing, it installs that too.

To uninstall, go to Settings → Apps → Prime Writer. Your settings in `%LOCALAPPDATA%\PrimeWriter` stay on the PC. Ollama is a separate program, so uninstall it on its own if you don't need it anymore.

There's no Mac or Android version. The parts that work inside other apps rely on Windows features.

## What it does

### In other apps

Type in a text box and mistakes get underlined: red for spelling, orange for grammar, blue for style. LanguageTool results show up within about a second, and the AI adds its own suggestions after you stop typing for a moment.

Hover over an underlined word to see the fixes. Clicking one replaces the word right where it is. Each text box also gets a small round button in its corner that shows how many issues it found. Click it to check or paraphrase the whole text box at once.

You can also select text anywhere and use a hotkey:

- Ctrl+Alt+G checks the selection
- Ctrl+Alt+P paraphrases it

A small window opens next to your mouse. Press Ctrl+Enter (or click Replace in app) to put the result back, or Esc to close it.

### The editor

Prime Writer also has its own editor. Open it from the tray icon or the desktop shortcut. It has:

- a toolbar for headings, bold, italic, lists, quotes and alignment
- underlined mistakes you can click to fix, ignore, or add to your dictionary
- an AI menu on selected text: Improve, Fix, Shorten, Paraphrase, Synonyms
- a side panel with all suggestions and a writing score, a paraphrase tab, and a stats tab with readability, grade level and reading time
- light and dark themes, and your document is saved automatically

### Other features

- 8 paraphrase modes: Fix grammar, Standard, Fluent, Formal, Concise, Casual, Academic and Simple, with a slider for how much to change
- "Freeze words" to keep certain words unchanged when paraphrasing
- A personal dictionary for names and terms you use often
- American, British, Canadian or Australian English
- Snippets: type something like `;addr` and it expands into your saved text
- Synonyms when you double-click a word
- Readability highlights for passive voice, wordy phrases and long sentences (off by default in other apps)
- Turn it off for specific apps, or everywhere, from Settings or the tray menu

## Limits

- Underlines only work in apps that expose their text to Windows accessibility. Chrome, Edge, Office, Notepad and most Electron apps do. Games, terminals and some Java apps don't, but the hotkeys still work there.
- WeChat hides its message box, so instead of underlines it gets a round P button. Click it to check what you've typed, then Replace. It never presses Enter, so nothing gets sent by accident. You can drag the button wherever you like.
- If Grammarly is running too, you'll see both sets of underlines. Turn one of them off for that app.
- It can't type into apps running as administrator unless Prime Writer also runs as administrator.
- Password fields are always skipped, and so is text longer than 6,000 characters.
- Copy and paste are used to replace text. Your clipboard is restored afterwards, but only if it held text.

## License

Prime Writer is © 2026 Maskawat Al Sium, released under the [PolyForm Noncommercial License 1.0.0](LICENSE).

You can use it, study it and change it for personal or other non-commercial purposes. You can't sell it or use it commercially without my written permission. Any copy has to keep the license and the "Required Notice" line with my name.

Prime Writer uses open-source projects that keep their own licenses, including LanguageTool, OpenJDK, Ollama, Qwen, React and Tiptap. The full list is in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

## Building from source

You'll need Python 3.13 with uv, Node.js, a JDK 17 or newer, and Inno Setup 6 (`winget install JRSoftware.InnoSetup`).

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_dev.ps1   # Python env, npm packages, LanguageTool, WebView2 bootstrapper
powershell -ExecutionPolicy Bypass -File build_exe.ps1           # dist\PrimeWriter\PrimeWriter.exe
powershell -ExecutionPolicy Bypass -File build_installer.ps1     # dist\installer\PrimeWriter-Setup-<version>.exe
```

To run it without building:

```powershell
.venv\Scripts\python -m writer.desktop    # tray app
.venv\Scripts\python -m writer.server     # editor only, at http://127.0.0.1:8000
cd frontend; npx vite                     # UI with live reload (keep the app running for the API)
```

The version number lives in `writer/__init__.py`. You can change the AI models with the `WRITER_CHECK_MODEL` and `WRITER_PARAPHRASE_MODEL` environment variables, and point to another Ollama with `OLLAMA_HOST`.

### Project layout

```
writer/server.py        API: checks, paraphrasing, settings
writer/overlay.py       underlines and suggestion cards in other apps
writer/desktop.py       tray icon, quick popup, start with Windows
writer/languagetool.py  starts and talks to LanguageTool
writer/readability.py   passive voice, wordy phrases, long sentences
writer/setup.py         first-run Ollama and model download
frontend/src/           the editor UI (React + Tiptap)
installer/              Inno Setup script
scripts/                build helpers, logo and license notice generators
```
