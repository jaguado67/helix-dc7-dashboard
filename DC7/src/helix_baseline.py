"""DC7 approved HELIX-only independent P6 baseline Line-Up and MOH audit.

Only TASK rows with QTS - Subcontractor = HELIX, under native
Data Hall / Electrical / Line-Up or MOH / Equipment WBS, qualify.
Commissioning, milestone tasks and third-party activities are excluded
from this display. They remain reconciled internally, never falsely
reassigned. Nothing here measures Current progress.
"""
from __future__ import annotations

import re
from typing import Mapping

import pandas as pd

from src.xer import to_task_frame

HALLS = tuple(f"DH{n}00" for n in range(11, 17))
LETTERS = ("A", "B", "C", "D", "E", "F", "G", "H", "J", "K")


def lineup_order(area: str) -> tuple[str, ...]:
    if area not in HALLS:
        raise ValueError(f"Unknown HELIX Data Hall: {area}")
    n = int(area[2:4])
    suffix = f"{n}0"
    letters = (("R",) + LETTERS) if n % 2 == 0 else (LETTERS + ("R",))
    return tuple(f"{x}{suffix}" for x in letters)


def baseline_outline() -> dict[str, list[dict]]:
    groups = {}
    for hall in HALLS:
        groups[hall] = [{"WBS Level": "Electrical", "Line-Up": x} for x in lineup_order(hall)]
    groups["MOH"] = [{"WBS Level": "Equipment", "Line-Up": "Equipment"}]
    return groups


def lineup_activity_summary(data: Mapping[str, pd.DataFrame] | None) -> pd.DataFrame:
    """Counts only HELIX-coded Electrical Line-Ups and MOH Equipment."""
    outline = baseline_outline()
    rows = []
    for area, items in outline.items():
        if data is None:
            rows.append({"Area":area, "Electrical Line-Ups":"—", "MOH Equipment":"—", "Total Activities":"Pendiente BL"})
            continue
        if area not in data:
            raise ValueError(f"Missing verified HELIX area {area}")
        frame = data[area]
        if list(zip(frame["WBS Level"],frame["Line-Up"])) != [(i["WBS Level"],i["Line-Up"]) for i in items]:
            raise ValueError(f"Line-Up WBS/order mismatch in {area}")
        if frame["Baseline Tasks"].isna().any() or (frame["Baseline Tasks"] < 0).any():
            raise ValueError(f"Invalid HELIX baseline quantities in {area}")
        elec = int(frame.loc[frame["WBS Level"].eq("Electrical"),"Baseline Tasks"].sum())
        moh = int(frame.loc[frame["WBS Level"].eq("Equipment"),"Baseline Tasks"].sum())
        rows.append({"Area":area,"Electrical Line-Ups":elec,"MOH Equipment":moh,"Total Activities":elec+moh})
    summary = pd.DataFrame(rows)
    if data is not None:
        audit = data["_audit"]
        if int(summary["Total Activities"].sum()) != len(audit):
            raise ValueError("HELIX Line-Up/MOH audit count differs from displayed totals")
        if not audit["Activity ID"].is_unique:
            raise ValueError("Duplicate HELIX Activity IDs in Line-Up/MOH audit")
        if not audit["QTS - Subcontractor"].eq("HELIX").all():
            raise ValueError("Non-HELIX activities entered restricted Line-Up/MOH counts")
    return summary


def summarize_approved_baseline(tables: Mapping[str, pd.DataFrame], project_id: str) -> dict[str, pd.DataFrame]:
    """Audit real HELIX-coded P6 TASK/PROJWBS/TASKACTV associations."""
    required = ("PROJWBS","TASK","ACTVTYPE","ACTVCODE","TASKACTV")
    for key in required:
        if key not in tables or tables[key].empty:
            raise ValueError(f"Missing P6 baseline table {key}")
    project_id = str(project_id)
    wbs = tables["PROJWBS"]
    wbs = wbs[wbs["proj_id"].astype(str).eq(project_id)]
    names = dict(zip(wbs["wbs_id"].astype(str),wbs["wbs_name"].fillna("").astype(str)))
    parents = dict(zip(wbs["wbs_id"].astype(str),wbs["parent_wbs_id"].astype(str)))

    type_rows = tables["ACTVTYPE"]
    types = type_rows[type_rows["actv_code_type"].fillna("").astype(str).str.strip().str.casefold().eq("qts - subcontractor")]
    if len(types) != 1:
        raise ValueError("Expected exactly one QTS - Subcontractor code type")
    code_type_id = str(types.iloc[0]["actv_code_type_id"])
    code_rows = tables["ACTVCODE"]
    code_rows = code_rows[code_rows["actv_code_type_id"].astype(str).eq(code_type_id)]
    codes = dict(zip(code_rows["actv_code_id"].astype(str),code_rows["short_name"].fillna("").astype(str).str.strip().str.upper()))
    if list(codes.values()).count("HELIX") != 1:
        raise ValueError("Expected exactly one HELIX subcontractor code")

    assignments = tables["TASKACTV"]
    assignments = assignments[
        assignments["proj_id"].astype(str).eq(project_id)
        & assignments["actv_code_type_id"].astype(str).eq(code_type_id)
    ].copy()
    if assignments["task_id"].astype(str).duplicated().any():
        raise ValueError("Ambiguous duplicate subcontractor codes on P6 activities")
    assigned = dict(zip(assignments["task_id"].astype(str), assignments["actv_code_id"].astype(str)))
    if set(assigned.values()) - set(codes):
        raise ValueError("Unknown P6 subcontractor code assignment")

    task = to_task_frame(tables["TASK"])
    task = task[task["proj_id"].astype(str).eq(project_id)].copy()
    if task.empty or task["task_id"].astype(str).duplicated().any():
        raise ValueError("Missing or duplicated independent P6 baseline task IDs")
    if task["task_code"].astype(str).duplicated().any():
        raise ValueError("Duplicated Activity IDs in the HELIX baseline")
    task["_Sub"] = task["task_id"].astype(str).map(assigned).map(codes).fillna("(Unassigned)")

    def ancestry(wbs_id: str) -> list[str]:
        out, node, seen = [], str(wbs_id), set()
        while node in names:
            if node in seen:
                raise ValueError(f"Cycle in HELIX P6 WBS: {node}")
            seen.add(node)
            out.append(names[node])
            node = parents.get(node, "")
        return list(reversed(out))

    def identify(path: list[str]) -> tuple[str | None, str | None]:
        for hall in HALLS:
            n = hall[2:]
            at = next((i for i,x in enumerate(path) if re.fullmatch(r"DH\s*"+n,x.strip(),re.I)),None)
            if at is None: continue
            remaining = path[at+1:]
            if len(remaining)>=2 and remaining[0].strip().casefold()=="electrical":
                code=remaining[1].strip().upper()
                if code in lineup_order(hall):
                    return hall,code
            return None,None
        upper = [x.strip().upper() for x in path]
        if "MOH" in upper and "EQUIPMENT" in upper[upper.index("MOH")+1:]:
            return "MOH","Equipment"
        return None,None

    paths = task["wbs_id"].astype(str).map(ancestry)
    mapped = paths.map(identify)
    task["_Area"] = mapped.map(lambda x:x[0])
    task["_LineUp"] = mapped.map(lambda x:x[1])
    task["_WBS Path"] = paths.map(lambda x:" / ".join(x))
    task["_Included"] = task["_Sub"].eq("HELIX") & task["_LineUp"].notna()
    task["_Start"] = pd.to_datetime(task.get("target_start_date"),errors="coerce")
    task["_Finish"] = pd.to_datetime(task.get("target_end_date"),errors="coerce")
    if not task["_Start"].notna().any():
        task["_Start"]=pd.to_datetime(task.get("early_start_date"),errors="coerce")
    if not task["_Finish"].notna().any():
        task["_Finish"]=pd.to_datetime(task.get("early_end_date"),errors="coerce")

    included = task[task["_Included"]].copy()
    out = {}
    for area, items in baseline_outline().items():
        rows=[]
        for group in items:
            code=group["Line-Up"]
            g=included[included["_Area"].eq(area)&included["_LineUp"].eq(code)]
            rows.append({
                "WBS Level":group["WBS Level"],"Line-Up":code,
                "Baseline Tasks":int(len(g)),
                "Baseline Start":g["_Start"].min() if not g.empty else pd.NaT,
                "Baseline Finish":g["_Finish"].max() if not g.empty else pd.NaT,
            })
        out[area]=pd.DataFrame(rows)

    audit=pd.DataFrame({
        "Activity ID":included["task_code"].astype(str),
        "Activity Name":included["task_name"].astype(str),
        "Data Hall / MOH":included["_Area"].astype(str),
        "Line-Up":included["_LineUp"].astype(str),
        "QTS - Subcontractor":included["_Sub"].astype(str),
        "Original P6 WBS":included["_WBS Path"].astype(str),
        "Baseline Start":included["_Start"],
        "Baseline Finish":included["_Finish"],
    }).reset_index(drop=True)
    # Keep the excluded population for internal auditing only; don't make
    # "whole-XER reconciliation" a widget or downloadable HELIX scope audit.
    out["_audit"]=audit
    out["_internal_control"]={
        "total_source":int(len(task)),
        "HELIX_total":int(task["_Sub"].eq("HELIX").sum()),
        "HELIX_in_scope":int(len(included)),
        "HELIX_outside_scope":int((task["_Sub"].eq("HELIX") & ~task["_Included"]).sum()),
        "other_or_unassigned":int(task["_Sub"].ne("HELIX").sum()),
    }
    if sum((out["_internal_control"]["HELIX_in_scope"],out["_internal_control"]["HELIX_outside_scope"],out["_internal_control"]["other_or_unassigned"]))!=len(task):
        raise ValueError("HELIX source reconciliation failed")
    if len(task)==4689:
        if out["_internal_control"] != {
            "total_source":4689,"HELIX_total":4197,"HELIX_in_scope":4153,
            "HELIX_outside_scope":44,"other_or_unassigned":492
        }:
            raise ValueError(f"Official HELIX P6 baseline quantities changed: {out['_internal_control']}")
        summary=lineup_activity_summary(out)
        if summary.set_index("Area").loc[list(HALLS),"Total Activities"].tolist()!=[654]*6:
            raise ValueError("Official Data Hall HELIX activity counts failed")
        if int(summary.set_index("Area").loc["MOH","Total Activities"])!=229:
            raise ValueError("Official HELIX MOH activity count failed")
    return out
