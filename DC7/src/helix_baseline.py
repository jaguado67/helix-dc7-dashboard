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

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from src.xer import to_task_frame

HALLS = tuple(f"DH{n}00" for n in range(11, 17))
LETTERS = ("A", "B", "C", "D", "E", "F", "G", "H", "J", "K")



def us_federal_workday_delay(contractual_date, finish_date) -> int:
    """Signed Mon–Fri US federal working-day displacement, OPM holidays.

    Exclude the contractual boundary day and include the finish boundary
    only when it is a workday. For earlier finishes, reverse the interval
    and return a negative displacement. No site-specific P6 exceptions are
    silently assumed. Uses observed US federal holidays, not weekday-only
    approximations; do not call this P6 resource/contract calendar.
    """
    contract = pd.Timestamp(contractual_date).normalize()
    finish = pd.Timestamp(finish_date).normalize()
    if pd.isna(contract) or pd.isna(finish):
        raise ValueError("Both contractual and P6 Finish dates are required")
    if contract == finish:
        return 0
    earlier, later = sorted((contract, finish))
    holidays = USFederalHolidayCalendar().holidays(
        start=earlier - pd.DateOffset(years=1),
        end=later + pd.DateOffset(years=1),
    ).to_numpy(dtype="datetime64[D]")
    low = np.datetime64(earlier.date(), "D") + np.timedelta64(1, "D")
    high = np.datetime64(later.date(), "D") + np.timedelta64(1, "D")
    count = int(np.busday_count(low, high, holidays=holidays))
    return count if finish > contract else -count


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



def wbs_lineup_hierarchy(data: Mapping[str, pd.DataFrame] | None, area: str) -> pd.DataFrame:
    """Only HELIX Line-Up or MOH leaf rows, with P6 Baseline statuses.

    No Data Hall/Electrical subtotal rows: their titles are already
    displayed in the expander. Every status comes from each original
    HELIX-coded TASK.status_code, never inferred from RD or SUFFOLK.
    """
    outline = baseline_outline()
    if area not in outline:
        raise ValueError(f"Unknown Data Hall / MOH: {area}")
    lineups = [row["Line-Up"] for row in outline[area]]
    columns = ["Line-Up", "Total Activities", "Not Started", "In Progress", "Completed"]
    if data is None:
        return pd.DataFrame(
            [{"Line-Up": code, **{name: "Pendiente BL" for name in columns[1:]}}
             for code in lineups], columns=columns
        )
    if area not in data or "_audit" not in data:
        raise ValueError(f"Missing official HELIX baseline detail/audit for {area}")
    raw = data[area]
    if raw["Line-Up"].tolist() != lineups:
        raise ValueError(f"P6 Line-Up sequence does not match {area}")
    if not raw["WBS Level"].isin(("Electrical", "Equipment")).all():
        raise ValueError(f"Non-electrical or non-MOH WBS grouping: {area}")

    audit = data["_audit"]
    scoped = audit[audit["Data Hall / MOH"].eq(area)]
    if not scoped["Activity ID"].is_unique:
        raise ValueError(f"Duplicated original Activity IDs under {area}")
    if not scoped["QTS - Subcontractor"].eq("HELIX").all():
        raise ValueError(f"Out-of-scope subcontractor under {area}")

    rows = []
    for _, item in raw.iterrows():
        lineup = str(item["Line-Up"])
        matched = scoped[scoped["Line-Up"].eq(lineup)]
        total = int(item["Baseline Tasks"])
        if total != len(matched):
            raise ValueError(f"HELIX Activity ID count mismatch in {area}/{lineup}")
        counts = {name: int(matched["Status"].eq(name).sum())
                  for name in ("Not Started", "In Progress", "Completed")}
        if sum(counts.values()) != total:
            raise ValueError(f"Invalid or unknown P6 TASK.status_code in {area}/{lineup}")
        rows.append({"Line-Up": lineup, "Total Activities": total, **counts})

    table = pd.DataFrame(rows, columns=columns)
    if int(table["Total Activities"].sum()) != len(scoped):
        raise ValueError(f"Unreconciled Line-Up or MOH activity statuses: {area}")
    return table




def helix_baseline_overview(
    data: Mapping[str, pd.DataFrame],
    baseline_data_date=None,
) -> tuple[dict, pd.DataFrame]:
    """Audit-only HELIX baseline snapshot and planned cumulative activity curve.

    Source is exclusively 226021-HE.B, QTS-Subcontractor HELIX, in the
    six Data Hall Electrical Line-Ups and MOH/Equipment. There is no
    independent Current HELIX: NEVER create forecast or actual curves.
    """
    if data is None or "_audit" not in data:
        raise ValueError("Official HELIX independent baseline is required")
    audit = data["_audit"]
    if len(audit) != 4153 or not audit["Activity ID"].is_unique:
        raise ValueError("Unexpected HELIX baseline activity universe")
    if not audit["QTS - Subcontractor"].eq("HELIX").all():
        raise ValueError("SUFFOLK or third-party activities entered HELIX baseline overview")
    status = audit["Status"].value_counts()
    counts = {
        "Total": int(len(audit)),
        "Completed": int(status.get("Completed", 0)),
        "In Progress": int(status.get("In Progress", 0)),
        "Not Started": int(status.get("Not Started", 0)),
    }
    if counts["Completed"] + counts["In Progress"] + counts["Not Started"] != counts["Total"]:
        raise ValueError("Unrecognized independent HELIX baseline statuses")

    starts = pd.to_datetime(audit["Baseline Start"], errors="coerce")
    finishes = pd.to_datetime(audit["Baseline Finish"], errors="coerce")
    if finishes.isna().any() or starts.isna().any():
        raise ValueError("HELIX Baseline Start/Finish missing for scheduled activities")
    if (finishes < starts).any():
        raise ValueError("P6 HELIX baseline activities finish before their starts")

    dd = pd.to_datetime(baseline_data_date, errors="coerce")
    dd = pd.Timestamp(dd).normalize() if pd.notna(dd) else pd.NaT
    start = min(finishes.min().normalize(), dd) if pd.notna(dd) else finishes.min().normalize()
    end = finishes.max().normalize()
    if end < start:
        raise ValueError("HELIX baseline data date is later than every activity Finish")
    timeline = list(pd.date_range(
        start=start.replace(day=1),
        end=end + pd.offsets.MonthEnd(0),
        freq="ME",
    ))
    if pd.notna(dd) and start <= dd <= end:
        timeline.append(dd)
    timeline.append(end)
    grid = pd.DatetimeIndex(sorted(set(timeline)))
    planned = finishes.dt.normalize()
    series = pd.DataFrame({
        "Date": grid,
        "Baseline Planned Activities": [
            int(planned.le(d).sum()) for d in grid
        ],
    })
    if series.empty or int(series.iloc[-1]["Baseline Planned Activities"]) != counts["Total"]:
        raise ValueError("HELIX planned cumulative curve does not reconcile to 4153 Activity IDs")
    if not series["Baseline Planned Activities"].is_monotonic_increasing:
        raise ValueError("HELIX cumulative curve is not monotonic")
    info = {
        "Counts": counts,
        "Baseline Start": starts.min().normalize(),
        "Baseline Finish": end,
        "Baseline Data Date": dd,
        "Source": "226021-HE.B.xer",
    }
    return info, series



def helix_milestone_update_comparison(
    baseline_tables: Mapping[str, pd.DataFrame],
    update_tables: Mapping[str, pd.DataFrame],
) -> pd.DataFrame:
    """Factual P6 BL -> U01 milestone shift, with US federal working days.

    Includes all six Data Halls for the HELIX-owned independent project.
    DH1100's missing QTS-Subcontractor=HELIX code is explicitly labelled,
    never silently represented as a valid HELIX subcontractor assignment.
    """
    base=to_task_frame(baseline_tables["TASK"])
    current=to_task_frame(update_tables["TASK"])
    if base["task_code"].duplicated().any() or current["task_code"].duplicated().any():
        raise ValueError("Duplicate milestone Activity ID")
    bd=base.set_index("task_code")
    cu=current.set_index("task_code")

    ct=update_tables["ACTVTYPE"]
    typ=ct.loc[
        ct["actv_code_type"].fillna("").astype(str).str.casefold().eq("qts - subcontractor")
    ]
    if len(typ)!=1:
        raise ValueError("Independent HELIX P6 subcontractor coding not found")
    type_id=str(typ.iloc[0]["actv_code_type_id"])
    codes=update_tables["ACTVCODE"]
    code_ids=set(codes.loc[
        codes["actv_code_type_id"].astype(str).eq(type_id)
        & codes["short_name"].fillna("").astype(str).str.upper().eq("HELIX"),
        "actv_code_id"
    ].astype(str))
    assignments=update_tables["TASKACTV"]
    coded_ids=set(assignments.loc[
        assignments["actv_code_type_id"].astype(str).eq(type_id)
        & assignments["actv_code_id"].astype(str).isin(code_ids),
        "task_id"
    ].astype(str))
    from datetime import datetime
    patt=re.compile(r"\((\d{1,2}/\d{1,2}/(?:\d{4}|\d{2}))\)")
    def name_date(name):
        found=patt.findall(str(name))
        if len(found)!=1:
            return pd.NaT
        fmt="%m/%d/%Y" if len(found[0].split("/")[-1])==4 else "%m/%d/%y"
        return pd.Timestamp(datetime.strptime(found[0],fmt).date())
    rows=[]
    for category, prefix in (("QC 2.2","M"),("L4 Cx / IST","IST")):
        for hall in HALLS:
            activity=f"{prefix}.{hall[2:]}"
            if activity not in bd.index or activity not in cu.index:
                raise ValueError(f"Missing contractual milestone in HELIX BL/U01: {activity}")
            b=bd.loc[activity]
            u=cu.loc[activity]
            baseline_date=pd.to_datetime(b["target_end_date"],errors="coerce")
            if u["Status"]=="Completed":
                current_date=pd.to_datetime(u["act_end_date"],errors="coerce")
            else:
                current_date=pd.to_datetime(u["reend_date"],errors="coerce")
                if pd.isna(current_date):
                    current_date=pd.to_datetime(u["target_end_date"],errors="coerce")
            if pd.isna(baseline_date) or pd.isna(current_date):
                raise ValueError(f"Invalid P6 BL/current milestone Finish: {activity}")
            bdt,udt=baseline_date.normalize(),current_date.normalize()
            coding="HELIX" if str(u["task_id"]) in coded_ids else "Unassigned to HELIX"
            if hall!="DH1100" and coding!="HELIX":
                raise ValueError(f"Milestone coding regressed for {activity}")
            rows.append({
                "Data Hall":hall,
                "Milestone":category,
                "Activity ID":activity,
                "Baseline Date":bdt,
                "Current Finish Date":udt,
                "Variance (US working days)":-us_federal_workday_delay(bdt,udt),
                "Calendar Shift (days)":int((bdt-udt).days),
                "Status":str(u["Status"]),
                "Coding Audit":coding,
                "BL Activity Name Date":name_date(b["task_name"]),
                "U01 Activity Name Date":name_date(u["task_name"]),
            })
    result=pd.DataFrame(rows)
    if len(result)!=12 or result["Activity ID"].duplicated().any():
        raise ValueError("HELIX QC/IST milestone audit must contain exactly 12 IDs")
    return result


def helix_current_overview(
    baseline: Mapping[str, pd.DataFrame],
    update: Mapping[str, pd.DataFrame],
    update_tables: Mapping[str, pd.DataFrame],
    current_data_date,
) -> tuple[dict, pd.DataFrame]:
    """Paired independent HELIX Line-Up/MOH BL vs U01 S-curves and KPI data.

    Three series: BL planned finish, U01 remaining forecast/actual finish,
    and actual recorded finishes through U01's data date. All 4,153 matched
    HELIX Activity IDs. No Suffolk task contributes to any quantity.
    """
    ba = baseline["_audit"].copy()
    ua = update["_audit"].copy()
    if ba["Activity ID"].duplicated().any() or ua["Activity ID"].duplicated().any():
        raise ValueError("Duplicated HELIX Activity ID in BL/U01")
    b_ids = set(ba["Activity ID"])
    u_ids = set(ua["Activity ID"])
    if b_ids != u_ids or len(b_ids) != 4153:
        raise ValueError("HELIX BL/U01 Activity IDs are not the same 4153")
    if not ba["QTS - Subcontractor"].eq("HELIX").all() or not ua[
        "QTS - Subcontractor"
    ].eq("HELIX").all():
        raise ValueError("Unassigned or third-party Line-Up included")
    tasks = to_task_frame(update_tables["TASK"])
    tasks = tasks[tasks["task_code"].astype(str).isin(u_ids)].copy()
    if len(tasks) != len(u_ids) or tasks["task_code"].duplicated().any():
        raise ValueError("U01 source TASK records cannot reconcile to HELIX Line-Up IDs")

    joined = ua[["Activity ID", "Status"]].merge(
        tasks[["task_code", "act_end_date", "reend_date",
               "target_end_date", "early_end_date"]],
        left_on="Activity ID", right_on="task_code", how="left", validate="one_to_one"
    )
    actual = pd.to_datetime(joined["act_end_date"], errors="coerce").dt.normalize()
    remaining = pd.to_datetime(joined["reend_date"], errors="coerce").dt.normalize()
    target = pd.to_datetime(joined["target_end_date"], errors="coerce").dt.normalize()
    early = pd.to_datetime(joined["early_end_date"], errors="coerce").dt.normalize()
    current_finish = actual.where(joined["Status"].eq("Completed"))
    current_finish = current_finish.where(current_finish.notna(), remaining)
    current_finish = current_finish.where(current_finish.notna(), target)
    current_finish = current_finish.where(current_finish.notna(), early)

    if current_finish.isna().any():
        raise ValueError("U01 Line-Up Current Finish dates are missing")
    if (joined["Status"].eq("Completed") & actual.isna()).any():
        raise ValueError("U01 completed Line-Up activities without P6 Actual Finish")

    date = pd.to_datetime(current_data_date, errors="coerce")
    if pd.isna(date):
        raise ValueError("No valid HELIX U01 Data Date")
    date = pd.Timestamp(date).normalize()
    recorded = actual.where(joined["Status"].eq("Completed") & actual.le(date))
    baseline_finish = pd.to_datetime(ba["Baseline Finish"], errors="coerce").dt.normalize()
    if baseline_finish.isna().any():
        raise ValueError("HELIX baseline schedule finish dates missing")
    complete = int(joined["Status"].eq("Completed").sum())
    in_progress = int(joined["Status"].eq("In Progress").sum())
    not_started = int(joined["Status"].eq("Not Started").sum())
    if complete+in_progress+not_started != len(u_ids):
        raise ValueError("HELIX status codes do not reconcile")
    if int(recorded.notna().sum()) != complete:
        raise ValueError("Recorded actual finishes do not reconcile to Completed")

    from_date = min(baseline_finish.min(), current_finish.min(), date)
    until = max(baseline_finish.max(), current_finish.max(), date)
    time_index = pd.DatetimeIndex(pd.date_range(
        from_date.replace(day=1), until + pd.offsets.MonthEnd(0),
        freq="ME"
    ))
    time_index = pd.DatetimeIndex(sorted(set(
        list(time_index) + [date, baseline_finish.max(), current_finish.max()]
    )))
    def cumulative(series):
        return [int(series.le(x).sum()) for x in time_index]
    graph = pd.DataFrame({
        "Date":time_index,
        "Baseline Planned Activities":cumulative(baseline_finish),
        "Current Forecast Activities":cumulative(current_finish),
        "Actual Completed Activities":cumulative(recorded),
    })
    graph.loc[graph["Date"] > date, "Actual Completed Activities"] = np.nan
    if int(graph["Baseline Planned Activities"].iloc[-1]) != 4153 or int(
        graph["Current Forecast Activities"].iloc[-1]
    ) != 4153:
        raise ValueError("HELIX independent S-curve does not close at 4153")
    info = {
        "Counts":{
            "Total":4153, "Completed":complete,
            "In Progress":in_progress, "Not Started":not_started
        },
        "Baseline Finish":baseline_finish.max(),
        "Current Forecast Finish":current_finish.max(),
        "Current Data Date":date,
        "Source BL":"226021-HE.B.xer",
        "Source Current":"226021-HE.U01.xer",
    }
    return info, graph


def lineup_area_status_summary(data: Mapping[str, pd.DataFrame] | None) -> pd.DataFrame:
    """Suffolk-style activity status summary, but for independent HELIX BL.

    Exactly six Data Halls and MOH; no FOH/BOH, other subcontractors,
    Commissioning or milestones. Statuses come ONLY from each official
    baseline P6 TASK.status_code, never Suffolk Current-C.
    """
    areas = (*HALLS, "MOH")
    columns = [
        "Area", "Total Tasks", "Activity Completion %",
        "Completed", "In Progress", "Not Started",
    ]
    rows = []
    for area in areas:
        detail = wbs_lineup_hierarchy(data, area)
        if data is None:
            rows.append({
                "Area": area, **{name: None for name in columns[1:]}
            })
            continue
        count = {name: int(detail[name].sum())
                 for name in ("Total Activities", "Not Started", "In Progress", "Completed")}
        total = count["Total Activities"]
        completed = count["Completed"]
        if count["Not Started"] + count["In Progress"] + completed != total:
            raise ValueError(f"Official HELIX baseline status mismatch for {area}")
        rows.append({
            "Area": area,
            "Total Tasks": total,
            "Activity Completion %": (completed / total * 100) if total else 0.0,
            "Completed": completed,
            "In Progress": count["In Progress"],
            "Not Started": count["Not Started"],
        })

    summary = pd.DataFrame(rows, columns=columns)
    if data is not None:
        audit = data["_audit"]
        if len(audit) != int(summary["Total Tasks"].sum()):
            raise ValueError("Summary total does not reconcile to original HELIX Activity IDs")
        if not audit["Activity ID"].is_unique or not audit["QTS - Subcontractor"].eq("HELIX").all():
            raise ValueError("Incorrect subcontractor or duplicate HELIX Activity ID in summary")
        for display, audit_status in (
            ("Completed", "Completed"),
            ("In Progress", "In Progress"),
            ("Not Started", "Not Started"),
        ):
            if int(summary[display].sum()) != int(audit["Status"].eq(audit_status).sum()):
                raise ValueError(f"HELIX baseline {display} counts do not reconcile")
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
    valid_statuses = {"Not Started", "In Progress", "Completed"}
    unexpected = set(included["Status"].unique()) - valid_statuses
    if unexpected:
        raise ValueError(f"Unrecognized status codes for HELIX baseline tasks: {sorted(unexpected)}")
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
        "Status":included["Status"].astype(str),
        "QTS - Subcontractor":included["_Sub"].astype(str),
        "Original P6 WBS":included["_WBS Path"].astype(str),
        "Baseline Start":included["_Start"],
        "Baseline Finish":included["_Finish"],
    }).reset_index(drop=True)
    # Contractual dates are embedded in ORIGINAL Activity Names, not P6
    # contractual-date UDFs. Only assigned HELIX tasks in Milestones WBS.
    # The official 226021-HE.B.xer is a baseline, NOT an independent Current.
    from datetime import datetime

    all_milestones = task[
        task["_Sub"].eq("HELIX")
        & task["_WBS Path"].str.contains(" / Milestones / ", regex=False, na=False)
    ].copy()
    date_pattern = re.compile(r"\((\d{1,2}/\d{1,2}/(?:\d{4}|\d{2}))\)")
    milestone_rows = []
    no_contract_date = []
    for _, item in all_milestones.iterrows():
        fullname = str(item["task_name"])
        found = date_pattern.findall(fullname)
        parts = str(item["_WBS Path"]).split(" / Milestones / ", 1)
        category = parts[1] if len(parts) == 2 else ""
        if not found:
            no_contract_date.append(str(item["task_code"]))
            continue
        if len(found) != 1:
            raise ValueError(f"Ambiguous embedded contract dates: {item['task_code']}")
        raw_date = found[0]
        fmt = "%m/%d/%Y" if len(raw_date.rsplit("/", 1)[-1]) == 4 else "%m/%d/%y"
        contract = pd.Timestamp(datetime.strptime(raw_date, fmt).date())
        # P6 Finish: remain end is the scheduled finish for not-started /
        # in-progress milestones; use Actual Finish when completed.
        if item["Status"] == "Completed":
            finish = pd.to_datetime(item.get("act_end_date"), errors="coerce")
        else:
            finish = pd.to_datetime(item.get("reend_date"), errors="coerce")
            if pd.isna(finish):
                finish = pd.to_datetime(item.get("target_end_date"), errors="coerce")
        if pd.isna(finish):
            raise ValueError(f"Missing P6 Finish for contractual HELIX milestone {item['task_code']}")
        finish = finish.normalize()
        delay = us_federal_workday_delay(contract, finish)
        group = "QC 2.2" if category.strip() == "QC 2.2" else "IST / L4 Cx" if category.strip() == "L4 Cx" else None
        if group is None:
            raise ValueError(f"Unrecognized dated HELIX contractual milestone WBS: {category}")
        activity_id = str(item["task_code"])
        area_match = re.match(r"^(?:M|IST)\.(\d{4})$", activity_id)
        if area_match is None:
            raise ValueError(f"Unrecognized HELIX contract milestone ID: {activity_id}")
        area = "DH" + area_match.group(1)
        if area not in HALLS:
            raise ValueError(f"HELIX milestone area outside six Data Halls: {area}")
        if not fullname.lstrip().upper().startswith(area):
            raise ValueError(f"Milestone Activity Name/ID area mismatch: {activity_id}")
        milestone_rows.append({
            "Area": area,
            "Milestone": group,
            "Activity ID": activity_id,
            "Activity Name": fullname,
            "Contractual Date": contract,
            "Baseline Finish": finish,
            "Delay (US working days)": delay,
            "Status": str(item["Status"]),
            "Subcontractor": str(item["_Sub"]),
            "Original P6 WBS": str(item["_WBS Path"]),
        })
    milestones = pd.DataFrame(milestone_rows)
    if not milestones.empty:
        milestones = milestones.sort_values(
            ["Milestone", "Area"], key=lambda col: col.map(
                {"QC 2.2": 0, "IST / L4 Cx": 1}
            ) if col.name == "Milestone" else col
        ).reset_index(drop=True)
        if milestones["Activity ID"].duplicated().any():
            raise ValueError("Repeated HELIX contract milestone Activity IDs")
        if not milestones["Subcontractor"].eq("HELIX").all():
            raise ValueError("Non-HELIX milestone in contractual variance report")
        if milestones["Contractual Date"].isna().any() or milestones["Baseline Finish"].isna().any():
            raise ValueError("Incomplete HELIX milestone date comparison")
        computed_workdays = milestones.apply(
            lambda row: us_federal_workday_delay(
                row["Contractual Date"], row["Baseline Finish"]
            ), axis=1
        )
        if not milestones["Delay (US working days)"].eq(computed_workdays).all():
            raise ValueError("US federal working-day contractual delay audit failed")
    if len(task) == 4689:
        if len(all_milestones) != 20 or len(milestones) != 10 or len(no_contract_date) != 10:
            raise ValueError(
                f"Unexpected official HELIX milestone audit: "
                f"{len(all_milestones)} assigned; "
                f"{len(milestones)} with contract date; {len(no_contract_date)} without"
            )
    out["_contract_milestones"] = milestones
    out["_contract_milestone_audit"] = {
        "helix_milestone_total": int(len(all_milestones)),
        "contract_date_extracted": int(len(milestones)),
        "no_contract_date_in_name": int(len(no_contract_date)),
        "no_contract_date_ids": sorted(no_contract_date),
        "schedule_source": "226021-HE.B independent baseline",
    }

    # Keep the Line-Up and MOH population separate from milestone audit.
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
