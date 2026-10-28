from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import re
import numpy as np
import pandas as pd

from config import AREA_ORDER, CONTROL_GATE_KEYWORDS, HOURS_PER_DAY
from src.xer import parse_xer, to_task_frame
from src.construction_audit import construction_wbs_ids, scoped_helix_construction, build_activity_audit
from src.helix_baseline import summarize_approved_baseline

WANTED = ["PROJECT", "TASK", "PROJWBS", "ACTVTYPE", "ACTVCODE", "TASKACTV"]


def _norm(x) -> str:
    return " ".join(str(x or "").strip().upper().replace("_", " ").split())


def _project_row(tables: dict[str, pd.DataFrame], path: Path) -> pd.Series:
    p = tables.get("PROJECT", pd.DataFrame())
    if p.empty:
        raise ValueError(f"No PROJECT table in {path.name}")
    stem = path.stem.upper()
    if "proj_short_name" in p.columns:
        exact = p[p["proj_short_name"].fillna("").astype(str).str.upper().eq(stem)]
        if not exact.empty:
            return exact.iloc[0]
    tasks = tables.get("TASK", pd.DataFrame())
    counts = tasks.get("proj_id", pd.Series(dtype=str)).astype(str).value_counts()
    candidates = p.copy()
    if "proj_short_name" in candidates.columns:
        bad = candidates["proj_short_name"].fillna("").astype(str).str.upper().str.contains(r"MIL|TFO", regex=True)
        candidates = candidates[~bad]
    if candidates.empty:
        candidates = p
    candidates = candidates.copy()
    candidates["_n"] = candidates["proj_id"].astype(str).map(counts).fillna(0)
    return candidates.sort_values("_n", ascending=False).iloc[0]


def _find_files(data_dir: Path) -> tuple[Path, Path]:
    """Strict official Suffolk BL + UP08 pair. No Current-C fallback."""
    source = Path(data_dir)
    files = sorted(source.rglob("226021.005.MO-BL.xer"))
    updates = sorted(source.rglob("226021.025.MO-UP-09.xer"))
    if len(files) != 1 or len(updates) != 1:
        raise FileNotFoundError(
            "Expected one 226021.005.MO-BL.xer and one "
            "226021.025.MO-UP-09.xer in DC7 data; no older-current fallback"
        )
    if files[0].parent != updates[0].parent:
        raise ValueError("Suffolk BL and official UP09 must share the same source directory")
    return files[0], updates[0]


def _type_id(tables: dict[str, pd.DataFrame], type_name: str) -> Optional[str]:
    df = tables.get("ACTVTYPE", pd.DataFrame())
    if df.empty or "actv_code_type" not in df.columns:
        return None
    m = df[df["actv_code_type"].fillna("").astype(str).str.strip().str.casefold().eq(type_name.casefold())]
    return str(m.iloc[0]["actv_code_type_id"]) if not m.empty else None


def _code_id(tables: dict[str, pd.DataFrame], type_id: str, short_name: str) -> Optional[str]:
    df = tables.get("ACTVCODE", pd.DataFrame())
    if df.empty:
        return None
    m = df[df["actv_code_type_id"].astype(str).eq(str(type_id))]
    s = m.get("short_name", pd.Series("", index=m.index)).fillna("").astype(str).str.strip()
    n = m.get("actv_code_name", pd.Series("", index=m.index)).fillna("").astype(str).str.strip()
    m = m[s.str.casefold().eq(short_name.casefold()) | n.str.casefold().eq(short_name.casefold())]
    return str(m.iloc[0]["actv_code_id"]) if not m.empty else None


def _assignment_map(tables: dict[str, pd.DataFrame], proj_id: str, type_name: str, value_col: str = "short_name") -> dict[str, str]:
    tid = _type_id(tables, type_name)
    if tid is None:
        return {}
    ta = tables.get("TASKACTV", pd.DataFrame())
    ac = tables.get("ACTVCODE", pd.DataFrame())
    if ta.empty or ac.empty:
        return {}
    ta = ta[(ta["proj_id"].astype(str).eq(str(proj_id))) & (ta["actv_code_type_id"].astype(str).eq(str(tid)))].copy()
    cols = ["actv_code_id", value_col]
    cols = [c for c in cols if c in ac.columns]
    if value_col not in cols:
        value_col = "actv_code_name"
        cols = ["actv_code_id", value_col]
    m = ta.merge(ac[cols].drop_duplicates("actv_code_id"), on="actv_code_id", how="left")
    return dict(zip(m["task_id"].astype(str), m[value_col].fillna("").astype(str)))


def _helix_task_ids(tables: dict[str, pd.DataFrame], proj_id: str) -> set[str]:
    tid = _type_id(tables, "QTS - Subcontractor")
    if tid is None:
        raise ValueError("Activity Code type 'QTS - Subcontractor' was not found in the update XER.")
    cid = _code_id(tables, tid, "HELIX")
    if cid is None:
        raise ValueError("Activity Code 'HELIX' was not found under QTS - Subcontractor.")
    ta = tables.get("TASKACTV", pd.DataFrame())
    m = ta[(ta["proj_id"].astype(str).eq(str(proj_id))) &
           (ta["actv_code_type_id"].astype(str).eq(str(tid))) &
           (ta["actv_code_id"].astype(str).eq(str(cid)))]
    return set(m["task_id"].astype(str))


def _moh_package(task_name: str) -> str:
    """Functional package for MOH activities from the dedicated HELIX schedule.

    HE.B-4 does not contain QTS-DASH, so MOH is grouped from the explicit
    equipment identifiers embedded in the activity names.
    """
    name = str(task_name or "").upper()
    if re.search(r"\bSWD\b|SWD-", name):
        return "Switchgear / Main Distribution"
    if re.search(r"\bXFMR\b|XFMR-", name):
        return "Transformers"
    if re.search(r"\bPNL\b|PNL-", name):
        return "Panels"
    if re.search(r"\bCIP\b|CIP-", name):
        return "CIP / Controls"
    if re.search(r"\bSTS\b|STS-|\bMTS\b|MTS-|\bATS\b|ATS-", name):
        return "Transfer Equipment"
    if re.search(r"\bUPS\b|UPS-|\bELI\b|ELI-|\bBATTERY\b", name):
        return "UPS / ELI / Battery Systems"
    if re.search(r"\bMPZ\b|MPZ-|\bMMR\b", name):
        return "MPZ / MMR"
    return "Other HELIX Electrical Scope"


def _clean_subarea(name: str) -> str:
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return "Other HELIX Electrical Scope"
    x = str(name).strip()
    if not x or x.lower() == "nan":
        return "Other HELIX Electrical Scope"
    fixes = {
        "Commissining & Start-Up": "Commissioning & Start-Up",
        "Gallery Rooms": "Galleries",
        "Corridors": "Corridor",
    }
    return fixes.get(x, x or "Other HELIX Electrical Scope")


def _helix_display_subarea(row: pd.Series) -> str:
    """Consolidate HELIX Data Hall categories for display only.

    The source QTS-DASH assignment in P6 is never overwritten. In particular,
    missing QTS-DASH activities are reclassified only if their descriptions
    unambiguously identify electrical work under slab or RTU roof systems.
    Unknown / future unclassified work remains visible in the residual group
    rather than being silently assigned to the wrong scope.
    """
    subarea = _clean_subarea(row.get("Subarea", ""))
    if not str(row.get("Area", "")).upper().startswith("DH"):
        return subarea

    groups = {
        "Other Rooms": "Technical & Auxiliary Rooms",
        "Electrical Rooms": "Technical & Auxiliary Rooms",
        "Electrical Yard": "Electrical Infrastructure & Yard",
        "Mechanical Yard": "Mechanical Systems & Yard",
    }
    if subarea in groups:
        return groups[subarea]
    if subarea != "Other HELIX Electrical Scope":
        return subarea

    name = str(row.get("task_name", "")).upper()
    if re.search(r"\b(?:UNDER[\s-]*SLAB|UNDERSLAB)\b", name) and "ELECTRICAL" in name:
        return "Electrical Infrastructure & Yard"
    if re.search(r"\bROOF\s*-\s*RTUS?\b", name):
        return "Mechanical Systems & Yard"
    return subarea


def _date_min(df: pd.DataFrame, cols: list[str]) -> pd.Timestamp:
    vals = []
    for c in cols:
        if c in df.columns:
            s = pd.to_datetime(df[c], errors="coerce").dropna()
            if not s.empty:
                vals.append(s.min())
    return min(vals) if vals else pd.NaT


def _date_max(df: pd.DataFrame, cols: list[str]) -> pd.Timestamp:
    vals = []
    for c in cols:
        if c in df.columns:
            s = pd.to_datetime(df[c], errors="coerce").dropna()
            if not s.empty:
                vals.append(s.max())
    return max(vals) if vals else pd.NaT


def _duration_pct(g: pd.DataFrame) -> float:
    if g.empty:
        return 0.0
    od = pd.to_numeric(g.get("target_drtn_hr_cnt", pd.Series(0, index=g.index)), errors="coerce").fillna(0).clip(lower=0)
    rd = pd.to_numeric(g.get("remain_drtn_hr_cnt", pd.Series(0, index=g.index)), errors="coerce").fillna(0).clip(lower=0)
    valid = od.gt(0)
    if not valid.any() or od[valid].sum() <= 0:
        return 0.0
    earned = (od - rd).clip(lower=0)
    earned = np.minimum(earned, od)
    return float(100.0 * earned[valid].sum() / od[valid].sum())


def _activity_completion_pct(g: pd.DataFrame) -> float:
    if g.empty:
        return 0.0
    status = g.get("Status", pd.Series("", index=g.index)).fillna("").astype(str)
    return float(100.0 * status.eq("Completed").sum() / len(g))


def _status_pct(g: pd.DataFrame, label: str) -> float:
    if g.empty:
        return 0.0
    status = g.get("Status", pd.Series("", index=g.index)).fillna("").astype(str)
    return float(100.0 * status.eq(label).sum() / len(g))


def _project_date(row: pd.Series, *cols: str) -> pd.Timestamp:
    for c in cols:
        if c in row.index:
            x = pd.to_datetime(row.get(c), errors="coerce")
            if pd.notna(x):
                return pd.Timestamp(x)
    return pd.NaT


@dataclass
class DC7Model:
    baseline_path: Path
    update_path: Path
    baseline_project: pd.Series
    update_project: pd.Series
    baseline_tasks: pd.DataFrame
    current_tasks: pd.DataFrame
    baseline_tables: dict[str, pd.DataFrame]
    update_tables: dict[str, pd.DataFrame]
    auxiliary_path: Optional[Path] = None
    auxiliary_tasks: Optional[pd.DataFrame] = None
    auxiliary_project: Optional[pd.Series] = None
    auxiliary_tables: Optional[dict[str, pd.DataFrame]] = None
    auxiliary_update_path: Optional[Path] = None
    auxiliary_update_project: Optional[pd.Series] = None
    auxiliary_update_tables: Optional[dict[str, pd.DataFrame]] = None
    historical_helix_tables: Optional[dict[str, pd.DataFrame]] = None
    historical_helix_project: Optional[pd.Series] = None
    audit_reports: Optional[dict[str, pd.DataFrame]] = None

    @property
    def data_date(self):
        return _project_date(self.update_project, "data_date", "last_recalc_date", "last_schedule_date")

    @property
    def baseline_data_date(self):
        return _project_date(self.baseline_project, "data_date", "last_recalc_date", "last_schedule_date")

    @property
    def baseline_finish(self):
        return _project_date(self.baseline_project, "scd_end_date", "plan_end_date")

    @property
    def current_finish(self):
        return _project_date(self.update_project, "scd_end_date", "plan_end_date")

    @property
    def finish_variance_days(self):
        # P6-style dashboard convention used throughout DC7:
        # Variance = Baseline date - Current date.
        # Positive = ahead / favorable; negative = late / unfavorable.
        if pd.notna(self.baseline_finish) and pd.notna(self.current_finish):
            return int((self.baseline_finish.normalize() - self.current_finish.normalize()).days)
        return None

    @property
    def duration_progress(self):
        return _duration_pct(self.current_tasks)

    @property
    def activity_completion_ratio(self):
        return _activity_completion_pct(self.current_tasks)

    def status_counts(self) -> dict[str, int]:
        vc = self.current_tasks["Status"].value_counts()
        return {
            "Total": int(len(self.current_tasks)),
            "Completed": int(vc.get("Completed", 0)),
            "In Progress": int(vc.get("In Progress", 0)),
            "Not Started": int(vc.get("Not Started", 0)),
        }

    def status_percentages(self) -> dict[str, float]:
        c = self.status_counts()
        total = c["Total"] or 1
        return {
            "Completed %": 100.0 * c["Completed"] / total,
            "In Progress %": 100.0 * c["In Progress"] / total,
            "Not Started %": 100.0 * c["Not Started"] / total,
        }

    def _main_areas(self) -> list[str]:
        have = set(self.current_tasks["Area"].dropna().astype(str))
        ordered = [x for x in AREA_ORDER if x in have]
        return ordered + sorted(have - set(ordered))

    def areas(self) -> list[str]:
        have = set(self._main_areas())
        if self.auxiliary_tasks is not None and not self.auxiliary_tasks.empty:
            if self.auxiliary_tasks["Area"].astype(str).eq("MOH").any():
                have.add("MOH")
        ordered = [x for x in AREA_ORDER if x in have]
        if "MOH" in have and "MOH" not in ordered:
            ordered.append("MOH")
        return ordered + sorted(have - set(ordered))

    def area_stats(self) -> pd.DataFrame:
        """Summary of the audited Suffolk Construction universe only.

        Auxiliary MOH and dedicated HELIX Line-Ups are displayed separately;
        neither can be counted in Suffolk project scope KPIs or this matrix.
        """
        rows = []
        for area in self._main_areas():
            g = self.current_tasks[self.current_tasks["Area"].eq(area)].copy()
            vc = g["Status"].value_counts()
            rows.append({
                "Area": area,
                "Total Tasks": len(g),
                "Activity Completion %": _activity_completion_pct(g),
                "Completed": int(vc.get("Completed", 0)),
                "In Progress": int(vc.get("In Progress", 0)),
                "Not Started": int(vc.get("Not Started", 0)),
                "Completed %": _status_pct(g, "Completed"),
                "In Progress %": _status_pct(g, "In Progress"),
                "Not Started %": _status_pct(g, "Not Started"),
            })
        return pd.DataFrame(rows)

    def area_windows(self) -> pd.DataFrame:
        """HELIX-only Suffolk Construction area windows from independent BL/UP09 XER.

        Use all qualifying activity dates for each area, not a chosen current
        activity as the start anchor. Baseline matches retain the original P6
        baseline dates; current completed tasks use actual start/finish and
        incomplete tasks use the remaining forecast.
        """
        def wbs_area_ids(tables: dict[str, pd.DataFrame], area: str) -> set[str]:
            wbs = tables["PROJWBS"]
            names = dict(zip(wbs["wbs_id"].astype(str), wbs["wbs_name"].astype(str)))
            parents = dict(zip(wbs["wbs_id"].astype(str), wbs["parent_wbs_id"].astype(str)))
            target = ("Front of House (FOH)" if area == "FOH" else
                      "Back of House (BOH)" if area == "BOH" else
                      "Data Hall " + area[2:])
            expected = (["Construction", "Interior Build-Outs", "House Systems", target]
                        if area in ("FOH", "BOH") else
                        ["Construction", "Interior Build-Outs", target])
            result = set()
            for wid in names:
                lineage, node, visited = [], wid, set()
                while node in names and node not in visited:
                    visited.add(node)
                    lineage.append(names[node].strip())
                    node = parents.get(node, "")
                lineage.reverse()
                if len(lineage) >= len(expected) + 1 and lineage[1:1 + len(expected)] == expected:
                    result.add(wid)
            if not result:
                raise ValueError(f"No P6 WBS for HELIX Suffolk area {area}: {expected}")
            return result

        rows = []
        for area in self._main_areas():
            # Source selection is independent in each XER, and P6 WBS (not
            # QTS-AREA alone) controls the eight summary windows.
            b_ids = wbs_area_ids(self.baseline_tables, area)
            c_ids = wbs_area_ids(self.update_tables, area)
            b_all = self.baseline_tasks[
                self.baseline_tasks["Area"].eq(area) &
                self.baseline_tasks["wbs_id"].astype(str).isin(b_ids)
            ].copy()
            c_all = self.current_tasks[
                self.current_tasks["Area"].eq(area) &
                self.current_tasks["wbs_id"].astype(str).isin(c_ids)
            ].copy()
            if b_all.empty or c_all.empty:
                raise ValueError(f"Missing Suffolk HELIX baseline/current area: {area}")

            # Baseline: one scheduled start/finish per matched HELIX task.
            baseline_start = pd.to_datetime(b_all["target_start_date"], errors="coerce")
            baseline_start = baseline_start.fillna(
                pd.to_datetime(b_all["early_start_date"], errors="coerce")
            )
            baseline_finish = pd.to_datetime(b_all["target_end_date"], errors="coerce")
            baseline_finish = baseline_finish.fillna(
                pd.to_datetime(b_all["early_end_date"], errors="coerce")
            ).fillna(pd.to_datetime(b_all["reend_date"], errors="coerce"))

            # Update: actual dates when available; otherwise remaining forecast.
            current_start = pd.to_datetime(c_all["act_start_date"], errors="coerce")
            current_start = current_start.fillna(
                pd.to_datetime(c_all["early_start_date"], errors="coerce")
            ).fillna(pd.to_datetime(c_all["restart_date"], errors="coerce")
            ).fillna(pd.to_datetime(c_all["target_start_date"], errors="coerce"))

            completed = c_all["status_code"].fillna("").astype(str).str.upper().eq("TK_COMPLETE")
            actual_finish = pd.to_datetime(c_all["act_end_date"], errors="coerce")
            forecast_finish = pd.to_datetime(c_all["reend_date"], errors="coerce").fillna(
                pd.to_datetime(c_all["early_end_date"], errors="coerce")
            )
            current_finish = actual_finish.where(completed, forecast_finish)
            for label, dates in (
                ("Baseline Start", baseline_start), ("Baseline Finish", baseline_finish),
                ("Current Start", current_start), ("Current Finish", current_finish),
            ):
                if dates.isna().any():
                    missing = b_all if label.startswith("Baseline") else c_all
                    examples = missing.loc[dates.isna(), "task_code"].head(5).tolist()
                    raise ValueError(f"Missing {label} in {area}: {examples}")

            bs, bf = baseline_start.min(), baseline_finish.max()
            cs, cf = current_start.min(), current_finish.max()
            finish_anchor_id = str(c_all.loc[current_finish.idxmax(), "task_code"])
            finish_anchor_name = str(c_all.loc[current_finish.idxmax(), "task_name"])
            finish_anchor_field = ("act_end_date" if bool(completed.loc[current_finish.idxmax()])
                else "reend_date" if pd.notna(pd.to_datetime(c_all.loc[current_finish.idxmax(), "reend_date"], errors="coerce"))
                else "early_end_date")
            finish_reference = "Latest HELIX Construction Finish"
            # The L3 Start gate is a Suffolk project milestone, not necessarily
            # subcontractor-coded HELIX. Use it for the Data Hall control boundary
            # without adding the milestone to HELIX activity counts.
            if area.startswith("DH"):
                code = {"DH1100": "DH1100.L3CX.000",
                        "DH1200": "DH1200.L3CX.39",
                        "DH1300": "DH1300.L3CX.59",
                        "DH1400": "DH1400.L3CX.79",
                        "DH1500": "DH1500.L3CX.99",
                        "DH1600": "DH1600.L3CX.19"}[area]
                def gate_row(tables):
                    tasks = tables["TASK"]
                    projects = tables["PROJECT"]
                    # Search by Activity ID; reject nonunique matches.
                    matches = tasks[tasks["task_code"].astype(str).eq(code)]
                    if len(matches) != 1:
                        raise ValueError(f"Expected exactly one Suffolk L3 Start milestone: {code}; got {len(matches)}")
                    return matches.iloc[0]
                current_gate = gate_row(self.update_tables)
                if not str(current_gate["task_name"]).strip().lower().endswith("l3 start"):
                    raise ValueError(f"Unexpected L3 Start activity identity: {code}")
                gate_actual = pd.to_datetime(current_gate.get("act_end_date"), errors="coerce")
                gate_finish = pd.to_datetime(current_gate.get("reend_date"), errors="coerce")
                if pd.isna(gate_finish):
                    gate_finish = pd.to_datetime(current_gate.get("early_end_date"), errors="coerce")
                if str(current_gate["status_code"]).upper() == "TK_COMPLETE" and pd.notna(gate_actual):
                    gate_finish = gate_actual
                if pd.isna(gate_finish):
                    raise ValueError(f"Missing current L3 Start date for {code}")
                cf = gate_finish
                finish_anchor_id = code
                finish_anchor_name = str(current_gate["task_name"])
                finish_anchor_field = "act_end_date" if str(current_gate["status_code"]).upper() == "TK_COMPLETE" else "reend_date / early_end_date"
                finish_reference = "L3 Start Control Milestone"
                # Do not conflate a baseline area maximum with a baseline L3 gate.
                baseline_gate = gate_row(self.baseline_tables)
                gate_bl = pd.to_datetime(baseline_gate.get("target_end_date"), errors="coerce")
                if pd.isna(gate_bl):
                    gate_bl = pd.to_datetime(baseline_gate.get("early_end_date"), errors="coerce")
                if pd.isna(gate_bl):
                    raise ValueError(f"Missing baseline L3 Start date for {code}")
                bf = gate_bl
            if bs > bf or cs > cf:
                raise ValueError(f"Invalid HELIX area window in {area}")

            rows.append({
                "Area": area,
                "Baseline Start": bs,
                "Baseline Finish": bf,
                "Current Start": cs,
                "Current Forecast Finish": cf,
                "Start Date Shift (d)": (bs.normalize() - cs.normalize()).days,
                "Finish Date Shift (d)": (bf.normalize() - cf.normalize()).days,
                "Duration Change (d)": ((bf - bs) - (cf - cs)).days,
                "Activity Completion %": _activity_completion_pct(c_all),
                "Start Anchor ID": str(b_all.loc[baseline_start.idxmin(), "task_code"]),
                "Start Anchor": str(b_all.loc[baseline_start.idxmin(), "task_name"]),
                # The source activity driving the area maximum is auditable.
                "Current Finish Anchor ID": finish_anchor_id,
                "Current Finish Anchor Name": finish_anchor_name,
                "Current Finish Anchor Field": finish_anchor_field,
                "Finish Reference": finish_reference,
            })
        return pd.DataFrame(rows)


    def wbs_area_activities(self, area: str, include_exceptions: bool = False) -> pd.DataFrame:
        """Return FOH/BOH HELIX Construction grouped by the genuine P6 WBS.

        FDN.1296 / FDN.1300 have QTS-AREA FOH/BOH but belong to
        Construction / Shell / Foundations, outside House Systems.
        By default these WBS exceptions are excluded ONLY from the FOH/BOH
        detail and chart. include_exceptions=True preserves both original
        records for the formal activity audit. Project-level HELIX counts
        and the original XERs are never changed by this presentation rule.
        """
        if area not in ("FOH", "BOH"):
            raise ValueError(f"P6 WBS detail is supported only for FOH/BOH, got {area!r}")
        source = self.current_tasks[self.current_tasks["Area"].astype(str).eq(area)].copy()
        if source.empty:
            return source.assign(**{"WBS Group": pd.Series(dtype=str), "WBS Path": pd.Series(dtype=str)})
        project_id = str(self.update_project["proj_id"])
        wbs = self.update_tables["PROJWBS"]
        wbs = wbs[wbs["proj_id"].astype(str).eq(project_id)].copy()
        names = dict(zip(wbs["wbs_id"].astype(str), wbs["wbs_name"].astype(str)))
        parents = dict(zip(wbs["wbs_id"].astype(str), wbs["parent_wbs_id"].astype(str)))
        marker = "Front of House (FOH)" if area == "FOH" else "Back of House (BOH)"

        def resolve(wbs_id: str) -> tuple[str, str]:
            node = str(wbs_id)
            lineage = []
            visited = set()
            while node in names:
                if node in visited:
                    raise ValueError(f"P6 WBS circular ancestry at {node}")
                visited.add(node)
                lineage.append(names[node])
                node = parents.get(node, "")
            lineage.reverse()
            if "Construction" not in lineage:
                raise ValueError(f"Activity in {area} outside Construction WBS: {wbs_id}")
            if marker in lineage:
                at = lineage.index(marker)
                if at + 1 >= len(lineage):
                    raise ValueError(f"Activity has no grouping child under {marker}: {wbs_id}")
                group = lineage[at + 1]
            elif "Foundations" in lineage and "Shell" in lineage:
                group = "Foundations"  # exact PROJWBS name, not a dashboard alias
            else:
                raise ValueError(
                    f"{area} activity is coded outside its P6 WBS and not Foundations: "
                    + " / ".join(lineage)
                )
            return group, " / ".join(lineage[1:])

        resolved = [resolve(wbs_id) for wbs_id in source["wbs_id"].astype(str)]
        source["WBS Group"] = [entry[0] for entry in resolved]
        source["WBS Path"] = [entry[1] for entry in resolved]
        if source["task_code"].astype(str).duplicated().any():
            raise ValueError(f"Duplicate HELIX Construction Activity IDs in {area}")
        # Only these two evidenced Shell/Foundations exceptions may be
        # left out of the FOH/BOH WBS detail; reject any new, unexpected one.
        exceptions = source[source["WBS Group"].eq("Foundations")]
        expected = {"FOH": {"FDN.1296"}, "BOH": {"FDN.1300"}}[area]
        found = set(exceptions["task_code"].astype(str))
        if found != expected:
            raise ValueError(f"{area} WBS exceptions changed: {sorted(found)}; expected {sorted(expected)}")
        if not include_exceptions:
            source = source[source["WBS Group"].ne("Foundations")].copy()
        return source

    def wbs_area_stats(self, area: str) -> pd.DataFrame:
        """Display EVERY direct child of the original FOH/BOH WBS in P6 order.

        Native PROJWBS is authoritative for names and ordering, including
        branches with zero HELIX-assigned Construction tasks. The numeric
        results still come solely from audited, active HELIX Construction
        activities, excluding the two separately audited Shell/Foundations
        coding exceptions. No dummy P6 tasks are created for empty branches.
        """
        detail = self.wbs_area_activities(area)
        wbs = self.update_tables["PROJWBS"].copy()
        wbs = wbs[wbs["proj_id"].astype(str).eq(str(self.update_project["proj_id"]))]
        marker = "Front of House (FOH)" if area == "FOH" else "Back of House (BOH)"
        parents = wbs[wbs["wbs_name"].astype(str).eq(marker)]
        if len(parents) != 1:
            raise ValueError(f"Expected one P6 WBS named {marker}, found {len(parents)}")
        children = wbs[wbs["parent_wbs_id"].astype(str).eq(str(parents.iloc[0]["wbs_id"]))].copy()
        if children.empty:
            raise ValueError(f"No P6 WBS children found under {marker}")
        children["_p6_sequence"] = pd.to_numeric(children["seq_num"], errors="raise")
        children = children.sort_values(["_p6_sequence", "wbs_id"], kind="stable")
        native_labels = children["wbs_name"].astype(str).tolist()
        if len(set(native_labels)) != len(native_labels):
            raise ValueError(f"Duplicate native P6 WBS names beneath {marker}")
        unexpected = set(detail["WBS Group"].astype(str)) - set(native_labels)
        if unexpected:
            raise ValueError(f"HELIX activities not mapped to native {area} P6 WBS children: {sorted(unexpected)}")

        rows = []
        for native_name in native_labels:
            activities = detail[detail["WBS Group"].eq(native_name)]
            counts = activities["Status"].value_counts()
            rows.append({
                "Area": native_name,
                "Tasks": int(len(activities)),
                "Activity Completion %": _activity_completion_pct(activities),
                "Not Started": int(counts.get("Not Started", 0)),
                "In Progress": int(counts.get("In Progress", 0)),
                "Completed": int(counts.get("Completed", 0)),
            })
        result = pd.DataFrame(rows)
        if int(result["Tasks"].sum()) != len(detail):
            raise ValueError(f"FOH/BOH P6 WBS reconciliation failed for {area}")
        return result

    def data_hall_wbs_activities(self, area: str, include_exceptions: bool = False) -> pd.DataFrame:
        """Native WBS-based seven-group SUFFOLK Data Hall detail for HELIX only.

        Read the original P6 WBS ancestry; no QTS-DASH renaming or activity
        description matching. Other HELIX Construction tasks are retained in
        the source model and its independent audit, never silently reassigned.
        """
        if area not in ("DH1100", "DH1200", "DH1300", "DH1400", "DH1500", "DH1600"):
            raise ValueError(f"Unsupported Data Hall WBS detail: {area}")
        source = self.current_tasks[self.current_tasks["Area"].astype(str).eq(area)].copy()
        if source.empty:
            raise ValueError(f"No active HELIX Construction tasks in {area}")
        wbs = self.update_tables["PROJWBS"]
        wbs = wbs[wbs["proj_id"].astype(str).eq(str(self.update_project["proj_id"]))]
        names = dict(zip(wbs["wbs_id"].astype(str), wbs["wbs_name"].astype(str)))
        parents = dict(zip(wbs["wbs_id"].astype(str), wbs["parent_wbs_id"].astype(str)))
        expected_hall = f"Data Hall {area[2:]}"
        groups = (
            "Electrical Yard", "Mechanical Yard", "Electrical Rooms",
            "Data Hall", "Galleries", "Corridors",
            "Energization, Start-up & Commissioning",
        )

        def native_path(wbs_id: str) -> list[str]:
            ancestry, node, visited = [], str(wbs_id), set()
            while node in names:
                if node in visited:
                    raise ValueError(f"Cycle in PROJWBS at {node}")
                visited.add(node)
                ancestry.append(names[node])
                node = parents.get(node, "")
            ancestry.reverse()
            if "Construction" not in ancestry:
                raise ValueError(f"Out-of-Construction HELIX task WBS {wbs_id}")
            return ancestry

        def identify(wbs_id: str) -> tuple[str, str]:
            path = native_path(wbs_id)
            full_path = " / ".join(path[1:])
            if expected_hall not in path or "Interior Build-Outs" not in path:
                return "WBS EXCEPTION", full_path
            offset = path.index(expected_hall)
            relative = path[offset + 1:]
            if len(relative) < 2:
                return "WBS EXCEPTION", full_path
            level, child = relative[:2]
            if level == "Exterior Build Out" and child in ("Electrical Yard", "Mechanical Yard"):
                return child, full_path
            if level == "Interior Build Out":
                if re.match(r"^Electr(?:i)?cal Room\s*#", child, re.I):
                    return "Electrical Rooms", full_path
                if child == expected_hall:
                    return "Data Hall", full_path
                if child in ("PDU Gallery", "CRAH/CDU Galleries"):
                    return "Galleries", full_path
                if child == "Corridors":
                    return "Corridors", full_path
                if re.search(r"\bEnergization\b.*\bStart[\s-]*up\b.*\bCommissioning\b", child, re.I):
                    return "Energization, Start-up & Commissioning", full_path
            return "WBS EXCEPTION", full_path

        assigned = [identify(x) for x in source["wbs_id"].astype(str)]
        source["WBS Group"] = [x[0] for x in assigned]
        source["WBS Path"] = [x[1] for x in assigned]
        if source["task_code"].astype(str).duplicated().any():
            raise ValueError(f"Duplicate Activity ID in {area}")
        classified = source[source["WBS Group"].isin(groups)]
        excluded = source[source["WBS Group"].eq("WBS EXCEPTION")]
        if len(classified) + len(excluded) != len(source):
            raise ValueError(f"Unreconciled P6 WBS groups in {area}")
        if include_exceptions:
            return source
        return classified.copy()

    def data_hall_wbs_stats(self, area: str) -> pd.DataFrame:
        """The seven requested categories in stable original-P6 WBS order."""
        detail = self.data_hall_wbs_activities(area)
        groups = (
            "Electrical Yard", "Mechanical Yard", "Electrical Rooms",
            "Data Hall", "Galleries", "Corridors",
            "Energization, Start-up & Commissioning",
        )
        rows = []
        for label in groups:
            g = detail[detail["WBS Group"].eq(label)]
            vc = g["Status"].value_counts()
            rows.append({
                "Area": label,
                "Tasks": int(len(g)),
                "Activity Completion %": _activity_completion_pct(g),
                "Not Started": int(vc.get("Not Started", 0)),
                "In Progress": int(vc.get("In Progress", 0)),
                "Completed": int(vc.get("Completed", 0)),
            })
        summary = pd.DataFrame(rows)
        if int(summary["Tasks"].sum()) != len(detail):
            raise ValueError(f"Data Hall WBS aggregation mismatch in {area}")
        return summary

    def subarea_stats(self, area: str, helix_display: bool = False) -> pd.DataFrame:
        if area == "MOH" and self.auxiliary_tasks is not None:
            g = self.auxiliary_tasks[self.auxiliary_tasks["Area"].eq(area)].copy()
            if not g.empty:
                g["Subarea"] = g.get("task_name", pd.Series("", index=g.index)).map(_moh_package)
        else:
            g = self.current_tasks[self.current_tasks["Area"].eq(area)].copy()
        if g.empty:
            return pd.DataFrame()
        if helix_display and str(area).upper().startswith("DH"):
            g["Subarea"] = g.apply(_helix_display_subarea, axis=1)
        rows = []
        for sub, sg in g.groupby("Subarea", dropna=False):
            label = _clean_subarea(sub)
            vc = sg["Status"].value_counts()
            rows.append({
                "Area": label,
                "Tasks": int(len(sg)),
                "Activity Completion %": _activity_completion_pct(sg),
                "Not Started": int(vc.get("Not Started", 0)),
                "In Progress": int(vc.get("In Progress", 0)),
                "Completed": int(vc.get("Completed", 0)),
                "Completed %": _status_pct(sg, "Completed"),
                "In Progress %": _status_pct(sg, "In Progress"),
                "Not Started %": _status_pct(sg, "Not Started"),
            })
        if helix_display and str(area).upper().startswith("DH"):
            order = [
                "Technical & Auxiliary Rooms", "Data Hall", "Galleries", "Corridor",
                "Electrical Infrastructure & Yard", "Mechanical Systems & Yard",
                "Commissioning & Start-Up", "Other HELIX Electrical Scope",
            ]
        else:
            order = [
                "Priority Rooms", "Other Rooms", "Electrical Rooms", "Data Hall",
                "Galleries", "Corridor", "Electrical Yard", "Mechanical Yard",
                "Commissioning & Start-Up",
                "Switchgear / Main Distribution", "Transformers", "Panels",
                "CIP / Controls", "Transfer Equipment",
                "UPS / ELI / Battery Systems", "MPZ / MMR",
                "Other HELIX Electrical Scope",
            ]
        rank = {x: i for i, x in enumerate(order)}
        out = pd.DataFrame(rows)
        out["_rank"] = out["Area"].map(rank).fillna(50)
        return out.sort_values(["_rank", "Area"]).drop(columns="_rank").reset_index(drop=True)

    def independent_helix_baseline(self) -> Optional[dict[str, pd.DataFrame]]:
        """Only the approved independent HELIX baseline, no SUFFOLK fallback."""
        if self.auxiliary_path is None or self.auxiliary_tables is None:
            return None
        if self.auxiliary_path.name != "226021-HE.B.xer":
            raise ValueError("Only official independent HELIX baseline is supported")
        return summarize_approved_baseline(
            self.auxiliary_tables, str(self.auxiliary_project["proj_id"])
        )

    def independent_helix_update(self) -> Optional[dict[str, pd.DataFrame]]:
        """Official independent HELIX U02. Never substitute Suffolk Current-C."""
        if self.auxiliary_update_path is None or self.auxiliary_update_tables is None:
            return None
        if self.auxiliary_update_path.name != "226021-HE.U02.xer":
            raise ValueError("Unapproved independent HELIX Current schedule")
        return summarize_approved_baseline(
            self.auxiliary_update_tables,
            str(self.auxiliary_update_project["proj_id"]),
            snapshot_role="Current",
        )

    def independent_helix_u01(self) -> Optional[dict[str, pd.DataFrame]]:
        if self.historical_helix_tables is None or self.historical_helix_project is None:
            return None
        return summarize_approved_baseline(self.historical_helix_tables, str(self.historical_helix_project["proj_id"]), snapshot_role="Current")

    def lineup_stats(self, area: str) -> pd.DataFrame:
        """Equipment Line-Ups from the exact HELIX baseline, if available.

        Never fall back to SUFFOLK-coded activities and never use a superseded
        HELIX export as a stand-in for the official independent P6 baseline.
        """
        if self.auxiliary_path is None or self.auxiliary_tasks is None or self.auxiliary_tasks.empty:
            return pd.DataFrame()
        if self.auxiliary_path.name != "226021-HE.B.xer":
            raise ValueError("Unauthorized independent HELIX line-up source")
        g = self.auxiliary_tasks[self.auxiliary_tasks["Area"].eq(area)].copy()
        if g.empty or not str(area).upper().startswith("DH"):
            return pd.DataFrame()

        names = g.get("task_name", pd.Series("", index=g.index)).fillna("").astype(str)
        codes = g.get("task_code", pd.Series("", index=g.index)).fillna("").astype(str)
        from_name = names.str.extract(r"\b([A-HJKR]\d{3})\b", expand=False, flags=re.I)
        from_code = codes.str.extract(r"(?:^|[-_.])([A-HJKR]\d{3})(?:[-_.]|$)", expand=False, flags=re.I)
        g["Line-Up"] = from_name.fillna(from_code).str.upper()

        m = re.search(r"DH(\d{2})00", str(area).upper())
        if m:
            suffix = m.group(1) + "0"
            g = g[g["Line-Up"].fillna("").str.endswith(suffix)]

        g = g[g["Line-Up"].notna()].copy()
        if g.empty:
            return pd.DataFrame()

        rows = []
        for lineup, sg in g.groupby("Line-Up"):
            vc = sg["Status"].value_counts()
            rows.append({
                "Line-Up": lineup,
                "Tasks": int(len(sg)),
                "Activity Completion %": _activity_completion_pct(sg),
                "Not Started": int(vc.get("Not Started", 0)),
                "In Progress": int(vc.get("In Progress", 0)),
                "Completed": int(vc.get("Completed", 0)),
            })
        out = pd.DataFrame(rows)
        def lineup_key(x):
            m = re.match(r"([A-Z]+)(\d+)", str(x))
            return (int(m.group(2)) if m else 9999, m.group(1) if m else str(x))
        return out.sort_values("Line-Up", key=lambda s: s.map(lineup_key)).reset_index(drop=True)

    def scurve(self) -> pd.DataFrame:
        b = self.baseline_tasks.copy()
        c = self.current_tasks.copy()

        def pick_date(df: pd.DataFrame, cols: list[str]) -> pd.Series:
            out = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
            for col in cols:
                if col in df.columns:
                    s = pd.to_datetime(df[col], errors="coerce")
                    out = out.where(out.notna(), s)
            return out

        b_finish = pick_date(b, ["target_end_date", "early_end_date", "reend_date"])
        c_finish = pick_date(c, ["act_end_date", "reend_date", "early_end_date", "target_end_date"])
        actual_finish = pd.to_datetime(c.get("act_end_date"), errors="coerce") if "act_end_date" in c.columns else pd.Series(pd.NaT, index=c.index)

        candidates = pd.concat([b_finish.dropna(), c_finish.dropna(), actual_finish.dropna()])
        if candidates.empty:
            return pd.DataFrame()

        lo = candidates.min().normalize().replace(day=1)
        hi = candidates.max().normalize().replace(day=1) + pd.offsets.MonthEnd(1)
        grid = pd.date_range(lo, hi, freq="ME")
        if pd.notna(self.data_date) and lo <= self.data_date <= hi:
            grid = pd.DatetimeIndex(sorted(set(grid.tolist() + [pd.Timestamp(self.data_date).normalize()])))

        def cumulative_count(finishes: pd.Series) -> np.ndarray:
            clean = pd.to_datetime(finishes, errors="coerce").dt.normalize()
            return np.asarray([int((clean.notna() & (clean <= pd.Timestamp(d).normalize())).sum()) for d in grid], dtype=float)

        out = pd.DataFrame({
            "Date": grid,
            "Baseline Planned Activities": cumulative_count(b_finish),
            "Current Forecast Activities": cumulative_count(c_finish),
            "Actual Completed Activities": cumulative_count(actual_finish),
        })
        if pd.notna(self.data_date):
            out.loc[out["Date"] > pd.Timestamp(self.data_date).normalize(), "Actual Completed Activities"] = np.nan
        return out

    def fte_ready_comparison(self) -> pd.DataFrame:
        """FTE Ready milestones from the DC7 main project only.

        The comparison is strictly like-for-like between the Baseline and
        Current main schedule using the IST.6100 milestone family. No external
        projects, external activities, or cross-project relationships are used.
        """
        rows = []
        for area in [a for a in AREA_ORDER if a.startswith("DH")]:
            c = self.current_tasks[self.current_tasks["Area"].eq(area)].copy()
            mask = c.get("task_code", pd.Series("", index=c.index)).fillna("").astype(str).str.upper().str.endswith(".IST.6100")
            cand = c[mask].copy()
            if cand.empty:
                continue

            names = cand.get("task_name", pd.Series("", index=cand.index)).fillna("").astype(str)
            explicit = cand[names.str.contains("Equipment Installed & Terminated", case=False, na=False)]
            r = explicit.iloc[0] if not explicit.empty else cand.iloc[0]
            code = str(r.get("task_code", ""))

            b = self.baseline_tasks[(self.baseline_tasks["Area"].eq(area)) & (self.baseline_tasks["task_code"].astype(str).eq(code))]
            bd = _date_max(b, ["target_end_date", "early_end_date", "reend_date"]) if not b.empty else pd.NaT

            if r.get("Status") == "Completed" and pd.notna(r.get("act_end_date")):
                cd = pd.Timestamp(r.get("act_end_date"))
            else:
                cd = _date_max(pd.DataFrame([r]), ["reend_date", "early_end_date", "target_end_date", "act_end_date"])

            tf = pd.to_numeric(pd.Series([r.get("total_float_hr_cnt")]), errors="coerce").iloc[0]
            tf = float(tf / HOURS_PER_DAY) if pd.notna(tf) else np.nan
            rows.append({
                "Area": area,
                "Activity ID": code,
                "Activity Name": str(r.get("task_name", code)),
                "Baseline Date": bd,
                "Current Date": cd,
                "Finish Date Shift (d)": (bd.normalize() - cd.normalize()).days if pd.notna(cd) and pd.notna(bd) else np.nan,
                "Total Float (d)": tf,
                "Status": r.get("Status", ""),
            })
        return pd.DataFrame(rows)

    @staticmethod
    def _gate_family(name: str, code: str) -> str:
        text = f"{name} {code}".lower()
        if "fte ready" in text or text.strip().endswith(".ist.6100"):
            return "FTE Ready"
        if "l3" in text and ("start" in text or "commission" in text):
            return "L3 Start"
        if "early access" in text:
            return "Early Access"
        if "substantial completion" in text or "tco" in text:
            return "TCO"
        if "ready to receive" in text:
            return "Ready to Receive"
        if "ofci" in text or "first skid" in text:
            return "OFCI Delivery"
        return "Other"

    @staticmethod
    def _gate_area(code: str, name: str) -> str:
        text = f"{code} {name}".upper()
        for area in AREA_ORDER:
            if area in text:
                return area
        return "Other"

    def control_gates(self, max_rows: int = 50) -> pd.DataFrame:
        c = self.current_tasks.copy()
        b = self.baseline_tasks.copy()
        typ = c.get("task_type", pd.Series("", index=c.index)).fillna("").astype(str).str.upper()
        od = pd.to_numeric(c.get("target_drtn_hr_cnt", pd.Series(np.nan, index=c.index)), errors="coerce")
        c = c[typ.str.contains("MILE", na=False) | od.fillna(-1).eq(0)].copy()
        if c.empty:
            return pd.DataFrame()

        bmap = b.drop_duplicates("task_code").set_index("task_code") if "task_code" in b.columns else pd.DataFrame()
        rows = []
        for _, r in c.iterrows():
            code = str(r.get("task_code", r.get("task_id", "")))
            br = bmap.loc[code] if not bmap.empty and code in bmap.index else None
            bd = _date_max(pd.DataFrame([br]), ["target_end_date", "early_end_date", "reend_date"]) if br is not None else pd.NaT
            if r.get("Status") == "Completed" and pd.notna(r.get("act_end_date")):
                cd = pd.Timestamp(r.get("act_end_date"))
            else:
                cd = _date_max(pd.DataFrame([r]), ["reend_date", "early_end_date", "target_end_date", "act_end_date"])
            tf = pd.to_numeric(pd.Series([r.get("total_float_hr_cnt")]), errors="coerce").iloc[0]
            tf = float(tf / HOURS_PER_DAY) if pd.notna(tf) else np.nan
            v = (bd.normalize() - cd.normalize()).days if pd.notna(cd) and pd.notna(bd) else np.nan
            name = str(r.get("task_name", code))
            score = sum(1 for kw in CONTROL_GATE_KEYWORDS if kw.lower() in f"{name} {code}".lower())
            rows.append({
                "Milestone": name,
                "Activity ID": code,
                "Area": self._gate_area(code, name),
                "Milestone Type": self._gate_family(name, code),
                "Status": r.get("Status", ""),
                "Baseline Date": bd,
                "Current Date": cd,
                "Finish Date Shift": v,
                "Total Float": tf,
                "_score": score,
            })

        out = pd.DataFrame(rows)
        if (out["_score"] > 0).any():
            out = out[out["_score"] > 0]
        out = out.sort_values(["_score", "Current Date"], ascending=[False, True], na_position="last").head(max_rows)
        return out.drop(columns="_score").reset_index(drop=True)

    def diagnostics(self) -> dict:
        current_codes = set(self.current_tasks.get("task_code", pd.Series(dtype=str)).dropna().astype(str))
        baseline_codes = set(self.baseline_tasks.get("task_code", pd.Series(dtype=str)).dropna().astype(str))
        current_only = sorted(current_codes - baseline_codes)
        unassigned = self.current_tasks[self.current_tasks.get("Subarea", pd.Series("", index=self.current_tasks.index)).eq("Other HELIX Electrical Scope")].copy()
        unassigned_ids = sorted(unassigned.get("task_code", pd.Series(dtype=str)).dropna().astype(str).tolist())
        return {
            "Baseline XER": self.baseline_path.name,
            "Baseline proj_id": str(self.baseline_project.get("proj_id", "")),
            "Baseline Data Date": self.baseline_data_date,
            "Update XER": self.update_path.name,
            "Update proj_id": str(self.update_project.get("proj_id", "")),
            "Update Data Date": self.data_date,
            "HELIX Current Activities": len(self.current_tasks),
            "HELIX Baseline Comparable Activities": len(self.baseline_tasks),
            "Current-only HELIX Activities": len(current_only),
            "Current-only Activity IDs": ", ".join(current_only[:20]) if current_only else "None",
            "HELIX Activities without QTS-DASH": len(unassigned),
            "HELIX without QTS-DASH IDs": ", ".join(unassigned_ids[:30]) if unassigned_ids else "None",
            "Areas": ", ".join(self.areas()),
            "Line-Up / MOH Source": self.auxiliary_path.name if self.auxiliary_path is not None else "Not loaded: official 226021-HE.B.xer pending",
            "MOH HELIX Activities": int((self.auxiliary_tasks["Area"].eq("MOH")).sum()) if self.auxiliary_tasks is not None and not self.auxiliary_tasks.empty else 0,
            "Scope Rule": "SUFFOLK BL/UP09 drives audited HELIX-coded construction; HELIX 226021-HE.B/U02 independently drives Line-Ups/MOH",
        }


def build_dc7_model(data_dir: Path) -> DC7Model:
    bl_path, up_path = _find_files(data_dir)
    bt = parse_xer(bl_path, WANTED)
    ut = parse_xer(up_path, WANTED)
    bp = _project_row(bt, bl_path)
    up = _project_row(ut, up_path)
    bpid, upid = str(bp["proj_id"]), str(up["proj_id"])

    cur_all = to_task_frame(ut["TASK"])
    cur_all = cur_all[cur_all["proj_id"].astype(str).eq(upid)].copy()
    helix_ids = _helix_task_ids(ut, upid)
    current = scoped_helix_construction(ut, upid, helix_ids)
    if current.empty:
        raise ValueError("HELIX scope contains zero activities in the DC7 update.")

    area_map = _assignment_map(ut, upid, "QTS - AREA", "short_name")
    sub_map = _assignment_map(ut, upid, "QTS - DASH", "actv_code_name")
    current["Area"] = current["task_id"].astype(str).map(area_map).fillna("Unclassified")
    current["Subarea"] = current["task_id"].astype(str).map(sub_map).map(_clean_subarea).fillna("Other HELIX Electrical Scope")

    if current["task_code"].duplicated().any():
        raise ValueError("Duplicate task_code values found inside current HELIX scope; baseline matching is not unique.")
    base_all = to_task_frame(bt["TASK"])
    base_all = base_all[base_all["proj_id"].astype(str).eq(bpid)].copy()
    base_wbs = construction_wbs_ids(bt, bpid)
    base_all = base_all[base_all["wbs_id"].astype(str).isin(base_wbs)].copy()
    mapping = current[["task_code", "Area", "Subarea"]].drop_duplicates("task_code")
    baseline = base_all.merge(mapping, on="task_code", how="inner")

    # Only official independent HELIX Baseline. Never use historical B-4.
    # Matching must be exact; wildcard/rglob aliasing of B-4 is prohibited.
    candidates = sorted(Path(data_dir).rglob("226021-HE.B.xer"))
    if len(candidates) > 1:
        raise ValueError("Multiple HELIX official baseline files: resolve before use")
    aux_path = candidates[0] if candidates else None
    aux_tasks = pd.DataFrame()
    aux_project = None
    aux_tables = None
    if aux_path is not None:
        at = parse_xer(aux_path, WANTED)
        aux_tables = at
        projects = at["PROJECT"]
        if "proj_short_name" not in projects.columns:
            raise ValueError("Independent HELIX baseline is missing proj_short_name")
        approved = projects[
            projects["proj_short_name"].fillna("").astype(str).str.strip().str.upper().eq("226021-HE.B")
        ]
        if len(approved) != 1:
            raise ValueError("Official HELIX Baseline must contain exactly one project with ID 226021-HE.B")
        aux_project = approved.iloc[0]
        apid = str(aux_project["proj_id"])
        a_all = to_task_frame(at["TASK"])
        a_all = a_all[a_all["proj_id"].astype(str).eq(apid)].copy()
        # This is a standalone HELIX-owned P6 project: do not require a
        # SUFFOLK QTS-Subcontractor code inside HELIX's own baseline.
        # P6 PROJWBS classification is authoritative for electrical line-ups.
        aux_tasks = a_all.copy()
        a_area_map = _assignment_map(at, apid, "QTS - AREA", "short_name")
        aux_tasks["Area"] = aux_tasks["task_id"].astype(str).map(a_area_map).fillna("Unclassified")
        aux_tasks["Subarea"] = "Other HELIX Electrical Scope"

    # Authorized HELIX U02 is independent of Suffolk's current schedule.
    current_helix_files = sorted(Path(data_dir).rglob("226021-HE.U02.xer"))
    if len(current_helix_files) != 1:
        raise ValueError("Exactly one official independent HELIX U02 is required")
    auxiliary_update_path = current_helix_files[0]
    auxiliary_update_tables = parse_xer(auxiliary_update_path, WANTED)
    current_projects = auxiliary_update_tables["PROJECT"]
    current_rows = current_projects[
        current_projects["proj_short_name"].fillna("").astype(str).str.strip().eq("226021-HE.C")
    ]
    if len(current_rows) != 1:
        raise ValueError("Incorrect independent HELIX U02 project ID")
    auxiliary_update_project = current_rows.iloc[0]
    if pd.Timestamp(auxiliary_update_project["last_recalc_date"]).normalize() != pd.Timestamp("2026-10-19"):
        raise ValueError("Unexpected independent HELIX U02 Data Date")

    historical_helix_tables = None
    historical_helix_project = None
    old_files = sorted(Path(data_dir).rglob("226021-HE.U01.xer"))
    if len(old_files) == 1:
        historical_helix_tables = parse_xer(old_files[0], WANTED)
        old_rows = historical_helix_tables["PROJECT"]
        old_rows = old_rows[old_rows["proj_short_name"].fillna("").astype(str).str.strip().eq("226021-HE.U01")]
        if len(old_rows) != 1 or pd.Timestamp(old_rows.iloc[0]["last_recalc_date"]).normalize() != pd.Timestamp("2026-10-14"):
            raise ValueError("Historical HELIX U01 identity or Data Date mismatch")
        historical_helix_project = old_rows.iloc[0]

    # Trace the exact source activities, including the previous active update.
    previous_active = None
    previous_path = next(iter(sorted(Path(data_dir).rglob("226021.022.MO-UP-08.xer"))), None)
    if previous_path is not None:
        pt = parse_xer(previous_path, WANTED)
        pp = _project_row(pt, previous_path)
        previous_pid = str(pp["proj_id"])
        previous_active = scoped_helix_construction(pt, previous_pid, _helix_task_ids(pt, previous_pid))
    audit_reports = build_activity_audit(cur_all, helix_ids, current, baseline, previous_active)
    # The re-exported Suffolk BL contains additional subcontractor-code data.
    # BL/UP09 Activity-ID matches are observed values, not fixed historical
    # counts. Keep all genuine unmatched IDs visible to the internal audit.
    matched_count = int(audit_reports["summary"].loc[
        audit_reports["summary"]["Metric"].eq("Matched to Baseline by Activity ID"), "Value"
    ].iloc[0])
    unmatched = audit_reports["active"].loc[
        audit_reports["active"]["Audit"].eq("NO BASELINE MATCH"), "Activity ID"
    ].astype(str).tolist()
    # Do not pin an earlier UP08 activity count: revised XER exports can
    # legitimately add, reclassify or remove HELIX-coded construction IDs.
    # Preserve the strict reconciliation, while reporting all unmatched IDs.
    if matched_count + len(unmatched) != len(current):
        raise ValueError(
            f"Invalid UP09 Suffolk baseline reconciliation: total={len(current)}, "
            f"matched={matched_count}, unmatched={unmatched}"
        )
    previous_report = audit_reports["summary"].set_index("Metric")["Value"]
    previous_count = int(previous_report["Previous HELIX construction"])
    exited_count = int(previous_report["Former HELIX construction no longer active"])
    added_count = int(previous_report["New active HELIX IDs not in Previous"])
    if previous_count - exited_count + added_count != len(current):
        raise ValueError(
            "Suffolk UP08 → UP09 ID reconciliation failed: "
            f"previous={previous_count}, exited={exited_count}, "
            f"added={added_count}, current={len(current)}"
        )
    audit_reports["up09_baseline_unmatched"] = audit_reports["active"].loc[
        audit_reports["active"]["Audit"].eq("NO BASELINE MATCH")
    ].copy()
    audit_reports["up08_to_up09"] = pd.DataFrame([
        {"Metric": "Previous UP08 HELIX Construction", "Value": previous_count},
        {"Metric": "UP09 HELIX Construction", "Value": len(current)},
        {"Metric": "Exited construction scope", "Value": exited_count},
        {"Metric": "New construction Activity IDs", "Value": added_count},
        {"Metric": "UP09 matched to approved BL", "Value": matched_count},
        {"Metric": "UP09 without BL counterpart", "Value": len(unmatched)},
    ])

    # Updates may add, split, replace, or recode activities.
    # Baseline-vs-current comparisons use matched task_codes only,
    # while current-status analytics retain the full current HELIX scope.
    model = DC7Model(
        bl_path, up_path, bp, up, baseline, current, bt, ut,
        auxiliary_path=aux_path,
        auxiliary_tasks=aux_tasks,
        auxiliary_project=aux_project,
        auxiliary_tables=aux_tables,
        auxiliary_update_path=auxiliary_update_path,
        auxiliary_update_project=auxiliary_update_project,
        auxiliary_update_tables=auxiliary_update_tables,
        historical_helix_tables=historical_helix_tables,
        historical_helix_project=historical_helix_project,
        audit_reports=audit_reports,
    )


    # Reconcile FOH/BOH category exclusions in an explicit audit register.
    # These remain HELIX-coded, active Construction records in P6,
    # but are NOT descendants of the FOH/BOH House Systems WBS nodes.
    exception_parts = []
    for zone in ("FOH", "BOH"):
        full = model.wbs_area_activities(zone, include_exceptions=True)
        mismatch = full[full["WBS Group"].eq("Foundations")].copy()
        for _, row in mismatch.iterrows():
            exception_parts.append({
                "Activity ID": str(row["task_code"]),
                "Activity Name": str(row.get("task_name", "")),
                "QTS - AREA": zone,
                "Original P6 WBS": str(row["WBS Path"]),
                "Current Status": str(row.get("Status", "")),
                "Reconciliation": "EXCLUDED FROM FOH/BOH WBS DETAIL · RETAINED IN HELIX CONSTRUCTION SOURCE",
                "Reason": "QTS - AREA differs from original P6 WBS: Construction / Shell / Foundations",
            })
    wbs_exceptions = pd.DataFrame(exception_parts)
    if set(wbs_exceptions["Activity ID"]) != {"FDN.1296", "FDN.1300"} or len(wbs_exceptions) != 2:
        raise ValueError("Unexpected FOH/BOH Foundations exceptions; audit required")
    audit_reports["wbs_exceptions"] = wbs_exceptions
    report = audit_reports["active"]
    matched = report["Activity ID"].astype(str).isin(wbs_exceptions["Activity ID"])
    if matched.sum() != 2:
        raise ValueError("Expected both Foundations records in the active construction audit")
    report.loc[matched, "Audit"] = "WBS EXCEPTION — FOH/BOH DETAIL EXCLUDED; SOURCE INCLUDED"
    audit_reports["summary"] = pd.concat([
        audit_reports["summary"],
        pd.DataFrame([
            {"Metric": "FOH/BOH Shell-Foundations WBS exceptions (audit only)", "Value": 2},
            {"Metric": "FOH/BOH WBS detail activity count (combined)", "Value": 323},
        ]),
    ], ignore_index=True)

    # Other native Data Hall WBS branches must not silently disappear.
    # Export every excluded HELIX task by exact Activity ID and original WBS.
    dh_parts = []
    for hall in ("DH1100", "DH1200", "DH1300", "DH1400", "DH1500", "DH1600"):
        detail = model.data_hall_wbs_activities(hall, include_exceptions=True)
        for _, row in detail[detail["WBS Group"].eq("WBS EXCEPTION")].iterrows():
            dh_parts.append({
                "Activity ID": str(row["task_code"]),
                "Activity Name": str(row.get("task_name", "")),
                "QTS - AREA": hall,
                "Original P6 WBS": str(row["WBS Path"]),
                "Current Status": str(row.get("Status", "")),
                "Reconciliation": "EXCLUDED FROM SEVEN-GROUP DATA HALL DETAIL · SOURCE INCLUDED",
                "Reason": "WBS branch outside the seven selected Data Hall groups",
            })
    dh_exceptions = pd.DataFrame(dh_parts)
    if dh_exceptions["Activity ID"].nunique() != len(dh_exceptions):
        raise ValueError("Duplicate Data Hall WBS exceptions in Suffolk UP09")
    if dh_exceptions["Activity ID"].isin(wbs_exceptions["Activity ID"]).any():
        raise ValueError("Duplicate FOH/BOH and Data Hall WBS exceptions")
    audit_reports["dh_wbs_exceptions"] = dh_exceptions
    report = audit_reports["active"]
    masked = report["Activity ID"].astype(str).isin(dh_exceptions["Activity ID"])
    if masked.sum() != len(dh_exceptions):
        raise ValueError("Data Hall WBS exceptions missing from complete HELIX source audit")
    report.loc[masked, "Audit"] = "WBS EXCEPTION — DATA HALL DETAIL EXCLUDED; SOURCE INCLUDED"
    audit_reports["summary"] = pd.concat([
        audit_reports["summary"],
        pd.DataFrame([
            {"Metric": "Data Hall other P6 WBS branches (audit only)", "Value": len(dh_exceptions)},
            {"Metric": "Data Hall seven-group displayed tasks",
             "Value": sum(
                 len(model.data_hall_wbs_activities(hall))
                 for hall in ("DH1100", "DH1200", "DH1300",
                              "DH1400", "DH1500", "DH1600")
             )},
        ]),
    ], ignore_index=True)
    return model


def build_suffolk_model(helix_model: DC7Model) -> DC7Model:
    """SUFFOLK Construction scope performed by HELIX, not procurement.

    Uses the already audited HELIX construction task IDs from the Suffolk XER.
    SUFFOLK contractual finish dates still come from the full P6 PROJECT row.
    """
    update_project_id = str(helix_model.update_project["proj_id"])
    baseline_project_id = str(helix_model.baseline_project["proj_id"])
    current_all = helix_model.current_tasks.copy()
    # Already coded QTS - Subcontractor = HELIX and descended from Construction.
    # Keep QTS-AREA and original QTS-DASH assignment in their existing columns.
    if current_all.empty:
        raise ValueError("No SUFFOLK activities matched QTS - AREA.")
    if current_all["task_code"].duplicated().any():
        raise ValueError("Duplicate activity IDs in SUFFOLK QTS-AREA scope.")

    baseline_all = to_task_frame(helix_model.baseline_tables["TASK"])
    baseline_all = baseline_all[
        baseline_all["proj_id"].astype(str).eq(baseline_project_id)
    ].copy()
    baseline_wbs = construction_wbs_ids(helix_model.baseline_tables, baseline_project_id)
    baseline_all = baseline_all[baseline_all["wbs_id"].astype(str).isin(baseline_wbs)].copy()
    area_mapping = current_all[["task_code", "Area", "Subarea"]].drop_duplicates("task_code")
    baseline = baseline_all.merge(area_mapping, on="task_code", how="inner")

    return DC7Model(
        helix_model.baseline_path, helix_model.update_path,
        helix_model.baseline_project, helix_model.update_project,
        baseline, current_all,
        helix_model.baseline_tables, helix_model.update_tables,
        audit_reports=helix_model.audit_reports,
    )
