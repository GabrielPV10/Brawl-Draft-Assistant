from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_recommend_dummy_returns_top3() -> None:
    resp = client.get("/recommend/dummy")
    assert resp.status_code == 200
    body = resp.json()
    assert body["map_id"] == 1
    assert len(body["recommendations"]) == 3
    assert all("brawler_name" in r and "score" in r for r in body["recommendations"])
