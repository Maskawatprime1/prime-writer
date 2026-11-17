"""Live underlines in any app, like Grammarly for Windows.

Uses Windows UI Automation to read the focused text box, checks it in the background
(LanguageTool first, then AI), draws click-through underlines over the errors, shows a
suggestion card on hover, and puts a floating button on the text box that opens the panel.
"""
from __future__ import annotations

import ctypes
import queue
import threading
import time
from ctypes import wintypes as wt

import comtypes
import comtypes.client
from PIL import Image, ImageDraw, ImageFont

from writer import config, win32
from writer.brand import make_logo
from writer.layered import LayeredWindow

comtypes.client.GetModule("UIAutomationCore.dll")
from comtypes.gen import UIAutomationClient as UIA  # noqa: E402

TEXT_PATTERN, VALUE_PATTERN, TEXT_PATTERN2 = 10014, 10002, 10024
CT_EDIT, CT_DOCUMENT = 50004, 50030
EP_START, EP_END, UNIT_CHAR = 0, 1, 0
MAX_CHARS = 6000
WM_APP = 0x8000
COLORS = {"spelling": (214, 56, 59, 235), "grammar": (226, 132, 37, 235), "style": (47, 111, 222, 220),
          "clarity": (138, 79, 216, 230), "sentence": (224, 176, 32, 190)}
WORD_RE = __import__("re").compile(r"^[^\W\d_][\w'’-]{1,29}$")
DELIMS = " \t\r\n.,!?;:)"
TICK_MS = 150
DEBOUNCE = 0.7        # seconds of no typing before LanguageTool runs
AI_DEBOUNCE = 1.5     # seconds of no typing before the AI check runs


@__import__("functools").lru_cache(maxsize=16)
def _logo(size: int, on: bool = True) -> Image.Image:
    return make_logo(size, "circle", on=on)


def _font(size: int):
    try:
        return ImageFont.truetype("segoeuib.ttf", size)
    except OSError:
        return ImageFont.load_default()


class Field:
    """The text box that currently has keyboard focus."""

    def __init__(self, el, tp, hwnd: int, exe: str):
        self.el, self.tp, self.hwnd, self.exe = el, tp, hwnd, exe
        self.text = ""
        self.changed_at = 0.0
        self.checked = {"lt": None, "ai": None}  # text each phase last ran on
        self.issues: list[dict] = []
        self.checking = {"lt": False, "ai": False}


class Overlay(threading.Thread):
    def __init__(self, desk):
        super().__init__(daemon=True, name="overlay")
        self.desk = desk
        self.tid = 0
        self.field: Field | None = None
        self.actions: queue.Queue = queue.Queue()
        self.ignored: set[tuple[str, str]] = set()
        self.hover = (None, 0)          # (issue id, ticks hovered)
        self.card_issue: dict | None = None
        self.card_left_at = 0.0
        self._ids = 0
        self.sel = (None, 0)            # (selected word, ticks stable)
        self.sel_shown = None           # word whose synonyms card is showing
        self.rewrite = None             # {"range", "source", "text"} for the card's sentence rewrite
        self.fallback_hwnd = 0          # window showing the fallback button (apps like WeChat)
        self.badge_anchor = None        # ("win"|"field", exe, (x, y)) the button's position is relative to

    # ---------- thread plumbing ----------
    def post(self, fn, *args, wait: bool = False):
        """Run fn on the overlay thread (UI Automation objects live there)."""
        done = threading.Event() if wait else None
        box = {}

        def job():
            try:
                box["r"] = fn(*args)
            finally:
                if done:
                    done.set()

        self.actions.put(job)
        if self.tid:
            win32.user32.PostThreadMessageW(self.tid, WM_APP, 0, 0)
        if done:
            done.wait(5)
            return box.get("r")

    def stop(self):
        if self.tid:
            win32.user32.PostThreadMessageW(self.tid, win32.WM_QUIT, 0, 0)

    def run(self):
        comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
        self.tid = win32.kernel32.GetCurrentThreadId()
        self.uia = comtypes.client.CreateObject(UIA.CUIAutomation8, interface=UIA.IUIAutomation)
        try:  # don't hang on unresponsive apps
            self.uia.QueryInterface(UIA.IUIAutomation2).ConnectionTimeout = 1500
            self.uia.QueryInterface(UIA.IUIAutomation2).TransactionTimeout = 1500
        except Exception:  # noqa: BLE001
            pass
        self.lines = LayeredWindow(click_through=True)
        self.badge = LayeredWindow(click_through=False, on_click=lambda _h: self.open_panel(),
                                   on_drag_start=self.hide_card, on_drag_end=self._badge_moved)
        win32.user32.SetTimer(None, 0, TICK_MS, None)
        msg = win32.MSG()
        while win32.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message in (win32.WM_TIMER, WM_APP):
                while not self.actions.empty():
                    try:
                        self.actions.get_nowait()()
                    except Exception as e:  # noqa: BLE001
                        print("overlay action error:", e)
                try:
                    self.tick()
                except comtypes.COMError:
                    self.clear()
                except Exception as e:  # noqa: BLE001
                    print("overlay tick error:", e)
                    self.clear()
            else:
                win32.user32.TranslateMessage(ctypes.byref(msg))
                win32.user32.DispatchMessageW(ctypes.byref(msg))

    # ---------- focus tracking ----------
    def clear(self):
        self.field = None
        self.fallback_hwnd = 0
        self.lines.hide()
        self.badge.hide()
        self.hide_card()

    # ---------- fallback button for apps without accessible text boxes (WeChat) ----------
    def _caret_on_screen(self, hwnd: int):
        class GTI(ctypes.Structure):
            _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD), ("hwndActive", wt.HWND), ("hwndFocus", wt.HWND),
                        ("hwndCapture", wt.HWND), ("hwndMenuOwner", wt.HWND), ("hwndMoveSize", wt.HWND),
                        ("hwndCaret", wt.HWND), ("rcCaret", wt.RECT)]
        g = GTI(cbSize=ctypes.sizeof(GTI))
        tid = win32.user32.GetWindowThreadProcessId(hwnd, None)
        if not win32.user32.GetGUIThreadInfo(tid, ctypes.byref(g)) or not g.hwndCaret:
            return None
        pt = wt.POINT(g.rcCaret.left, g.rcCaret.bottom)
        win32.user32.ClientToScreen(g.hwndCaret, ctypes.byref(pt))
        return pt.x, pt.y

    def show_fallback(self, hwnd: int):
        self.fallback_hwnd = hwnd
        r = wt.RECT()
        win32.user32.GetWindowRect(hwnd, ctypes.byref(r))
        if r.right - r.left < 200:
            return self.badge.hide()
        size = 34
        exe = win32.process_exe(win32._pid_of(hwnd))
        self.badge_anchor = ("win", exe, (r.right, r.bottom))
        saved = config.get().get("button_pos", {}).get(f"win:{exe}")
        caret = None if saved else self._caret_on_screen(hwnd)
        if saved:  # where the user dragged it, relative to the window's bottom-right corner
            x = min(max(r.left, r.right + saved[0]), r.right - size)
            y = min(max(r.top, r.bottom + saved[1]), r.bottom - size)
        elif caret:  # follow the text cursor, like the live button
            x, y = min(caret[0] + 10, r.right - size - 8), caret[1] - size
        else:  # bottom of the window, left of WeChat's Send button
            x, y = r.right - size - 150, r.bottom - size - 18
        self.badge.update(_logo(size), x, y)

    def open_fallback_panel(self):
        """Copy the message being written (Ctrl+A, Ctrl+C), open the panel; Replace pastes over it."""
        hwnd, exe = self.fallback_hwnd, win32.process_exe(win32._pid_of(self.fallback_hwnd))
        if not hwnd:
            return
        win32.activate(hwnd)
        time.sleep(0.08)
        saved = win32.get_clipboard()
        before = win32.clipboard_seq()
        win32.send_ctrl("a")
        time.sleep(0.06)
        win32.send_ctrl("c")
        text = None
        for _ in range(30):
            time.sleep(0.02)
            if win32.clipboard_seq() != before:
                time.sleep(0.03)
                text = win32.get_clipboard()
                break
        if text is not None and saved is not None:
            win32.set_clipboard(saved)
        win32.send_key(0x23)  # End: drop the select-all, cursor back at the end

        def select_all():
            win32.activate(hwnd)
            time.sleep(0.08)
            win32.send_ctrl("a")
            time.sleep(0.05)

        self.desk.open_panel((text or "").replace("\r\n", "\n"), exe, hwnd, lambda: self.post(select_all, wait=True))

    def _editable(self, el) -> bool:
        if el.CurrentIsPassword:
            return False
        ct = el.CurrentControlType
        vp = el.GetCurrentPattern(VALUE_PATTERN)
        readonly = None
        if vp:
            readonly = bool(vp.QueryInterface(UIA.IUIAutomationValuePattern).CurrentIsReadOnly)
        if ct == CT_EDIT:
            return readonly is not True
        if ct == CT_DOCUMENT:
            if readonly is False:
                return True
            tp2 = el.GetCurrentPattern(TEXT_PATTERN2)
            if tp2:
                active, _ = tp2.QueryInterface(UIA.IUIAutomationTextPattern2).GetCaretRange()
                return bool(active)
        return False

    def _focused_field(self, fg_hwnd: int, exe: str) -> Field | None:
        el = self.uia.GetFocusedElement()
        if el is None:
            return None
        if self.field and self.uia.CompareElements(el, self.field.el):
            return self.field
        tp = el.GetCurrentPattern(TEXT_PATTERN)
        if not tp or not self._editable(el):
            return None
        return Field(el, tp.QueryInterface(UIA.IUIAutomationTextPattern), fg_hwnd, exe)

    # ---------- main loop ----------
    def tick(self):
        cfg = config.get()
        if not cfg["enabled"]:
            return self.clear()
        fg, exe, _, pid = win32.foreground()
        if pid == win32.OWN_PID:
            return  # our card/popup is in front: keep everything as is
        if not exe or not config.app_enabled(exe):
            return self.clear()
        button_app = cfg.get("fallback_button", True) and exe in cfg.get("button_apps", [])
        field = self._focused_field(fg, exe) if cfg.get("live", True) and not button_app else None
        if field is not self.field or (field and self.fallback_hwnd):
            self.clear()
            self.field = field
        if not field:
            # Apps like WeChat hide their text boxes from Windows; offer the button instead of underlines.
            if button_app:
                self.show_fallback(fg)
            elif self.fallback_hwnd:
                self.clear()
            return
        f = field
        text = f.tp.DocumentRange.GetText(MAX_CHARS + 1)
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS]
        now = time.time()
        if text != f.text:
            first = not f.text and not f.changed_at
            f.text, f.changed_at = text, now
            self.hide_card()
            if not first and cfg.get("snippets") and self._maybe_snippet(f, cfg["snippets"]):
                return
            # keep underlines whose words are still there (they move with the text)
            f.issues = [i for i in f.issues if self._range_text(i) == i["original"]]
        idle = now - f.changed_at
        if text.strip():
            if not f.checking["lt"] and f.checked["lt"] != text and idle > DEBOUNCE:
                self._start_check(f, text, ai=False)
            elif (cfg.get("live_ai", True) and not f.checking["ai"] and f.checked["ai"] != text
                  and f.checked["lt"] == text and idle > AI_DEBOUNCE):
                self._start_check(f, text, ai=True)
        self.draw(f)
        if cfg.get("synonyms_on_select", True):
            self.track_selection(f)
        self.track_hover(f)

    def _range_text(self, issue) -> str:
        try:
            return issue["range"].GetText(len(issue["original"]) + 1)
        except comtypes.COMError:
            return ""

    # ---------- checking ----------
    def _start_check(self, f: Field, text: str, ai: bool):
        f.checking["ai" if ai else "lt"] = True

        def work():
            from writer import server
            try:
                readable = bool(config.get().get("live_readability"))
                res = server.check(server.CheckIn(text=text, use_lt=True, use_llm=ai, readability=readable))
                issues = res["issues"]
            except Exception as e:  # noqa: BLE001
                print("live check error:", e)
                issues = None
            self.post(self._apply_result, f, text, ai, issues)

        threading.Thread(target=work, daemon=True).start()

    def _apply_result(self, f: Field, text: str, ai: bool, issues):
        f.checking["ai" if ai else "lt"] = False
        f.checked["ai" if ai else "lt"] = text
        if f is not self.field or issues is None or f.text != text:
            return
        if not ai and f.checked["ai"] == text:
            return  # AI result (which includes LanguageTool) already shown
        mapped = []
        for it in issues:
            original = text[it["offset"]: it["offset"] + it["length"]]
            if not original.strip() or (it["message"], original) in self.ignored:
                continue
            rng = self._make_range(f, it["offset"], it["length"], original)
            if rng is None:
                continue
            self._ids += 1
            mapped.append({**it, "id": self._ids, "original": original, "range": rng, "rects": []})
        mapped.sort(key=lambda i: i.get("scope") == "sentence")  # word-level issues win on hover
        f.issues = mapped

    def _make_range(self, f: Field, offset: int, length: int, original: str):
        try:
            r = f.tp.DocumentRange.Clone()
            r.MoveEndpointByRange(EP_END, r, EP_START)
            if offset:
                r.Move(UNIT_CHAR, offset)
            r.MoveEndpointByUnit(EP_END, UNIT_CHAR, length)
            got = r.GetText(length + 1)
            if got == original:
                return r
            # Some apps count line breaks differently; search nearby.
            for delta in (-1, 1, -2, 2):
                r2 = f.tp.DocumentRange.Clone()
                r2.MoveEndpointByRange(EP_END, r2, EP_START)
                if offset + delta > 0:
                    r2.Move(UNIT_CHAR, offset + delta)
                r2.MoveEndpointByUnit(EP_END, UNIT_CHAR, length)
                if r2.GetText(length + 1) == original:
                    return r2
        except comtypes.COMError:
            pass
        return None

    # ---------- drawing ----------
    def draw(self, f: Field):
        fr = f.el.CurrentBoundingRectangle
        L, T, R, B = fr.left, fr.top, fr.right, fr.bottom
        if R - L < 20 or B - T < 8:
            self.lines.hide(); self.badge.hide()
            return
        pad = 6
        img = Image.new("RGBA", (R - L + 2 * pad, B - T + 2 * pad), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        drawn = 0
        for it in f.issues:
            try:
                raw = it["range"].GetBoundingRectangles()
            except comtypes.COMError:
                raw = ()
            rects = []
            for k in range(0, len(raw) - 3, 4):
                x, y, w, h = (int(v) for v in raw[k:k + 4])
                if w <= 0 or h <= 0 or x + w < L or x > R or y + h < T or y > B:
                    continue  # scrolled out of view
                rects.append((x, y, w, h))
            it["rects"] = rects
            sentence = it.get("scope") == "sentence"
            color = COLORS["sentence"] if sentence else COLORS.get(it["kind"], COLORS["grammar"])
            for x, y, w, h in rects:
                lx, ly = x - L + pad, y + h - T + pad
                if sentence:
                    d.rectangle((lx, ly + 1, lx + w, ly + 1), fill=color)  # thin line under the whole sentence
                elif it["kind"] == "clarity":
                    for dx in range(0, w, 4):  # dotted
                        d.rectangle((lx + dx, ly - 1, lx + min(dx + 1, w), ly), fill=color)
                else:
                    d.rectangle((lx, ly - 1, lx + w, ly), fill=color)  # 2 px underline
                drawn += 1
        if drawn:
            self.lines.update(img, L - pad, T - pad)
        else:
            self.lines.hide()
        self.draw_badge(f, R, B, T)

    def draw_badge(self, f: Field, R: int, B: int, T: int):
        size = 26
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        n = len(f.issues)
        if f.checking["lt"] or not f.text.strip() or f.checked["lt"] != f.text:
            fill, label = None, ""
        elif n:
            fill, label = (214, 56, 59, 245), str(n) if n < 100 else "99"
        else:
            fill, label = (46, 158, 74, 245), "✓"
        if fill is None:
            img = _logo(size)
        else:
            d.ellipse((1, 1, size - 2, size - 2), fill=fill)
            d.text((size / 2, size / 2), label, fill="white", font=_font(13 if len(label) < 2 else 11), anchor="mm")
        self.badge_anchor = ("field", f.exe, (R, B))
        saved = config.get().get("button_pos", {}).get(f"field:{f.exe}")
        if saved:
            x = min(max(R + saved[0], R - 2000), R + 120)
            y = min(max(B + saved[1], T - 120), B + 120)
        else:
            x = R - size - 6
            y = B - size - 4 if B - T > size + 8 else T + (B - T - size) // 2
        self.badge.update(img, x, y)

    # ---------- hover card ----------
    def track_hover(self, f: Field):
        cx, cy = win32.cursor_pos()
        over = None
        for it in f.issues:
            for x, y, w, h in it["rects"]:
                if x - 2 <= cx <= x + w + 2 and y - 2 <= cy <= y + h + 6:
                    over = it
                    break
            if over:
                break
        if self.card_issue:
            on_card = self.desk.cursor_on_card(cx, cy)
            keep_syn = self.card_issue.get("kind") == "synonyms" and self.sel[0] == self.card_issue["original"]
            if over is self.card_issue or on_card or keep_syn:
                self.card_left_at = 0.0
            elif not self.card_left_at:
                self.card_left_at = time.time()
            elif time.time() - self.card_left_at > 0.6:
                self.hide_card()
        hid, ticks = self.hover
        if over is not None:
            self.hover = (over["id"], ticks + 1 if hid == over["id"] else 1)
            if self.hover[1] >= 2 and self.card_issue is not over and not (
                    self.card_issue and self.desk.cursor_on_card(cx, cy)):
                self.show_card(over)
        else:
            self.hover = (None, 0)

    def show_card(self, it: dict):
        self.card_issue = it
        self.card_left_at = 0.0
        self.rewrite = None
        sentence = it.get("scope") == "sentence"
        x, y, w, h = it["rects"][-1]
        self.desk.show_card({
            "mode": "issue",
            "message": it["message"], "replacements": [] if sentence else it["replacements"][:4],
            "kind": "sentence" if sentence else it["kind"],
            "label": "Long sentence" if sentence else (it.get("sub") or it["kind"]).replace("-", " ").capitalize(),
            "source": it["source"], "original": "" if sentence else it["original"],
            "exe": self.field.exe if self.field else "",
            "canAddWord": it["kind"] == "spelling" and bool(WORD_RE.match(it["original"])),
            "canRewrite": sentence or it.get("sub") in ("passive", "adverb", "qualifier", "wordy") or it["source"] == "AI",
        }, (x, y, w, h))

    def hide_card(self):
        if self.card_issue is not None:
            self.card_issue = None
            self.rewrite = None
            self.desk.hide_card()

    # ---------- actions from the card / badge ----------
    def apply_fix(self, r: int):
        it, f = self.card_issue, self.field
        self.hide_card()
        if not it or not f:
            return
        rep = it["replacements"][r] if r < len(it["replacements"]) else None
        if rep is None:
            return
        if self._range_text(it) != it["original"]:
            return  # text changed under us
        self._replace_range(f, it["range"], rep)
        f.issues = [i for i in f.issues if i is not it]

    def ignore_current(self):
        it, f = self.card_issue, self.field
        self.hide_card()
        if it and f:
            self.ignored.add((it["message"], it["original"]))
            f.issues = [i for i in f.issues if i is not it]

    def open_panel(self):
        """Floating button: open the check/paraphrase panel for the whole text box."""
        f = self.field
        if not f:
            if self.fallback_hwnd:
                self.open_fallback_panel()
            return
        self.hide_card()
        doc = f.tp.DocumentRange

        def select_all():
            win32.activate(f.hwnd)
            time.sleep(0.05)
            doc.Select()
            time.sleep(0.05)

        self.desk.open_panel(f.text, f.exe, f.hwnd, lambda: self.post(select_all, wait=True))

    # ---------- personal dictionary ----------
    def add_word_current(self):
        it, f = self.card_issue, self.field
        self.hide_card()
        if not it or not f:
            return
        word = it["original"].lower()
        config.add_word(it["original"])
        f.issues = [i for i in f.issues if not (i["kind"] == "spelling" and i["original"].lower() == word)]

    # ---------- rewrite the sentence around an issue ----------
    def start_rewrite(self):
        it, f = self.card_issue, self.field
        if not it or not f:
            return
        from writer import readability
        if it.get("scope") == "sentence":
            start, end = it["offset"], it["offset"] + it["length"]
        else:
            start, end = readability.sentence_at(f.text, it["offset"]) or (it["offset"], it["offset"] + it["length"])
        source = f.text[start:end]
        rng = self._make_range(f, start, end - start, source)
        if rng is None:
            self.desk.card_js("window.showRewrite({error: 'Could not find the sentence in the text box.'})")
            return
        self.rewrite = {"range": rng, "source": source, "text": None}
        token = self.rewrite

        def work():
            from writer import server
            try:
                out = server.paraphrase(server.ParaIn(text=source, mode="clarity"))["text"]
                payload = {"text": out}
            except Exception as e:  # noqa: BLE001
                out, payload = None, {"error": str(e)}
            self.post(self._rewrite_done, token, out, payload)

        threading.Thread(target=work, daemon=True).start()

    def _rewrite_done(self, token, out, payload):
        if self.rewrite is not token:
            return
        token["text"] = out
        self.desk.card_js(f"window.showRewrite({__import__('json').dumps(payload)})")

    def apply_rewrite(self):
        rw, f = self.rewrite, self.field
        self.hide_card()
        if not rw or not rw["text"] or not f:
            return
        try:
            if rw["range"].GetText(len(rw["source"]) + 1) != rw["source"]:
                return
        except comtypes.COMError:
            return
        self._replace_range(f, rw["range"], rw["text"])

    def _replace_range(self, f: Field, rng, text: str):
        win32.activate(f.hwnd)
        time.sleep(0.05)
        rng.Select()
        time.sleep(0.05)
        if text == "":
            win32.send_key(0x2E)
            return
        saved = win32.get_clipboard()
        win32.set_clipboard(text)
        win32.send_ctrl("v")
        time.sleep(0.35)
        if saved is not None:
            win32.set_clipboard(saved)

    # ---------- synonyms for a selected word ----------
    def _selection(self, f: Field):
        try:
            sel = f.tp.GetSelection()
            if not sel or sel.Length != 1:
                return None, None
            r = sel.GetElement(0)
            t = r.GetText(40)
        except comtypes.COMError:
            return None, None
        t = t.strip()
        return (t, r) if WORD_RE.match(t) else (None, None)

    def track_selection(self, f: Field):
        word, rng = self._selection(f)
        last, ticks = self.sel
        self.sel = (word, ticks + 1 if word == last else 1)
        if not word:
            self.sel_shown = None
            return
        if self.sel[1] < 3 or self.sel_shown == word or (self.card_issue and self.card_issue.get("kind") != "synonyms"):
            return
        try:
            raw = rng.GetBoundingRectangles()
        except comtypes.COMError:
            return
        rects = [tuple(int(v) for v in raw[k:k + 4]) for k in range(0, len(raw) - 3, 4) if raw[k + 2] > 0]
        if not rects:
            return
        self.sel_shown = word
        it = {"id": -1, "kind": "synonyms", "original": word, "range": rng, "rects": rects, "replacements": []}
        self.card_issue, self.card_left_at, self.rewrite = it, 0.0, None
        x, y, w, h = rects[-1]
        self.desk.show_card({"mode": "synonyms", "word": word, "exe": f.exe}, (x, y, w, h))
        from writer import readability
        pos = f.text.find(word)
        span = readability.sentence_at(f.text, pos) if pos >= 0 else None
        context = f.text[span[0]:span[1]] if span else word

        def work():
            from writer import server
            try:
                syns = server.synonyms(server.SynIn(word=word, context=context[:600]))["synonyms"]
                payload = {"synonyms": syns}
            except Exception as e:  # noqa: BLE001
                syns, payload = [], {"error": str(e)}
            self.post(self._synonyms_done, it, syns, payload)

        threading.Thread(target=work, daemon=True).start()

    def _synonyms_done(self, it, syns, payload):
        if self.card_issue is not it:
            return
        it["replacements"] = syns
        self.desk.card_js(f"window.showSynonyms({__import__('json').dumps(payload)})")

    # ---------- snippets: trigger + space/Enter/punctuation expands ----------
    def _maybe_snippet(self, f: Field, snippets: dict) -> bool:
        try:
            sel = f.tp.GetSelection()
            if not sel or sel.Length != 1:
                return False
            caret = sel.GetElement(0)
            if caret.CompareEndpoints(EP_START, caret, EP_END) != 0:
                return False
            longest = max(len(k) for k in snippets) + 2
            before_r = caret.Clone()
            before_r.MoveEndpointByUnit(EP_START, UNIT_CHAR, -longest)
            before = before_r.GetText(longest + 2)
        except comtypes.COMError:
            return False
        if not before or before[-1] not in DELIMS:
            return False
        head = before[:-1]
        for trig, expansion in snippets.items():
            if not head.endswith(trig):
                continue
            prev = head[:-len(trig)]
            if prev and not prev[-1].isspace():
                continue
            try:
                t = caret.Clone()
                t.MoveEndpointByUnit(EP_START, UNIT_CHAR, -(len(trig) + 1))
                t.MoveEndpointByUnit(EP_END, UNIT_CHAR, -1)
                if t.GetText(len(trig) + 1) != trig:
                    return False
            except comtypes.COMError:
                return False
            self._replace_range(f, t, expansion)
            return True
        return False

    # ---------- dragging the button ----------
    def _badge_moved(self, x: int, y: int):
        """Remember where the user dropped the button, per app, relative to its window or text box."""
        if not self.badge_anchor:
            return
        kind, exe, (ax, ay) = self.badge_anchor
        pos = dict(config.get().get("button_pos", {}))
        pos[f"{kind}:{exe}"] = [x - ax, y - ay]
        config.update(button_pos=pos)
