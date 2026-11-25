"""Brand assets and names remain consistent in real HTTP responses."""

from fastapi.testclient import TestClient

from app.main import app


def test_quillmark_home_and_coach_are_branded_without_a_legacy_watermark():
    client = TestClient(app)
    for path, marker in [("/", "Read the signals."), ("/coach", "Style coach")]:
        response = client.get(path)
        assert response.status_code == 200
        assert marker in response.text
        assert "Hiram G. edition" in response.text
        assert "/static/css/quillmark.css" in response.text
        assert 'class="st-logo__word qm-firma"' in response.text
        assert 'class="qm-firma__q"' in response.text
        assert 'src="/static/quillmark-margen.svg"' not in response.text
        assert 'aria-label="Quillmark home"' in response.text
        assert "CREDITS.md" in response.text
        assert "self-hosted fork" not in response.text
        assert "SlopTotal</a>" not in response.text


def test_brand_styles_and_icon_are_served_locally():
    client = TestClient(app)
    stylesheet = client.get("/static/css/quillmark.css")
    icon = client.get("/static/favicon.svg")
    assert stylesheet.status_code == 200
    assert ".qm-workspace" in stylesheet.text
    assert icon.status_code == 200
    assert icon.headers["content-type"] == "image/svg+xml"
    assert "#3e2865" in icon.text
    shell = client.get("/static/css/quillmark-shell.css")
    assert shell.status_code == 200
    assert ".qm-firma" in shell.text
    for name in ("quillmark-secondary", "quillmark-report"):
        assert client.get(f"/static/css/{name}.css").status_code == 200


def test_detector_has_workspace_navigation_and_labeled_queue_dialog():
    client = TestClient(app)
    html = client.get("/").text
    assert 'aria-label="Workspace"' in html
    assert "/static/illustrations/reviewers.png" not in html
    assert (
        'aria-modal="true" aria-labelledby="queue-title" aria-describedby="queue-desc"'
        in html
    )
    assert 'id="queue-cancel"' in html


def test_home_reading_guide_links_and_artwork_are_local():
    client = TestClient(app)
    html = client.get("/").text
    for anchor in ("detector-workspace", "how-heading", "score-heading", "engines-heading"):
        assert f'href="#{anchor}"' in html
        assert f'id="{anchor}"' in html
    image = client.get("/static/img/lente-atlas.webp")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/webp"
    assert html.count('src="/static/img/lente-atlas.webp"') == 2


def test_coach_can_import_and_apply_edits_to_a_document():
    client = TestClient(app)
    page = client.get("/coach").text
    assert 'id="coach-file"' in page
    assert 'id="coach-download"' in page
    assert "Compare with original" in page
    assert 'href="/coach#coach-file"' in client.get("/").text
    draft = (
        "Por otra parte, en el ambito de la educacion el alumnado aprende a escribir. "
        "Cabe destacar que la implementacion de programas nuevos exige tiempo. "
        "No cabe duda de que el profesorado necesita apoyo."
    )
    upload = client.post("/api/extract", files={"file": ("draft.txt", draft, "text/plain")})
    assert upload.status_code == 200
    text = upload.json()["text"]
    assert text == draft
    review = client.post("/api/coach", json={"text": text})
    assert review.status_code == 200
    edit = next(item for item in review.json()["findings"] if item["auto"])
    revised = client.post(
        "/api/coach/apply",
        json={"text": text, "edits": [{k: edit[k] for k in ("start", "end", "replacement")}]},
    )
    assert revised.status_code == 200
    assert revised.json()["text"] != text
