"""Brand assets and names remain consistent in real HTTP responses."""

from fastapi.testclient import TestClient

from app.main import app


def test_quillmark_home_and_coach_are_branded_without_a_legacy_watermark():
    client = TestClient(app)
    for path, marker in [("/", "Read between the lines."), ("/coach", "Revision desk")]:
        response = client.get(path)
        assert response.status_code == 200
        assert marker in response.text
        assert "Hiram G. edition" in response.text
        assert "/static/css/quillmark.css" in response.text
        assert 'src="/static/quillmark-margen.svg"' in response.text
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
    header_mark = client.get("/static/quillmark-margen.svg")
    assert header_mark.status_code == 200
    assert header_mark.headers["content-type"] == "image/svg+xml"
    assert "prefers-color-scheme: dark" in header_mark.text
