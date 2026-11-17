"""Hemingway-style readability checks: long sentences, passive voice, adverbs, wordy phrases, weak qualifiers.
Pure rules, no model: instant."""
from __future__ import annotations

import re

IRREGULAR_PARTICIPLES = set("""
arisen awoken beaten become begun bent bet bound bitten bled blown broken brought built burnt burned bought caught
chosen clung come cost crept cut dealt done drawn dreamt driven drunk eaten fallen fed felt fought found fled flung
flown forbidden forgotten forgiven frozen gotten given gone ground grown hung heard hidden hit held hurt kept knelt
known laid led left lent let lain lit lost made meant met mistaken paid proven put quit read ridden rung risen run
said seen sought sold sent set sewn shaken shed shone shot shown shrunk shut sung sunk sat slain slept slid slung
spoken sped spent spilt spun spat split spread sprung stood stolen stuck stung stridden struck strung sworn swept
swollen swum swung taken taught torn told thought thrown thrust trodden understood undertaken upset woken worn woven
wept won wound withdrawn written
""".split())

NOT_ADVERBS = set("""
only family early likely unlikely reply apply supply july italy holy ugly belly jelly rely fly ally daily weekly
monthly yearly hourly friendly unfriendly lovely lonely silly costly elderly assembly butterfly anomaly homily bully
rally tally lily emily kelly sally molly hilly chilly curly lively deadly orderly kindly(adj) firefly dragonfly
comply imply multiply july melancholy monopoly oily scholarly smelly sly wily woolly bubbly cuddly holly folly
""".replace("(adj)", "").split())

QUALIFIERS = ["very", "really", "quite", "rather", "somewhat", "just", "actually", "basically", "literally",
              "totally", "pretty much", "kind of", "sort of"]

WORDY = {
    "utilize": "use", "utilise": "use", "utilization": "use", "in order to": "to", "due to the fact that": "because",
    "owing to the fact that": "because", "at this point in time": "now", "at the present time": "now",
    "commence": "start", "terminate": "end", "facilitate": "help", "approximately": "about",
    "subsequently": "later", "additional": "more", "assistance": "help", "demonstrate": "show",
    "endeavor": "try", "endeavour": "try", "purchase": "buy", "sufficient": "enough", "numerous": "many",
    "prior to": "before", "in the event that": "if", "with regard to": "about", "with respect to": "about",
    "in spite of the fact that": "although", "despite the fact that": "although", "a large number of": "many",
    "the majority of": "most", "is able to": "can", "are able to": "can", "has the ability to": "can",
    "have the ability to": "can", "in close proximity to": "near", "on a daily basis": "daily",
    "initiate": "start", "modify": "change", "obtain": "get", "individuals": "people", "methodology": "method",
    "ascertain": "find out", "in the near future": "soon", "for the purpose of": "for", "in addition to": "besides",
    "a number of": "some", "it is important to note that": "", "needless to say": "", "each and every": "every",
    "first and foremost": "first", "until such time as": "until", "in light of the fact that": "because",
    "has a tendency to": "tends to", "make a decision": "decide", "come to a conclusion": "conclude",
    "give consideration to": "consider", "take into consideration": "consider",
}

_PASSIVE = re.compile(
    r"\b(am|is|are|was|were|be|been|being)\s+(?:not\s+)?(?:\w+ly\s+)?(\w+ed|"
    + "|".join(sorted(IRREGULAR_PARTICIPLES, key=len, reverse=True)) + r")\b",
    re.I,
)
_ADVERB = re.compile(r"\b[A-Za-z]{3,}ly\b")
_WORDY = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(WORDY, key=len, reverse=True)) + r")\b", re.I)
_QUAL = re.compile(r"\b(" + "|".join(re.escape(q) for q in QUALIFIERS) + r")\b", re.I)
_SENT = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")


def _match_case(src: str, rep: str) -> str:
    return rep[:1].upper() + rep[1:] if src[:1].isupper() and rep else rep


def sentences(text: str) -> list[tuple[int, int]]:
    """(start, end) of each sentence, trimmed."""
    out = []
    for m in _SENT.finditer(text):
        s, e = m.start(), m.end()
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e > s:
            out.append((s, e))
    return out


def analyze(text: str) -> list[dict]:
    issues: list[dict] = []

    def add(s, e, msg, reps, sub, scope="word"):
        issues.append({"offset": s, "length": e - s, "message": msg, "replacements": reps,
                       "kind": "clarity", "source": "Readability", "sub": sub, "scope": scope})

    for m in _WORDY.finditer(text):
        rep = WORDY[m.group(1).lower()]
        add(m.start(), m.end(), f"Wordy: “{m.group(1)}” can be simpler." if rep else "This phrase adds nothing. Remove it?",
            [_match_case(m.group(1), rep)], "wordy")
    for m in _QUAL.finditer(text):
        add(m.start(), m.end(), f"“{m.group(1)}” weakens your writing. Remove it?", [""], "qualifier")
    for m in _PASSIVE.finditer(text):
        add(m.start(), m.end(), "Passive voice. Active voice is usually clearer: say who does what.", [], "passive")
    for m in _ADVERB.finditer(text):
        w = m.group(0).lower()
        if w in NOT_ADVERBS or w in ("very",):
            continue
        add(m.start(), m.end(), f"Adverb “{m.group(0)}”. A stronger verb often works better.", [], "adverb")

    # Word-level issues must not overlap each other; keep the earliest.
    issues.sort(key=lambda i: (i["offset"], -i["length"]))
    kept, end = [], -1
    for it in issues:
        if it["offset"] >= end:
            kept.append(it)
            end = it["offset"] + it["length"]

    for s, e in sentences(text):
        n = len(re.findall(r"\b\w+\b", text[s:e]))
        if n >= 35:
            add(s, e, f"Very hard to read: {n} words in one sentence. Split it or rewrite it.", [], "very-long", "sentence")
        elif n >= 25:
            add(s, e, f"Hard to read: {n} words in one sentence. Consider splitting it.", [], "long", "sentence")
    kept += [i for i in issues if i["scope"] == "sentence"]
    return kept


def sentence_at(text: str, offset: int) -> tuple[int, int] | None:
    for s, e in sentences(text):
        if s <= offset < e:
            return s, e
    return None
