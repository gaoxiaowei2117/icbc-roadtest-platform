"""UserUpdate 档案字段的 schema 层校验（纯 Pydantic，不依赖 DB）。

覆盖之前审查发现的"档案输入未在后端校验"问题：pos_ids 存在性、
日期区间顺序、时间格式、星期/时段取值、exam_class 语义。

本文件把 conftest 的两个 autouse DB fixture 覆盖为 no-op，
使其无需 Postgres 即可运行。
"""
from datetime import date

import pytest
from pydantic import ValidationError

from app.api.pos import valid_pos_ids
from app.schemas.user import UserUpdate


@pytest.fixture(scope="session", autouse=True)
def _schema():
    # 覆盖 conftest 的建表 fixture：schema 测试不碰 DB。
    yield


@pytest.fixture(autouse=True)
def _clean():
    # 覆盖 conftest 的 TRUNCATE fixture：schema 测试不碰 DB。
    yield


@pytest.fixture(scope="session")
def a_pos_id() -> int:
    """一个真实存在的合法 posID。"""
    return next(iter(valid_pos_ids()))


# ---------- 合法输入 ----------

def test_valid_full_profile(a_pos_id):
    u = UserUpdate(
        icbc_license_no="1234567",
        icbc_last_name="GAO",
        exam_class="5",
        pos_ids=[a_pos_id],
        expect_after_date=date(2026, 7, 1),
        expect_before_date=date(2026, 8, 1),
        expect_time_range="09:00-17:00",
        pref_days_of_week=[0, 1, 2, 3, 4],
        pref_parts_of_day=[0, 1],
    )
    assert u.pos_ids == [a_pos_id]
    assert u.expect_time_range == "09:00-17:00"


def test_all_none_is_valid():
    """PATCH 语义：未提交的字段（None）应全部放行。"""
    u = UserUpdate()
    assert u.pos_ids is None
    assert u.expect_time_range is None


def test_boundary_time_and_days(a_pos_id):
    u = UserUpdate(
        expect_time_range="00:00-23:59",
        pref_days_of_week=[0, 6],
        pref_parts_of_day=[0, 1],
    )
    assert u.expect_time_range == "00:00-23:59"


def test_equal_dates_allowed():
    u = UserUpdate(
        expect_after_date=date(2026, 7, 1),
        expect_before_date=date(2026, 7, 1),
    )
    assert u.expect_after_date == u.expect_before_date


# ---------- 去重 ----------

def test_pos_ids_deduped(a_pos_id):
    u = UserUpdate(pos_ids=[a_pos_id, a_pos_id])
    assert u.pos_ids == [a_pos_id]


def test_days_deduped_preserving_order():
    u = UserUpdate(pref_days_of_week=[6, 0, 6, 0])
    assert u.pref_days_of_week == [6, 0]


def test_parts_deduped():
    u = UserUpdate(pref_parts_of_day=[1, 0, 1])
    assert u.pref_parts_of_day == [1, 0]


# ---------- exam_class 取值 ----------

@pytest.mark.parametrize("cls", ["5", "6", "7", "8"])
def test_valid_exam_class(cls):
    # 可在线预约 road test 的班级：5、6、7、8（8 = 摩托车 novice）。
    assert UserUpdate(exam_class=cls).exam_class == cls


@pytest.mark.parametrize("cls", ["1", "2", "3", "4"])
def test_commercial_exam_class_rejected(cls):
    # 商用类 1-4 需电话/线下预约，本平台不支持。
    with pytest.raises(ValidationError):
        UserUpdate(exam_class=cls)


# ---------- 非法输入 ----------

def test_bad_exam_class():
    with pytest.raises(ValidationError):
        UserUpdate(exam_class="9")


def test_bad_exam_class_non_numeric():
    with pytest.raises(ValidationError):
        UserUpdate(exam_class="C5")


def test_unknown_pos_id():
    with pytest.raises(ValidationError):
        UserUpdate(pos_ids=[999_999_999])


def test_too_many_pos_ids():
    with pytest.raises(ValidationError):
        UserUpdate(pos_ids=list(range(1, 60)))


def test_weekday_out_of_range():
    with pytest.raises(ValidationError):
        UserUpdate(pref_days_of_week=[7])


def test_weekday_negative():
    with pytest.raises(ValidationError):
        UserUpdate(pref_days_of_week=[-1])


def test_part_out_of_range():
    with pytest.raises(ValidationError):
        UserUpdate(pref_parts_of_day=[2])


def test_time_range_bad_format():
    with pytest.raises(ValidationError):
        UserUpdate(expect_time_range="9am-5pm")


def test_time_range_bad_hour():
    with pytest.raises(ValidationError):
        UserUpdate(expect_time_range="24:00-25:00")


def test_time_range_start_not_before_end():
    with pytest.raises(ValidationError):
        UserUpdate(expect_time_range="17:00-09:00")


def test_time_range_equal_start_end():
    with pytest.raises(ValidationError):
        UserUpdate(expect_time_range="09:00-09:00")


def test_date_before_earlier_than_after():
    with pytest.raises(ValidationError):
        UserUpdate(
            expect_after_date=date(2026, 8, 1),
            expect_before_date=date(2026, 7, 1),
        )
