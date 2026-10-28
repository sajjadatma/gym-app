from __future__ import annotations

from fastapi.testclient import TestClient


def test_missing_hashed_asset_is_not_replaced_with_the_spa_shell(
    client: TestClient,
) -> None:
    response = client.get("/assets/missing-build-file.js")
    assert response.status_code == 404
    assert "text/html" not in response.headers.get("content-type", "")


def test_missing_icon_is_not_replaced_with_the_spa_shell(
    client: TestClient,
) -> None:
    response = client.get("/icons/missing-icon.png")
    assert response.status_code == 404
    assert "text/html" not in response.headers.get("content-type", "")


def test_spa_routes_serve_an_uncached_shell(client: TestClient) -> None:
    response = client.get("/some/client/route")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert response.headers.get("cache-control") == "no-store"
