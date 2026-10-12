"""Reproducible SUFFOLK / HELIX construction-only audit for Primavera P6 XER.

All scopes are resolved through real P6 code assignments and WBS ancestry.
No original XER fields or Activity IDs are re-coded.
"""
from __future__ import annotations

import pandas as pd


def construction_wbs_ids(tables: dict, project_id: str) -> set[str]:
    w = tables["PROJWBS"].copy()
    w = w[w["proj_id"].astype(str).eq(str(project_id))]
    roots = w[w["wbs_name"].fillna("").str.strip().str.casefold().eq("construction")]
    if len(roots) != 1:
        raise ValueError(f"Expected exactly one Construction WBS in project {project_id}, found {len(roots)}")
    descendants = {str(roots.iloc[0]["wbs_id"])}
    children = {}
    for row in w.itertuples():
        children.setdefault(str(row.parent_wbs_id), []).append(str(row.wbs_id))
    todo = list(descendants)
    while todo:
        next_id = todo.pop()
        for child in children.get(next_id, []):
            if child not in descendants:
                descendants.add(child)
                todo.append(child)
    return descendants


def scoped_helix_construction(tables: dict, project_id: str, helix_ids: set[str]) -> pd.DataFrame:
    from src.xer import to_task_frame
    tasks = to_task_frame(tables["TASK"])
    tasks = tasks[tasks["proj_id"].astype(str).eq(str(project_id))].copy()
    construction_ids = construction_wbs_ids(tables, project_id)
    return tasks[
        tasks["task_id"].astype(str).isin(helix_ids)
        & tasks["wbs_id"].astype(str).isin(construction_ids)
    ].copy()


def build_activity_audit(
    current_all: pd.DataFrame, current_helix_ids: set[str],
    current_active: pd.DataFrame, baseline_active: pd.DataFrame,
    previous_active: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """Track active activities, reassigned/archived IDs and unmatched baseline codes."""
    active = current_active.copy()
    baseline = baseline_active.set_index("task_code", drop=False)
    prev = (
        previous_active.set_index("task_code", drop=False)
        if previous_active is not None and not previous_active.empty
        else pd.DataFrame()
    )
    act = []
    for _, r in active.sort_values("task_code").iterrows():
        code = str(r["task_code"])
        b = baseline.loc[code] if code in baseline.index else None
        p = prev.loc[code] if not prev.empty and code in prev.index else None
        act.append({
            "Activity ID": code,
            "Activity Name": str(r.get("task_name", "")),
            "WBS ID": str(r.get("wbs_id", "")),
            "QTS - Subcontractor": "HELIX",
            "Status Current": str(r.get("Status", "")),
            "Status Previous": str(p.get("Status", "")) if p is not None else "Not in previous",
            "Baseline Start": str(b.get("target_start_date", "")) if b is not None else "",
            "Baseline Finish": str(b.get("target_end_date", "")) if b is not None else "",
            "Current Start": str(r.get("act_start_date") if pd.notna(r.get("act_start_date")) else r.get("early_start_date", "")),
            "Current Finish": str(r.get("act_end_date") if pd.notna(r.get("act_end_date")) else r.get("reend_date", "")),
            "Previous Finish": str(p.get("reend_date", "")) if p is not None else "",
            "Remaining Duration (h)": r.get("remain_drtn_hr_cnt"),
            "Total Float (h)": r.get("total_float_hr_cnt"),
            "Audit": "MATCHED BL" if b is not None else "NO BASELINE MATCH",
        })
    active_df = pd.DataFrame(act)

    current_helix = current_all[
        current_all["task_id"].astype(str).isin(current_helix_ids)
    ].copy()
    active_codes = set(active["task_code"].astype(str))
    inactive = current_helix[
        ~current_helix["task_code"].astype(str).isin(active_codes)
    ]
    inactive_codes = set(inactive["task_code"].astype(str))
    previous_codes = set(prev.index.astype(str)) if not prev.empty else set()
    cur_all_codes = set(current_all["task_code"].astype(str))
    removed = sorted(previous_codes - active_codes)
    departures = []
    for code in removed:
        p = prev.loc[code]
        i = inactive[inactive["task_code"].astype(str).eq(code)]
        is_archived = not i.empty
        departures.append({
            "Activity ID": code,
            "Previous Name": str(p.get("task_name", "")),
            "Previous Status": str(p.get("Status", "")),
            "Current Location": "OUTSIDE CONSTRUCTION (ARCHIVED)" if is_archived else
                ("NO LONGER QTS-HELIX CONSTRUCTION" if code in cur_all_codes else "NOT IN CURRENT XER"),
            "Current WBS ID": str(i.iloc[0]["wbs_id"]) if is_archived else "",
            "Audit": "EXCLUDED FROM ACTIVE COUNTS",
        })
    excluded = pd.DataFrame(departures)
    summary = pd.DataFrame([
        {"Metric": "Current HELIX construction", "Value": len(active)},
        {"Metric": "Matched to Baseline by Activity ID", "Value": len(active_codes & set(baseline.index.astype(str)))},
        {"Metric": "Current HELIX outside Construction", "Value": len(inactive)},
        {"Metric": "Former HELIX construction no longer active", "Value": len(removed)},
        {"Metric": "Of which still in Current outside Construction", "Value": len(inactive_codes & previous_codes)},
        {"Metric": "Previous HELIX construction", "Value": len(previous_codes)},
        {"Metric": "New active HELIX IDs not in Previous", "Value": len(active_codes - previous_codes)},
    ])
    return {"summary": summary, "active": active_df, "departures": excluded}
