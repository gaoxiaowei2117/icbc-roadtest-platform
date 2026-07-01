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


def test_clear_profile_fields(client, auth_headers):
    """显式传 null 应清空字段；未传的字段保持不变。"""
    h = auth_headers()
    # 先写入
    client.patch(
        "/api/users/me",
        headers=h,
        json={
            "icbc_license_no": "7654321",
            "icbc_last_name": "GAO",
            "pos_ids": [1, 274],
            "expect_after_date": "2026-07-01",
        },
    )
    # 只清空部分字段，其余字段不出现在 payload 中
    r = client.patch(
        "/api/users/me",
        headers=h,
        json={"icbc_license_no": None, "pos_ids": None, "expect_after_date": None},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["icbc_license_no"] is None
    assert body["pos_ids"] is None
    assert body["expect_after_date"] is None
    # 未提交的字段保持原值
    assert body["icbc_last_name"] == "GAO"
    # 读回确认已持久化，而非仅响应体
    me = client.get("/api/users/me", headers=h).json()
    assert me["icbc_license_no"] is None
    assert me["pos_ids"] is None
    assert me["expect_after_date"] is None
    assert me["icbc_last_name"] == "GAO"
