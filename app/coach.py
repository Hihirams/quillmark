"""Style coach: finds the patterns that make written prose read as machine-made
and suggests *surgical* edits, one span at a time.

Why it exists: our own evaluation (experiments/rewriting) showed that rewriting a
text from scratch lowers the calibrated score far less than editing the specific
formulaic patterns in place. A free rewrite drops most engines but flips TMR, the
heaviest weight in the Spanish fit; surgical edits drop every engine together.

What it does not do: it never invents content, never touches citations, quoted
text, numbers or URLs, and never claims a text is "undetectable". The score is a
signal, not proof.

Everything here is deterministic and local: no model calls, no external APIs.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

# --- protected context -------------------------------------------------------

# Things the coach must never edit: citations with a year, quoted speech, URLs.
_PROTECTED = (
    re.compile(
        r"\([^()]{0,140}?\b(?:1[5-9]\d{2}|20\d{2})\b[^()]{0,60}?\)"
    ),  # (Autor, 1923)
    re.compile(r"\[[^\[\]]{1,80}\]"),  # [1], [12]
    re.compile(r"«[^»]{0,400}»"),  # «cita»
    re.compile(r"“[^”]{0,400}”"),  # “cita”
    re.compile(r"\"[^\"]{0,400}\""),  # "cita"
    re.compile(r"https?://\S+"),
)


def protected_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for pattern in _PROTECTED:
        ranges.extend((m.start(), m.end()) for m in pattern.finditer(text))
    return sorted(ranges)


def _is_protected(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start < r_end and end > r_start for r_start, r_end in ranges)


# --- rules -------------------------------------------------------------------

# R3: stock connectors. Pure removal, so they are safe to apply mechanically.
CONNECTORS: list[tuple[str, str]] = [
    ("Por otra parte, ", ""),
    ("Por otro lado, ", ""),
    ("En este sentido, ", ""),
    ("En ese sentido, ", ""),
    ("En este contexto, ", ""),
    ("Del mismo modo, ", ""),
    ("De igual manera, ", ""),
    ("De igual modo, ", ""),
    ("Asimismo, ", ""),
    ("Adicionalmente, ", ""),
    ("En conclusión, ", ""),
    ("En definitiva, ", ""),
    ("En síntesis, ", ""),
    ("Cabe destacar que ", ""),
    ("Cabe señalar que ", ""),
    ("Cabe mencionar que ", ""),
    ("Es importante señalar que ", ""),
    ("Es importante destacar que ", ""),
    ("Es importante mencionar que ", ""),
    ("Vale la pena señalar que ", ""),
]

# R6: closing hedges and filler openers that add nothing.
HEDGES: list[tuple[str, str | None]] = [
    ("no cabe duda de que ", ""),
    ("sin lugar a dudas, ", ""),
    ("huelga decir que ", ""),
    ("conviene recordar que ", ""),
    ("es fundamental entender que ", ""),
    ("en última instancia, ", ""),
    ("a nivel general, ", ""),
    ("en términos generales, ", ""),
    ("resulta significativo que ", None),
    ("resulta fundamental ", None),
    ("juega un papel crucial", None),
]

# R8: word-level filler with a plain equivalent.
FILLERS: list[tuple[str, str]] = [
    ("en el ámbito de", "en"),
    ("en el marco de", "en"),
    ("en el contexto de", "en"),
    ("con el objetivo de", "para"),
    ("con la finalidad de", "para"),
    ("debido al hecho de que", "porque"),
    ("a pesar del hecho de que", "aunque"),
    ("un abanico de", "varios"),
    ("un sinfín de", "muchos"),
    ("una amplia gama de", "varios"),
    ("de vital importancia", "importante"),
    ("de suma importancia", "muy importante"),
    ("sumamente", "muy"),
    ("en la actualidad", "hoy"),
    ("de manera significativa", "mucho"),
    ("en gran medida", "mucho"),
    ("cabe la posibilidad de", "puede"),
]

# R1: abstract noun + "de". Suggest turning the noun into a verb; never automatic
# because the grammar around it changes.
_NOMINAL = re.compile(
    r"\b(?:la|el|los|las)\s+([a-záéíóúüñ]{4,}?(?:ción|siones|miento|mientos|idad|idades|encia|encias|ancia|ancias|ización|izaciones))\s+de\b",
    re.IGNORECASE,
)
_NOMINAL_VERB = {
    "implementación": "implementar",
    "aplicación": "aplicar",
    "utilización": "usar",
    "realización": "hacer",
    "elaboración": "elaborar",
    "construcción": "construir",
    "evaluación": "evaluar",
    "medición": "medir",
    "análisis": "analizar",
    "descripción": "describir",
    "identificación": "identificar",
    "comparación": "comparar",
    "justificación": "justificar",
    "presentación": "presentar",
    "desarrollo": "desarrollar",
    "crecimiento": "crecer",
    "disminución": "disminuir",
    "aumento": "aumentar",
    "pérdida": "perder",
    "proximidad": "acercarse",
    "alejamiento": "alejarse",
    "importancia": "importar",
    "posibilidad": "poder",
    "necesidad": "necesitar",
    "influencia": "influir",
}

# R2: chained "de" inside one sentence.
_CHAIN = re.compile(
    r"\bde\s+(?:la|las|los|el)?\s*\w+\s+de\s+(?:la|las|los|el)?\s*\w+\s+de\b",
    re.IGNORECASE,
)

# R4: symmetric enumerations of four or more items. A plain regex cannot tell how
# many items a list has once "y"/"o" joins the last two, so count them per sentence.
_SENTENCE_BLOCK = re.compile(r"[^.!?\n]+")


def _enumerations(text: str):
    for match in _SENTENCE_BLOCK.finditer(text):
        sentence = match.group(0)
        parts = [part.strip() for part in sentence.split(",")]
        if len(parts) < 3:
            continue
        tail = re.split(r"\s(?:y|e|o)\s", parts[-1])
        if len(tail) < 2:
            continue
        items = len(parts) - 1 + len(tail)
        if items >= 4:
            yield match.start(), match.end(), items


_SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Finding:
    rule: str
    label: str
    start: int
    end: int
    quote: str
    suggestion: str
    replacement: str | None
    auto: bool
    note: str


def _finding(
    rule, label, text, start, end, suggestion, replacement, auto, note, spans
) -> Finding | None:
    if _is_protected(start, end, spans):
        return None
    quote = text[start:end]
    if not quote.strip():
        return None
    return Finding(
        rule=rule,
        label=label,
        start=start,
        end=end,
        quote=quote if len(quote) <= 160 else quote[:157] + "...",
        suggestion=suggestion,
        replacement=replacement,
        auto=auto,
        note=note,
    )


def _paragraphs(text: str) -> list[tuple[int, int]]:
    blocks = []
    for match in re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*", text):
        if match.group(0).strip():
            blocks.append((match.start(), match.end()))
    return blocks


def find_patterns(text: str) -> list[Finding]:
    """Every finding, sorted by position. Citations and quotes are untouched."""
    spans = protected_ranges(text)
    findings: list[Finding] = []

    def add(item: Finding | None) -> None:
        if item is not None:
            findings.append(item)

    for phrase, replacement in CONNECTORS:
        for match in re.finditer(re.escape(phrase), text, re.IGNORECASE):
            add(
                _finding(
                    "R3",
                    "Stock connector",
                    text,
                    match.start(),
                    match.end(),
                    'Drop it: "A través de", "Por otra parte" and the rest are filler.',
                    replacement,
                    True,
                    "Connector phrases are the cheapest thing to remove: the sentence keeps its meaning.",
                    spans,
                )
            )

    for phrase, replacement in HEDGES:
        for match in re.finditer(re.escape(phrase), text, re.IGNORECASE):
            auto = replacement is not None
            add(
                _finding(
                    "R6",
                    "Closing hedge" if auto else "Empty emphasis",
                    text,
                    match.start(),
                    match.end(),
                    "Say it plainly, or cut the clause."
                    if not auto
                    else "Cut it; the claim stands on its own.",
                    replacement,
                    auto,
                    "Hedges pad the sentence and are one of the strongest style signals detectors read.",
                    spans,
                )
            )

    for phrase, replacement in FILLERS:
        for match in re.finditer(re.escape(phrase), text, re.IGNORECASE):
            add(
                _finding(
                    "R8",
                    "Filler phrase",
                    text,
                    match.start(),
                    match.end(),
                    f'"{match.group(0)}" -> "{replacement}"',
                    replacement,
                    True,
                    "One plain word beats a three-word formula.",
                    spans,
                )
            )

    for match in _NOMINAL.finditer(text):
        noun = match.group(1).lower()
        verb = _NOMINAL_VERB.get(noun)
        if not verb:
            continue
        add(
            _finding(
                "R1",
                "Abstract noun",
                text,
                match.start(1),
                match.end(1),
                f'Turn "{match.group(1)}" into the verb "{verb}" and rebuild the clause around it.',
                None,
                False,
                '"la disminucion de X" hides the action; "X disminuye" shows it.',
                spans,
            )
        )

    for match in _CHAIN.finditer(text):
        add(
            _finding(
                "R2",
                "Chained 'de'",
                text,
                match.start(),
                match.end(),
                "Split it or reorder: one 'de' per noun phrase is enough.",
                None,
                False,
                "Chains of 'de ... de ... de' are the most recognisable machine-made construction.",
                spans,
            )
        )

    for start, end, items in _enumerations(text):
        add(
            _finding(
                "R4",
                "Symmetric list",
                text,
                start,
                end,
                "Keep two or three items, or replace the list with one concrete example.",
                None,
                False,
                f"{items} items of equal weight: the rhythm gives it away more than the words.",
                spans,
            )
        )

    for start, end in _paragraphs(text):
        block = text[start:end]
        sentences = [s for s in _SENTENCE.split(block) if len(s.split()) > 3]
        if len(sentences) < 4:
            continue
        lengths = [len(s.split()) for s in sentences]
        mean = sum(lengths) / len(lengths)
        var = sum((x - mean) ** 2 for x in lengths) / len(lengths)
        cv = (var**0.5) / mean if mean else 0
        if mean >= 24 and cv < 0.35:
            add(
                Finding(
                    rule="R5",
                    label="Uniform sentence length",
                    start=start,
                    end=end,
                    quote=block[:160] + ("..." if len(block) > 160 else ""),
                    suggestion=f"Mix it up: {len(sentences)} sentences averaging {mean:.0f} words (CV {cv:.2f}).",
                    replacement=None,
                    auto=False,
                    note="Uniform, long sentences are the single most reliable style signal in our tests.",
                )
            )
        elif mean >= 32:
            add(
                Finding(
                    rule="R5",
                    label="Overlong sentences",
                    start=start,
                    end=end,
                    quote=block[:160] + ("..." if len(block) > 160 else ""),
                    suggestion=f"Average {mean:.0f} words per sentence: cut at the commas.",
                    replacement=None,
                    auto=False,
                    note="Long sentences hide the subject and flatten the rhythm.",
                )
            )

        if len(block.split()) >= 60 and not re.search(r"\d", block):
            add(
                Finding(
                    rule="R7",
                    label="No concrete detail",
                    start=start,
                    end=end,
                    quote=block[:160] + ("..." if len(block) > 160 else ""),
                    suggestion="Add one verifiable detail: a date, a figure, a name, a quotation.",
                    replacement=None,
                    auto=False,
                    note="Abstraction without anchors is what makes prose sound generated.",
                )
            )

    findings.sort(key=lambda f: (f.start, f.rule))
    return findings


def apply_findings(text: str, replacements: list[dict]) -> str:
    """Apply mechanical edits from the end of the text backwards, so offsets stay valid.

    Each item is `{"start": int, "end": int, "replacement": str}`. Items that
    overlap a protected range are ignored, and so are overlapping edits.
    """
    spans = protected_ranges(text)
    accepted: list[tuple[int, int, str]] = []
    for item in sorted(replacements, key=lambda r: int(r["start"]), reverse=True):
        start, end = int(item["start"]), int(item["end"])
        if start < 0 or end > len(text) or start >= end:
            continue
        if _is_protected(start, end, spans):
            continue
        if any(
            start < other_end and end > other_start
            for other_start, other_end, _ in accepted
        ):
            continue
        accepted.append((start, end, str(item.get("replacement") or "")))

    result = text
    for start, end, replacement in accepted:
        result = result[:start] + replacement + result[end:]
    return result


def summarise(findings: list[Finding]) -> dict:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.rule] = counts.get(finding.rule, 0) + 1
    return {
        "total": len(findings),
        "mechanical": sum(1 for f in findings if f.auto),
        "by_rule": dict(sorted(counts.items())),
    }


def analyse(text: str) -> dict:
    findings = find_patterns(text)
    return {
        "findings": [asdict(f) for f in findings],
        "summary": summarise(findings),
        "protected_spans": len(protected_ranges(text)),
        "chars": len(text),
        "words": len(text.split()),
    }
