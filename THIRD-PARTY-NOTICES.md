# Third-party notices

Prime Writer is © 2026 Maskawat Al Sium and licensed under the PolyForm Noncommercial License 1.0.0 (see `LICENSE`).

It is built with, ships with, or downloads the open-source software below. Each component stays under its own
license and belongs to its respective authors; Prime Writer's license does not apply to them.

## Shipped with the installer

| Component | License | Notes |
|---|---|---|
| LanguageTool 6.6 | LGPL-2.1-or-later | Grammar engine, shipped unmodified in `tools\LanguageTool-6.6` with its own `COPYING.txt` and `third-party-licenses`. Source: https://github.com/languagetool-org/languagetool. You may replace or modify this component. |
| OpenJDK runtime 21 (Microsoft Build of OpenJDK) | GPL-2.0 with Classpath Exception | Trimmed Java runtime in `tools\jre` (made with `jlink`); full license texts in `tools\jre\legal`. Source: https://github.com/microsoft/openjdk |
| Python 3.13 | PSF-2.0 | Runtime embedded in `PrimeWriter.exe`. https://www.python.org |
| PyInstaller bootloader | GPL-2.0 with bootloader exception | Starts `PrimeWriter.exe`. https://github.com/pyinstaller/pyinstaller |
| Microsoft Edge WebView2 bootstrapper | Microsoft redistributable | Installs the WebView2 runtime only if missing. https://developer.microsoft.com/microsoft-edge/webview2 |

## Downloaded on first launch (not included in the installer)

| Component | License | Source |
|---|---|---|
| Ollama | MIT | https://github.com/ollama/ollama |
| Qwen3 language models (8B / 4B) | Apache-2.0 | https://huggingface.co/Qwen |

## Python packages inside PrimeWriter.exe

| Component | Version | License | Source |
|---|---|---|---|
| annotated-doc | 0.0.6 | MIT | https://github.com/fastapi/annotated-doc |
| annotated-types | 0.8.0 | MIT | https://github.com/annotated-types/annotated-types |
| anyio | 4.16.0 | MIT | https://github.com/agronholm/anyio |
| bottle | 0.13.4 | MIT | http://bottlepy.org/ |
| certifi | 2026.10.23 | MPL-2.0 | https://github.com/certifi/python-certifi |
| cffi | 2.1.1 | MIT-0 | https://github.com/python-cffi/cffi |
| click | 8.5.1 | BSD-3-Clause | https://github.com/pallets/click/ |
| clr_loader | 0.3.1 | MIT | https://github.com/pythonnet/clr-loader |
| comtypes | 1.5.0 | MIT | https://github.com/enthought/comtypes |
| fastapi | 0.163.1 | MIT | https://github.com/fastapi/fastapi |
| h11 | 0.16.0 | MIT | https://github.com/python-hyper/h11 |
| httpcore | 1.0.9 | BSD-3-Clause | https://www.encode.io/httpcore/ |
| httptools | 0.9.0 | MIT | https://github.com/MagicStack/httptools |
| httpx | 0.28.1 | BSD-3-Clause | https://github.com/encode/httpx |
| idna | 3.20 | BSD-3-Clause | https://github.com/kjd/idna |
| opentelemetry-api | 1.45.2 | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api |
| pillow | 13.0.0 | MIT-CMU | https://python-pillow.org |
| proxy_tools | 0.1.0 | MIT | http://github.com/jtushman/proxy_tools |
| pycparser | 3.12 | BSD-3-Clause | https://github.com/eliben/pycparser |
| pydantic | 2.14.3 | MIT | https://github.com/pydantic/pydantic |
| pydantic_core | 2.50.4 | MIT | https://github.com/pydantic/pydantic |
| pystray | 0.19.5 | LGPL-3.0 | https://github.com/moses-palmer/pystray |
| python-dotenv | 1.2.4 | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| python-multipart | 0.0.34 | Apache-2.0 | https://github.com/Kludex/python-multipart |
| pythonnet | 3.2.1 | MIT | https://pythonnet.github.io/ |
| pywebview | 6.2.1 | BSD-3-Clause | https://pywebview.flowrl.com/ |
| PyYAML | 6.0.3 | MIT | https://pyyaml.org/ |
| six | 1.17.0 | MIT | https://github.com/benjaminp/six |
| starlette | 1.10.0 | BSD-3-Clause | https://github.com/Kludex/starlette |
| typing-inspection | 0.4.5 | MIT | https://github.com/pydantic/typing-inspection |
| typing_extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |
| uvicorn | 0.54.0 | BSD-3-Clause | https://uvicorn.dev/ |
| watchfiles | 1.3.0 | MIT | https://github.com/samuelcolvin/watchfiles |
| websockets | 17.4 | BSD-3-Clause | https://github.com/python-websockets/websockets |

pystray is LGPL-3.0: it is used unmodified, and you may replace it (source: https://github.com/moses-palmer/pystray).

## JavaScript packages in the user interface

| Component | Version | License | Source |
|---|---|---|---|
| @floating-ui/core | 1.8.0 | MIT | https://github.com/floating-ui/floating-ui |
| @floating-ui/dom | 1.8.0 | MIT | https://github.com/floating-ui/floating-ui |
| @floating-ui/utils | 0.2.12 | MIT | https://github.com/floating-ui/floating-ui |
| @tiptap/core | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-blockquote | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-bold | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-bubble-menu | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-bullet-list | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-code | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-code-block | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-document | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-dropcursor | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-floating-menu | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-gapcursor | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-hard-break | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-heading | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-highlight | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-horizontal-rule | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-italic | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-link | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-list | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-list-item | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-list-keymap | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-ordered-list | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-paragraph | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-strike | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-text | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-text-align | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extension-underline | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/extensions | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/pm | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/react | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @tiptap/starter-kit | 3.34.0 | MIT | https://github.com/ueberdosis/tiptap |
| @types/react | 19.3.0 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/react-dom | 19.3.0 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/use-sync-external-store | 0.0.6 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| fast-equals | 5.4.5 | MIT | https://github.com/planttheidea/fast-equals |
| linkifyjs | 4.4.0 | MIT | https://github.com/nfrasser/linkifyjs |
| lucide-react | 1.74.0 | ISC | https://github.com/lucide-icons/lucide |
| react | 19.3.1 | MIT | https://github.com/react/react |
| react-dom | 19.3.1 | MIT | https://github.com/react/react |
| use-sync-external-store | 1.7.0 | MIT | https://github.com/react/react |
