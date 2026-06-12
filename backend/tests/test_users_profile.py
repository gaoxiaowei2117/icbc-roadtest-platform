def test_update_and_read_profile(client, auth_headers):
    h = auth_headers()
    payload = {
        "icbc_license_no": "7654321",
        "icbc_last_name": "GAO",
        "exam_class": "5",
        "pos_ids": [1, 274],
        "expect_after_date": "2026-07-01",
        "expect_before_date": "2026-08-01",
        "expect_time_range": "10:00-17:00",
        "pref_days_of_week": [0, 1, 2, 3, 4],
        "pref_parts_of_day": [0, 1],
    }
    r = client.patch("/api/users/me", headers=h, json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["exam_class"] == "5"
    assert body["pos_ids"] == [1, 274]
    assert body["expect_time_range"] == "10:00-17:00"
    assert body["pref_days_of_week"] == [0, 1, 2, 3, 4]
    # 读回一致
    me = client.get("/api/users/me", headers=h).json()
    assert me["pos_ids"] == [1, 274]
    assert me["expect_after_date"] == "2026-07-01"
