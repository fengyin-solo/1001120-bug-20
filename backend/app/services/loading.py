"""装卸任务业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "loading"
REQUIRED_FIELDS = ["任务编号", "关联航次", "作业类型"]
RESULT_FIELDS = ["计划箱量", "完成箱量", "作业班组", "开始时间"]
STATUS_ORDER = ["待开工", "作业中", "待复核", "已完成"]
ACTION_RULES = {"确认开工": "作业中", "提交复核": "待复核", "确认完成": "已完成"}
# 每个动作允许从哪些状态发起；已处于目标状态的重复提交按幂等处理，只保留一次结果
ACTION_SOURCES = {
    "确认开工": {"待开工"},
    "提交复核": {"作业中", "已完成"},  # 已完成可退回复核，完成箱量保留不丢
    "确认完成": {"待复核"},
}
NEGATIVE_ACTIONS: list[str] = []


def _is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _to_number(value: Any) -> float:
    """把完成箱量这类字段宽容地转成数值，转不了的按 0 计。"""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


class LoadingService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        missing_gang: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("任务编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if missing_gang:
            rows = [row for row in rows if _is_blank(row.get("作业班组"))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def summary(self) -> dict[str, Any]:
        """看板口径：按 status 统计各状态任务数，完成箱量只合计已完成任务。"""
        rows = store.rows(MODULE)
        status_counts = {status: 0 for status in STATUS_ORDER}
        for row in rows:
            name = str(row.get("status", ""))
            if name in status_counts:
                status_counts[name] += 1
        completed_quantity = sum(
            _to_number(row.get("完成箱量"))
            for row in rows
            if row.get("status") == STATUS_ORDER[-1]
        )
        return {
            "status_counts": status_counts,
            "completed_quantity": completed_quantity,
            "missing_gang": sum(1 for row in rows if _is_blank(row.get("作业班组"))),
        }

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if _is_blank(values.get(field))]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in RESULT_FIELDS:
            value = values.get(field)
            if _is_blank(value):
                entry[field] = 0 if field in ("计划箱量", "完成箱量") else ""
            else:
                entry[field] = value
        entry["status"] = STATUS_ORDER[0]
        entry["任务状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
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
        current = str(entry.get("status", ""))
        if current != target and current not in ACTION_SOURCES[action]:
            return None, f"装卸任务当前为「{current}」，不能{action}"
        # 结果字段只接受非空提交：重复提交、退回复核都不会把已确认的完成箱量冲掉
        for field in RESULT_FIELDS:
            value = (values or {}).get(field)
            if not _is_blank(value):
                entry[field] = value
        entry["status"] = target
        entry["任务状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"装卸任务已{action}"
