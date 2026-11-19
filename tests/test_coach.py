"""Unit tests for the style coach: rules, protections and mechanical edits.

No models, no network: these run in milliseconds.
"""

from app.coach import analyse, apply_findings, find_patterns, protected_ranges

TEXT = (
    "Por otra parte, en el ámbito de la educación el alumnado aprende a escribir. "
    "Cabe destacar que la implementación de programas nuevos exige tiempo. "
    "No cabe duda de que el profesorado necesita apoyo. "
    "La revisión de los trabajos de los estudiantes de la facultad de letras requiere "
    "un esfuerzo notable y constante por parte del profesorado."
)


def rules(text):
    return [f.rule for f in find_patterns(text)]


def test_finds_stock_connector_and_it_is_mechanical():
    findings = [f for f in find_patterns(TEXT) if f.rule == "R3"]
    assert findings, "the connector at the start of the text should be found"
    assert findings[0].quote.strip().lower().startswith("por otra parte")
    assert findings[0].auto is True
    assert findings[0].replacement == ""


def test_finds_hedges_and_filler():
    found = rules(TEXT)
    assert "R6" in found  # "Cabe destacar que"
    assert "R8" in found  # "en el ámbito de"


def test_detects_abstract_noun_and_chain():
    text = "La implementación de la política de la dirección de la empresa llegó tarde."
    found = rules(text)
    assert "R1" in found
    assert "R2" in found


def test_detects_symmetric_list():
    text = "Trajo pan, queso, vino, aceitunas y fruta para la cena del sábado por la noche."
    assert "R4" in rules(text)


def test_detects_uniform_long_sentences():
    sentence = (
        "El proceso de revisión de los documentos que llegan a la oficina central requiere "
        "la atención sostenida del equipo completo durante varias jornadas de trabajo"
    )
    text = ". ".join([sentence] * 5) + "."
    findings = find_patterns(text)
    assert any(f.rule == "R5" for f in findings)


def test_clean_prose_has_few_findings():
    text = (
        "Mi abuela guardaba las cartas en una caja de latón. Nunca dijo por qué. "
        "Un martes de julio abrí la caja y encontré cuarenta años de sobres sin abrir. "
        "El primero era de 1961."
    )
    assert len(find_patterns(text)) <= 1


def test_citations_are_never_flagged_nor_edited():
    text = "En el ámbito de la discusión (Cicerón, 44 a.C. – 1923), la autora matiza su postura."
    findings = find_patterns(text)
    protected = protected_ranges(text)
    for finding in findings:
        for start, end in protected:
            assert not (finding.start < end and finding.end > start), finding
    # A replacement that targets the citation must be refused.
    citation_start = text.index("(Cicerón")
    out = apply_findings(
        text,
        [{"start": citation_start, "end": citation_start + 10, "replacement": "X"}],
    )
    assert out == text


def test_apply_is_idempotent_on_offsets():
    findings = [f for f in find_patterns(TEXT) if f.auto]
    edits = [
        {"start": f.start, "end": f.end, "replacement": f.replacement} for f in findings
    ]
    out = apply_findings(TEXT, edits)
    assert "Por otra parte" not in out
    assert "en el ámbito de" not in out
    assert "educación" in out


def test_summary_counts_mechanical_edits():
    data = analyse(TEXT)
    assert data["summary"]["total"] >= 3
    assert data["summary"]["mechanical"] >= 2
    assert data["protected_spans"] == 0
