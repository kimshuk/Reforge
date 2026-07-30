import re

from app.errors import AppError

CJK_SCRIPT_RE = re.compile(
    r"[\u1100-\u11ff\u3040-\u30ff\u3130-\u318f\u3400-\u4dbf"
    r"\u4e00-\u9fff\uac00-\ud7af]"
)


def validate_explanation_ladder(
    term: str, brief: str, simple: str, contextual: str, detailed: str
) -> None:
    errors = explanation_ladder_errors(term, brief, simple, contextual, detailed)
    if errors:
        raise AppError(502, "LLM_CLIPPINGS_INVALID_JSON", "; ".join(errors))


def explanation_ladder_errors(
    term: str, brief: str, simple: str, contextual: str, detailed: str
) -> list[str]:
    errors: list[str] = []
    if any(not value.strip() for value in (term, brief, simple, contextual, detailed)):
        errors.append("Explanation ladder fields must not be empty")
    levels = [normalize_explanation(value) for value in (simple, contextual, detailed)]
    if len(set(levels)) != 3:
        errors.append("Explanation ladder levels must not be duplicates")
    if len(term) < 2:
        errors.append("Term must contain at least 2 characters")
    if len(term) > 60:
        errors.append("Term must be at most 60 characters")
    if re.search(r"[.!?。！？]\s*$", term):
        errors.append("Term must be a reusable label, not a sentence")
    if " " not in brief or CJK_SCRIPT_RE.search(brief):
        brief_characters = len(re.sub(r"\s+", "", brief))
        if not 5 <= brief_characters <= 40:
            errors.append("Brief must contain 5-40 non-whitespace characters")
    elif not 5 <= len(brief.split()) <= 10:
        errors.append("Brief must contain 5-10 words")
    if len(brief) >= len(simple):
        errors.append("Brief must be shorter than simple explanation")
    simple_sentences = sentence_count(simple)
    contextual_sentences = sentence_count(contextual)
    detailed_sentences = sentence_count(detailed)
    if simple_sentences != 1:
        errors.append(
            f"Simple explanation has {simple_sentences} {_sentence_word(simple_sentences)}; "
            "expected exactly 1"
        )
    if contextual_sentences not in {2, 3}:
        errors.append(
            f"Contextual explanation has {contextual_sentences} "
            f"{_sentence_word(contextual_sentences)}; expected 2-3"
        )
    if len(simple) >= len(contextual):
        errors.append("Contextual explanation must be longer than simple explanation")
    if detailed_sentences not in {3, 4, 5}:
        errors.append(
            f"Detailed explanation has {detailed_sentences} "
            f"{_sentence_word(detailed_sentences)}; expected 3-5"
        )
    if len(contextual) >= len(detailed):
        errors.append("Detailed explanation must be longer than contextual explanation")
    return errors


def sentence_count(value: str) -> int:
    protected = re.sub(r"(?<=\d)\.(?=\d)", "<DOT>", value.strip())
    protected = re.sub(
        r"\b(?:e\.g|i\.e)\.",
        lambda match: match.group(0).replace(".", "<DOT>"),
        protected,
        flags=re.IGNORECASE,
    )
    protected = re.sub(
        r"\b(?:mr|mrs|ms|dr|prof|sr|jr)\.",
        lambda match: match.group(0).replace(".", "<DOT>"),
        protected,
        flags=re.IGNORECASE,
    )
    protected = re.sub(
        r"\b(?:[A-Za-z]\.){2,}",
        lambda match: _protect_contextual_abbreviation(match, protected),
        protected,
    )
    protected = re.sub(
        r"\b(?:vs|etc)\.",
        lambda match: _protect_contextual_abbreviation(match, protected),
        protected,
        flags=re.IGNORECASE,
    )
    parts = [
        part
        for part in re.split(r"[.!?。！？]+(?:[\"')\]]*)\s*", protected)
        if part.strip()
    ]
    return max(1, len(parts))


def normalize_explanation(value: str) -> str:
    return re.sub(r"[.?!。！？]+$", "", re.sub(r"\s+", " ", value.lower()).strip())


def _sentence_word(count: int) -> str:
    return "sentence" if count == 1 else "sentences"


def _protect_contextual_abbreviation(match: re.Match[str], value: str) -> str:
    token = match.group(0)
    next_text = value[match.end() :].lstrip()
    protect_final_period = bool(next_text and next_text[0].islower())
    body = token[:-1].replace(".", "<DOT>")
    return body + ("<DOT>" if protect_final_period else ".")
