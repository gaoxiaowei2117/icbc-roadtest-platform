"""worker 端点：claim 下发密文、鉴权、回报结果（F5 回归 + S1 安全属性）。"""
from app.models.booking import Booking, BookingStatus
from tests.conftest import WORKER_HEADERS


def test_claim_requires_worker_key(client):
    assert client.post("/api/worker/claim", headers={"X-Worker-Key": "wrong"}).status_code == 401


def test_claim_returns_ciphertext_no_plaintext(client, ready_user, decrypt_secret):
    """S1：claim 响应含完整档案 + keyword 密文，不含明文凭据；私钥解密往返一致。"""
    h, icbc_user, icbc_pass = ready_user()
    client.post("/api/bookings", headers=h, json={})  # 建任务（无参数）

    r = client.post("/api/worker/claim", headers=WORKER_HEADERS)
    assert r.status_code == 200
    body = r.json()
    # 含完整档案 + keyword 密文，不含明文
    assert body["exam_class"] == "5"
    assert body["pos_ids"] == [1, 274]
    assert body["expect_time_range"] == "10:00-17:00"
    assert "keyword_ciphertext" in body
    assert "keyword" not in body  # 明文 keyword 不下发
    assert body["attempt"] == 1  # 首次认领下发 fencing token
    assert decrypt_secret(body["keyword_ciphertext"]) == f"{icbc_user}\n{icbc_pass}"


def test_claim_empty_when_no_pending(client):
    r = client.post("/api/worker/claim", headers=WORKER_HEADERS)
    assert r.status_code == 200
    assert r.json() is None


def test_claim_marks_running(client, ready_user, db):
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    client.post("/api/worker/claim", headers=WORKER_HEADERS)
    assert db.get(Booking, bid).status == BookingStatus.running


def test_claim_fails_gracefully_on_incomplete_profile(client, ready_user, db):
    """C 兜底：claim 时必填档案缺失，应判失败而非 500 卡死重排。

    直接把字段清成 NULL 绕过 update_me 的 B 守卫，模拟历史脏数据或其它写入路径。
    """
    from app.models.user import User

    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    u = db.query(User).filter_by(email="user@gmail.com").first()
    u.expect_after_date = None
    db.commit()

    r = client.post("/api/worker/claim", headers=WORKER_HEADERS)
    assert r.status_code == 200
    assert r.json() is None  # 没下发任务，而不是 500

    db.expire_all()
    booking = db.get(Booking, bid)
    assert booking.status == BookingStatus.failed
    assert "档案不完整" in booking.last_error
    assert "开始日期" in booking.last_error


def test_worker_report_completes_booking(client, ready_user, db):
    """F5 回归：回报结果不再 NameError，任务进入终态。"""
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    client.post("/api/worker/claim", headers=WORKER_HEADERS)

    r = client.post(f"/api/worker/bookings/{bid}/result", headers=WORKER_HEADERS,
                    json={"attempt": 1, "status": "done", "last_error": None,
                          "result": {"confirmation_no": "CONF-1"}})
    assert r.status_code == 204
    db.expire_all()
    booking = db.get(Booking, bid)
    assert booking.status == BookingStatus.done
    assert booking.result == {"confirmation_no": "CONF-1"}


def test_worker_report_pending_requeues_booking(client, ready_user, db):
    """没抢到号是可重试结果：任务回到 pending，下一轮继续 claim。"""
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    client.post("/api/worker/claim", headers=WORKER_HEADERS)

    r = client.post(
        f"/api/worker/bookings/{bid}/result",
        headers=WORKER_HEADERS,
        json={"attempt": 1, "status": "pending", "last_error": "本轮没号，继续抢", "result": None},
    )
    assert r.status_code == 204
    db.expire_all()
    booking = db.get(Booking, bid)
    assert booking.status == BookingStatus.pending
    assert booking.started_at is None
    assert booking.finished_at is None
    assert booking.last_error == "本轮没号，继续抢"


def test_worker_can_read_booking_status(client, ready_user):
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    client.post("/api/worker/claim", headers=WORKER_HEADERS)

    r = client.get(f"/api/worker/bookings/{bid}/status?attempt=1", headers=WORKER_HEADERS)
    assert r.status_code == 200
    assert r.json() == {"id": bid, "status": "running", "attempt": 1}


def test_worker_report_progress_updates_summary(client, ready_user, db):
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    client.post("/api/worker/claim", headers=WORKER_HEADERS)

    r = client.post(
        f"/api/worker/bookings/{bid}/progress",
        headers=WORKER_HEADERS,
        json={"attempt": 1, "message": "考点 274 查询结果 no_appointments"},
    )
    assert r.status_code == 204
    db.expire_all()
    booking = db.get(Booking, bid)
    assert booking.progress_rounds == 1
    assert booking.last_progress == "考点 274 查询结果 no_appointments"
    assert booking.last_progress_at is not None


def test_worker_report_requires_key(client, ready_user):
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    r = client.post(f"/api/worker/bookings/{bid}/result", headers={"X-Worker-Key": "wrong"},
                    json={"attempt": 1, "status": "done"})
    assert r.status_code == 401


def _requeue_and_reclaim(client, bid: int) -> int:
    """模拟 reaper 重排 + 新 worker 接管，返回新的 attempt（fencing token）。"""
    client.post(
        f"/api/worker/bookings/{bid}/result",
        headers=WORKER_HEADERS,
        json={"attempt": 1, "status": "pending", "last_error": "超时重排", "result": None},
    )
    return client.post("/api/worker/claim", headers=WORKER_HEADERS).json()["attempt"]


def test_stale_attempt_result_rejected(client, ready_user, db):
    """S1 fencing：任务被重排重新认领后，慢 worker 用旧 attempt 的回写被拒，不覆盖新运行。"""
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    assert client.post("/api/worker/claim", headers=WORKER_HEADERS).json()["attempt"] == 1
    assert _requeue_and_reclaim(client, bid) == 2  # worker B 接管 → attempt 2

    # 慢 worker A 用旧 attempt=1 回报 done → 被拒，任务仍 running（B 的运行未被覆盖）
    stale = client.post(
        f"/api/worker/bookings/{bid}/result",
        headers=WORKER_HEADERS,
        json={"attempt": 1, "status": "done", "result": {"confirmation_no": "A"}},
    )
    assert stale.status_code == 409
    db.expire_all()
    booking = db.get(Booking, bid)
    assert booking.status == BookingStatus.running
    assert booking.result is None

    # worker B 用当前 attempt=2 回报 done → 成功
    ok = client.post(
        f"/api/worker/bookings/{bid}/result",
        headers=WORKER_HEADERS,
        json={"attempt": 2, "status": "done", "result": {"confirmation_no": "B"}},
    )
    assert ok.status_code == 204
    db.expire_all()
    booking = db.get(Booking, bid)
    assert booking.status == BookingStatus.done
    assert booking.result == {"confirmation_no": "B"}


def test_stale_attempt_progress_rejected(client, ready_user):
    """重排重认领后，旧 attempt 的进度上报被拒。"""
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    client.post("/api/worker/claim", headers=WORKER_HEADERS)
    _requeue_and_reclaim(client, bid)
    r = client.post(
        f"/api/worker/bookings/{bid}/progress",
        headers=WORKER_HEADERS,
        json={"attempt": 1, "message": "stale"},
    )
    assert r.status_code == 409


def test_stale_attempt_status_rejected(client, ready_user):
    """重排重认领后，旧 attempt 查询 status 返回 409（worker 据此停止本轮）。"""
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    client.post("/api/worker/claim", headers=WORKER_HEADERS)
    _requeue_and_reclaim(client, bid)
    assert client.get(f"/api/worker/bookings/{bid}/status?attempt=1", headers=WORKER_HEADERS).status_code == 409
    assert client.get(f"/api/worker/bookings/{bid}/status?attempt=2", headers=WORKER_HEADERS).status_code == 200


def test_worker_result_rejects_running(client, ready_user, db):
    """ISSUE-003：worker result 不得写入 running（会造出 finished_at 已设的不一致态）。"""
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    client.post("/api/worker/claim", headers=WORKER_HEADERS)
    r = client.post(
        f"/api/worker/bookings/{bid}/result",
        headers=WORKER_HEADERS,
        json={"attempt": 1, "status": "running", "last_error": None, "result": None},
    )
    assert r.status_code == 422
    db.expire_all()
    booking = db.get(Booking, bid)
    assert booking.status == BookingStatus.running
    assert booking.finished_at is None


def test_worker_result_rejects_cancelled(client, ready_user, db):
    """ISSUE-003：worker result 不得写入 cancelled（仅用户取消路径可写）。"""
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    client.post("/api/worker/claim", headers=WORKER_HEADERS)
    r = client.post(
        f"/api/worker/bookings/{bid}/result",
        headers=WORKER_HEADERS,
        json={"attempt": 1, "status": "cancelled", "last_error": None, "result": None},
    )
    assert r.status_code == 422
    db.expire_all()
    assert db.get(Booking, bid).status == BookingStatus.running


def test_worker_result_still_accepts_done_failed_pending(client, ready_user, db):
    """回归：合法的 done 仍能写终态，验证白名单没误伤正常回报。"""
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    client.post("/api/worker/claim", headers=WORKER_HEADERS)
    r = client.post(
        f"/api/worker/bookings/{bid}/result",
        headers=WORKER_HEADERS,
        json={"attempt": 1, "status": "failed", "last_error": "网站维护", "result": None},
    )
    assert r.status_code == 204
    db.expire_all()
    assert db.get(Booking, bid).status == BookingStatus.failed
