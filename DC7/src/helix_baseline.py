"""Official independent DC7 HELIX baseline: WBS line-up structure and audit.

This module NEVER derives HELIX baseline data from the SUFFOLK update.
It NEVER makes activity progress or completion forecasts from a baseline.
"""
from __future__ import annotations

import re
from typing import Mapping

import pandas as pd

from src.xer import to_task_frame


HALLS = tuple(f"DH{n}00" for n in range(11, 17))
LETTERS = ("A", "B", "C", "D", "E", "F", "G", "H", "J", "K")


def lineup_order(area: str) -> tuple[str, ...]:
    """P6 WBS line-up ordering shown in the HELIX DC7 baseline screenshots."""
    if area not in HALLS:
        raise ValueError(f"Unknown HELIX Data Hall {area}")
    number = int(area[2:4])
    suffix = f"{number}0"
    order = (("R",) + LETTERS) if number % 2 == 0 else (LETTERS + ("R",))
    return tuple(f"{letter}{suffix}" for letter in order)


def baseline_outline() -> dict[str, list[dict]]:
    """Navigation skeleton only. Empty metrics mean no official XER is loaded."""
    result = {}
    for hall in HALLS:
        result[hall] = [
            {"WBS Level": "Electrical", "Line-Up": value}
            for value in lineup_order(hall)
        ] + [{"WBS Level": "Commissioning", "Line-Up": "Commissioning"}]
    result["MOH"] = [{"WBS Level": "Equipment", "Line-Up": "Equipment"}]
    return result


def summarize_approved_baseline(tables: Mapping[str, pd.DataFrame], project_id: str) -> dict[str, pd.DataFrame]:
    """Resolve the exact original WBS of the approved HELIX independent baseline.

    Return ordered electrical line-ups plus Commissioning for each hall, and
    MOH / Equipment. Counts and baseline dates derive only from original tasks.
    The returned data never include status-based current progress calculations.
    """
    wbs = tables["PROJWBS"]
    wbs = wbs[wbs["proj_id"].astype(str).eq(str(project_id))]
    names = dict(zip(wbs["wbs_id"].astype(str), wbs["wbs_name"].fillna("").astype(str)))
    parents = dict(zip(wbs["wbs_id"].astype(str), wbs["parent_wbs_id"].astype(str)))
    task = to_task_frame(tables["TASK"])
    task = task[task["proj_id"].astype(str).eq(str(project_id))].copy()
    if task.empty:
        raise ValueError("Approved HELIX baseline contains no tasks in selected project")

    def ancestry(wbs_id):
        out, node, seen = [], str(wbs_id), set()
        while node in names:
            if node in seen:
                raise ValueError(f"Cycle detected in HELIX P6 WBS: {node}")
            seen.add(node)
            out.append(names[node])
            node = parents.get(node, "")
        return list(reversed(out))

    def category(path: list[str]) -> tuple[str | None, str | None]:
        for n in range(11, 17):
            hall = f"DH{n}00"
            hall_match = f"DH {n}00"
            matches = [i for i, label in enumerate(path) if re.fullmatch(r"DH\s*"+str(n)+r"00", label, re.I)]
            if not matches:
                continue
            position = matches[-1]
            remaining = path[position+1:]
            if not remaining:
                return hall, None
            if remaining[0].strip().casefold() == "electrical" and len(remaining) >= 2:
                lineup = remaining[1].strip().upper()
                if lineup in lineup_order(hall):
                    return hall, lineup
            if remaining[0].strip().casefold() == "commissioning":
                return hall, "Commissioning"
            return hall, None
        if "MOH" in [x.strip().upper() for x in path]:
            i = [x.strip().upper() for x in path].index("MOH")
            if any(x.strip().casefold() == "equipment" for x in path[i+1:]):
                return "MOH", "Equipment"
            return "MOH", None
        return None, None

    paths = task["wbs_id"].astype(str).map(ancestry)
    identified = paths.map(category)
    task["_Area"] = identified.map(lambda t: t[0])
    task["_LineUp"] = identified.map(lambda t: t[1])
    task["_P6 WBS"] = paths.map(lambda t: " / ".join(t))
    task["_Start"] = pd.to_datetime(task.get("target_start_date"), errors="coerce")
    task["_Finish"] = pd.to_datetime(task.get("target_end_date"), errors="coerce")
    if not task["_Start"].notna().any():
        task["_Start"] = pd.to_datetime(task.get("early_start_date"), errors="coerce")
    if not task["_Finish"].notna().any():
        task["_Finish"] = pd.to_datetime(task.get("early_end_date"), errors="coerce")
    if task["task_id"].duplicated().any():
        raise ValueError("Duplicate task_id in independent HELIX baseline")
    if task["_Start"].notna().any() and task["_Finish"].notna().any():
        bad = task[task["_Start"].notna() & task["_Finish"].notna() & (task["_Finish"] < task["_Start"])]
        if not bad.empty:
            raise ValueError(f"Invalid baseline dates: {bad['task_code'].tolist()[:10]}")

    grouped = {}
    for area, outline in baseline_outline().items():
        rows = []
        for placeholder in outline:
            code = placeholder["Line-Up"]
            found = task[task["_Area"].eq(area) & task["_LineUp"].eq(code)]
            rows.append({
                "WBS Level": placeholder["WBS Level"],
                "Line-Up": code,
                "Baseline Tasks": int(len(found)),
                "Baseline Start": found["_Start"].min() if not found.empty else pd.NaT,
                "Baseline Finish": found["_Finish"].max() if not found.empty else pd.NaT,
            })
        grouped[area] = pd.DataFrame(rows)
    # Any non-mapped tasks remain outside this structural view; provide them
    # to the audit rather than inventing a line-up destination.
    all_task_rows = []
    for _, item in task.iterrows():
        all_task_rows.append({
            "Activity ID": str(item.get("task_code","")),
            "Activity Name": str(item.get("task_name","")),
            "Data Hall": item["_Area"] or "",
            "P6 WBS": item["_P6 WBS"],
            "Line-Up": item["_LineUp"] or "",
            "Classification": "MAPPED" if item["_LineUp"] is not None else "NOT IN SELECTED LINE-UP WBS",
        })
    grouped["_audit"] = pd.DataFrame(all_task_rows)
    # The baseline cannot be treated as a Current.
    return grouped
