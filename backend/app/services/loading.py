"""装卸任务业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "loading"
REQUIRED_FIELDS = ["任务编号", "关联航次", "作业类型"]
STATUS_ORDER = ["待开工", "作业中", "待复核", "已完成"]
ACTION_RULES = {"确认开工": "作业中", "提交复核": "待复核", "确认完成": "已完成"}
# 每个动作只允许从指定状态发起，保证任务只能沿着状态序列往前走。
ACTION_SOURCES = {"确认开工": "待开工", "提交复核": "作业中", "确认完成": "待复核"}
# 登记时允许顺带落库的选填字段，缺省不补、提交不丢。
OPTIONAL_FIELDS = ["计划箱量", "完成箱量", "作业班组", "开始时间"]


def _parse_quantity(value: Any) -> int | None:
    """把提交上来的箱量收敛成非负整数；无法辨认时返回 None。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = int(value)
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            number = int(float(text))
        except ValueError:
            return None
    return number if number >= 0 else None


def _quantity_of(entry: dict[str, Any], field: str) -> int:
    return _parse_quantity(entry.get(field)) or 0


def _has_crew(entry: dict[str, Any]) -> bool:
    return bool(str(entry.get("作业班组") or "").strip())


def _sync_flags(entry: dict[str, Any]) -> None:
    """根据当前状态与字段重算派生标记，保证列表、详情与运营概览读到同一份结论。"""
    entry["任务状态"] = str(entry.get("status") or STATUS_ORDER[0])
    entry["pending"] = entry.get("status") != STATUS_ORDER[-1]
    entry["abnormal"] = not _has_crew(entry)


class LoadingService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        abnormal: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        for row in rows:
            _sync_flags(row)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("任务编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if abnormal:
            rows = [row for row in rows if not _has_crew(row)]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is not None:
            _sync_flags(entry)
        return entry

    def stats(self) -> list[dict[str, Any]]:
        """汇总装卸任务看板卡片：待开工、作业中、今日完成箱量与缺班组任务。"""
        rows = store.rows(MODULE)
        today = date.today().isoformat()
        finished_today = sum(
            _quantity_of(row, "完成箱量")
            for row in rows
            if row.get("status") == STATUS_ORDER[-1] and row.get("完成时间") == today
        )
        return [
            {"label": "待开工任务", "value": sum(1 for row in rows if row.get("status") == STATUS_ORDER[0])},
            {"label": "作业中任务", "value": sum(1 for row in rows if row.get("status") == STATUS_ORDER[1])},
            {"label": "今日完成箱量", "value": finished_today},
            {"label": "缺班组任务", "value": sum(1 for row in rows if not _has_crew(row))},
        ]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        for field in OPTIONAL_FIELDS:
            if str(values.get(field) or "").strip():
                entry[field] = values.get(field)
        entry.setdefault("完成箱量", 0)
        _sync_flags(entry)
        rows.append(entry)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"装卸任务 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于装卸任务可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        current = str(entry.get("status") or STATUS_ORDER[0])
        if current == target:
            # 重复提交：保留首次结果，不再改写完成箱量等字段。
            _sync_flags(entry)
            return entry, f"装卸任务已是「{target}」，重复{action}已忽略，保留首次结果"
        if current != ACTION_SOURCES[action]:
            expect = next((name for name, source in ACTION_SOURCES.items() if source == current), None)
            if expect is None:
                return None, f"装卸任务已是「{STATUS_ORDER[-1]}」，无需再执行「{action}」"
            return None, f"装卸任务当前为「{current}」，请先{expect}再{action}"
        values = values or {}
        quantity = _parse_quantity(values.get("完成箱量"))
        if action == "提交复核" and quantity is None and str(values.get("完成箱量") or "").strip():
            return None, "完成箱量必须是非负整数，本次未提交"
        crew = str(values.get("作业班组") or "").strip()
        if crew:
            entry["作业班组"] = crew
        if action == "提交复核":
            if quantity is not None:
                entry["完成箱量"] = quantity
            elif _quantity_of(entry, "完成箱量") == 0:
                # 首次提交复核又没填完成箱量时，按计划箱量补齐，之后不再覆盖。
                entry["完成箱量"] = _quantity_of(entry, "计划箱量")
        entry["status"] = target
        if action == "确认完成":
            entry["完成时间"] = date.today().isoformat()
        _sync_flags(entry)
        return entry, f"装卸任务已{action}"
