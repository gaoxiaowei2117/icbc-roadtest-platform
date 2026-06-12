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


def test_worker_report_completes_booking(client, ready_user, db):
    """F5 回归：回报结果不再 NameError，任务进入终态。"""
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    client.post("/api/worker/claim", headers=WORKER_HEADERS)

    r = client.post(f"/api/worker/bookings/{bid}/result", headers=WORKER_HEADERS,
                    json={"status": "done", "last_error": None,
                          "result": {"confirmation_no": "CONF-1"}})
    assert r.status_code == 204
    db.expire_all()
    booking = db.get(Booking, bid)
    assert booking.status == BookingStatus.done
    assert booking.result == {"confirmation_no": "CONF-1"}


def test_worker_report_requires_key(client, ready_user):
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    r = client.post(f"/api/worker/bookings/{bid}/result", headers={"X-Worker-Key": "wrong"},
                    json={"status": "done"})
    assert r.status_code == 401
