from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional
import pandas as pd

ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


def _read_text(path: Path) -> str:
    for enc in ENCODINGS:
        try:
            return path.read_text(encoding=enc, errors="strict")
        except UnicodeDecodeError:
            pass
    return path.read_text(encoding="latin-1", errors="replace")


def parse_xer(path: str | Path, wanted_tables: Optional[Iterable[str]] = None) -> Dict[str, pd.DataFrame]:
    path = Path(path)
    wanted = {x.upper() for x in wanted_tables} if wanted_tables else None
    tables: dict[str, list[dict]] = {}
    current = None
    fields: list[str] = []
    for line in _read_text(path).splitlines():
        if not line:
            continue
        parts = line.split("\t")
        marker = parts[0].strip()
        if marker == "%T":
            current = parts[1].strip().upper() if len(parts) > 1 else None
            fields = []
            if current and (wanted is None or current in wanted):
                tables.setdefault(current, [])
        elif marker == "%F":
            fields = [x.strip() for x in parts[1:]]
        elif marker == "%R" and current and fields:
            if wanted is not None and current not in wanted:
                continue
            vals = parts[1:]
            if len(vals) < len(fields):
                vals += [""] * (len(fields) - len(vals))
            elif len(vals) > len(fields):
                vals = vals[: len(fields) - 1] + ["\t".join(vals[len(fields) - 1 :])]
            tables.setdefault(current, []).append(dict(zip(fields, vals)))
    return {k: pd.DataFrame(v) for k, v in tables.items()}


def to_task_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    date_cols = [
        "act_start_date", "act_end_date", "target_start_date", "target_end_date",
        "early_start_date", "early_end_date", "late_start_date", "late_end_date",
        "restart_date", "reend_date", "expect_end_date", "rem_late_start_date", "rem_late_end_date",
    ]
    for c in date_cols:
        if c in out.columns:
            out[c] = pd.to_datetime(out[c], errors="coerce")
    for c in ["target_drtn_hr_cnt", "remain_drtn_hr_cnt", "total_float_hr_cnt", "phys_complete_pct"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    if "status_code" in out.columns:
        m = {
            "TK_COMPLETE": "Completed", "TK_COMPLETE ": "Completed",
            "TK_ACTIVE": "In Progress", "TK_NOTSTART": "Not Started",
        }
        out["Status"] = out["status_code"].fillna("").astype(str).str.upper().map(m).fillna("Unknown")
    else:
        out["Status"] = "Unknown"
    return out
