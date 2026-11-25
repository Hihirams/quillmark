"""Secondary pages keep their route, local styles, and working API contract."""

from fastapi.testclient import TestClient

from app.main import app


def test_style_coach_workspace_is_accessible():
    client = TestClient(app)
    page = client.get("/coach")
    assert page.status_code == 200
    assert "<h1>Style coach</h1>" in page.text
    assert 'id="coach-input"' in page.text
    assert 'id="coach-findings"' in page.text


def test_api_reference_preserves_swagger_references_and_compatibility():
    client = TestClient(app, root_path="/service")
    page = client.get("/docs")
    assert page.status_code == 200
    assert 'data-openapi-url="/service/openapi.json"' in page.text
    assert 'data-oauth-redirect="/service/docs/oauth2-redirect"' in page.text
    assert "swagger-ui-bundle.js" in page.text
    assert "api-docs.js" in page.text
    assert client.get("/docs/oauth2-redirect").status_code == 200
    assert client.get("/redoc").status_code == 200

    paths = client.get("/openapi.json").json()["paths"]
    assert "/docs" not in paths
    assert "/api/coach" in paths
