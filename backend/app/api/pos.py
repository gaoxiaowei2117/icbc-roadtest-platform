"""考点字典：GET /api/pos-list，供前端下拉。"""
import csv
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["pos"])

_CSV = Path(__file__).resolve().parent.parent / "data" / "icbc_pos_list.csv"


@lru_cache
def _load_pos() -> list[dict]:
    out: list[dict] = []
    with _CSV.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("考场名称") or "").strip()
            pos_id = (row.get("posID") or "").strip()
            if name and pos_id.isdigit():
                out.append({"name": name, "pos_id": int(pos_id)})
    return out


@lru_cache
def valid_pos_ids() -> frozenset[int]:
    """合法 posID 集合，供档案校验做存在性检查。"""
    return frozenset(p["pos_id"] for p in _load_pos())


@router.get("/pos-list")
def pos_list() -> list[dict]:
    return _load_pos()
