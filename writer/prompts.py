"""Prompts for grammar checking and paraphrasing."""

BASE_RULES = (
    "Keep the original meaning, facts, names and numbers. Keep the same language as the input. "
    "Always fix every grammar, spelling, punctuation and capitalization error, "
    "including pronoun case ('Me and him went' -> 'He and I went'). "
    "Return only the rewritten text: no preface, no quotes, no notes."
)

MODES = {
    "fix": "Correct every error in grammar, spelling, punctuation, capitalization, apostrophes, subject-verb agreement, "
           "pronoun case (e.g. 'Me and him went' -> 'He and I went') and word choice (their/there/they're, its/it's). "
           "Otherwise keep the author's wording and sentence structure.",
    "standard": "Paraphrase it: express the same ideas with different words and varied sentence structure, at a similar length.",
    "fluent": "Make it read smoothly and naturally, like a skilled native writer. Fix awkward phrasing and improve flow.",
    "formal": "Rewrite it in a formal, professional tone suitable for business or official communication. "
              "No contractions, no slang, polite and precise wording.",
    "concise": "Make it as short and direct as possible. Cut filler, redundancy and wordiness. Keep every key point.",
    "casual": "Rewrite it in a relaxed, friendly, conversational tone, like talking to a friend. Contractions are fine.",
    "academic": "Rewrite it in a scholarly academic register, as in a research paper: precise and sophisticated vocabulary, "
                "objective third-person tone where possible, complex but clear sentences, formal connectors "
                "(e.g. 'furthermore', 'consequently'), and no contractions. Restructure sentences; do not just fix errors.",
    "simple": "Rewrite it in plain, simple English that a 12-year-old can understand. Use short sentences and common words.",
}

SYSTEM = "You are an expert editor and writing assistant. " + BASE_RULES

GRAMMAR_SYSTEM = (
    "You are a meticulous proofreader. Find real errors in the user's text: grammar, spelling, "
    "punctuation, capitalization, wrong word, agreement, tense, pronoun case, and clearly awkward style. "
    "For each error return the exact erroneous substring copied verbatim from the text (short: a word or phrase, "
    "not the whole sentence), the corrected replacement, a short explanation, and a kind: "
    "'grammar', 'spelling' or 'style'. Do not flag correct text. If there are no errors return an empty list."
)

GRAMMAR_SCHEMA = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original": {"type": "string"},
                    "replacement": {"type": "string"},
                    "explanation": {"type": "string"},
                    "kind": {"type": "string", "enum": ["grammar", "spelling", "style"]},
                },
                "required": ["original", "replacement", "explanation", "kind"],
            },
        }
    },
    "required": ["issues"],
}


# Internal modes (not shown as paraphrase chips)
EXTRA_MODES = {
    "clarity": "Rewrite this sentence so it is clear, direct and easy to read. If it is long, split it into shorter "
               "sentences. Prefer active voice. Fix any errors.",
}

STRENGTH = {
    1: "Change as little as possible: keep most of the original words and sentence structure.",
    2: "Make light changes: keep the structure, swap some words.",
    3: "",
    4: "Change the wording substantially and vary the sentence structure.",
    5: "Rewrite it boldly with very different wording and sentence structure.",
}

VARIETY = {"en-US": "American", "en-GB": "British", "en-CA": "Canadian", "en-AU": "Australian"}


def paraphrase_messages(mode: str, text: str, strength: int = 3, freeze: list[str] | None = None,
                        language: str = "en-US") -> tuple[str, str]:
    """Instruction goes in the user turn: small models follow it far better there."""
    parts = [MODES.get(mode) or EXTRA_MODES[mode]]
    if mode != "fix" and STRENGTH.get(strength):
        parts.append(STRENGTH[strength])
    if freeze:
        parts.append("Keep these words and phrases exactly as written, unchanged: "
                     + "; ".join(f'"{f}"' for f in freeze) + ".")
    if language in VARIETY:
        parts.append(f"Use {VARIETY[language]} English spelling and vocabulary.")
    user = " ".join(parts) + f"\n\nText:\n<<<\n{text}\n>>>\n\nRewritten text:"
    return SYSTEM, user


SYNONYM_SYSTEM = (
    "You are a thesaurus. Give synonyms for the target word that fit its meaning in the given sentence. "
    "Match the word's form (tense, plural, part of speech). Most useful first. No duplicates, no explanations."
)
SYNONYM_SCHEMA = {
    "type": "object",
    "properties": {"synonyms": {"type": "array", "items": {"type": "string"}, "maxItems": 8}},
    "required": ["synonyms"],
}
