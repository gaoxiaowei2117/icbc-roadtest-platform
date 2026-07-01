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


def test_cannot_clear_required_field_with_active_booking(client, ready_user):
    """B 守卫：有进行中任务时，清空抢号必填字段应被 409 拒绝且不落库。"""
    h, *_ = ready_user()
    client.post("/api/bookings", headers=h, json={})  # 建一个 active 任务

    r = client.patch("/api/users/me", headers=h, json={"expect_after_date": None})
    assert r.status_code == 409
    assert "任务进行中" in r.json()["detail"]
    # 原值保持不变
    me = client.get("/api/users/me", headers=h).json()
    assert me["expect_after_date"] == "2026-07-01"


def test_can_edit_nonrequired_field_with_active_booking(client, ready_user):
    """B 守卫只挡清空必填字段：清空非必填字段（时间区间）仍放行。"""
    h, *_ = ready_user()
    client.post("/api/bookings", headers=h, json={})

    r = client.patch("/api/users/me", headers=h, json={"expect_time_range": None})
    assert r.status_code == 200
    assert r.json()["expect_time_range"] is None


def test_can_change_required_field_to_valid_value_with_active_booking(client, ready_user):
    """B 守卫只挡清空，不挡改成别的合法值。"""
    h, *_ = ready_user()
    client.post("/api/bookings", headers=h, json={})

    r = client.patch("/api/users/me", headers=h, json={"expect_before_date": "2026-09-01"})
    assert r.status_code == 200
    assert r.json()["expect_before_date"] == "2026-09-01"


def test_patch_single_before_date_cannot_break_order(client, auth_headers):
    """ISSUE-002：只 PATCH 一个日期时，需与库中已有日期合并校验顺序。"""
    h = auth_headers()
    client.patch(
        "/api/users/me",
        headers=h,
        json={"expect_after_date": "2026-07-01", "expect_before_date": "2026-08-01"},
    )
    # 只改 before 到早于已有 after → 合并后 结束 < 开始，应 400
    r = client.patch("/api/users/me", headers=h, json={"expect_before_date": "2026-06-01"})
    assert r.status_code == 400
    assert "结束日期" in r.json()["detail"]
    # 未落库，保持原值
    me = client.get("/api/users/me", headers=h).json()
    assert me["expect_before_date"] == "2026-08-01"


def test_patch_single_after_date_cannot_break_order(client, auth_headers):
    """ISSUE-002 对称情形：只改 after 到晚于已有 before。"""
    h = auth_headers()
    client.patch(
        "/api/users/me",
        headers=h,
        json={"expect_after_date": "2026-07-01", "expect_before_date": "2026-08-01"},
    )
    r = client.patch("/api/users/me", headers=h, json={"expect_after_date": "2026-09-01"})
    assert r.status_code == 400
    me = client.get("/api/users/me", headers=h).json()
    assert me["expect_after_date"] == "2026-07-01"
