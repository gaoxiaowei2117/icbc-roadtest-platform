def test_pos_list_returns_entries(client):
    r = client.get("/api/pos-list")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 50
    first = data[0]
    assert "name" in first and "pos_id" in first
    assert isinstance(first["pos_id"], int)
