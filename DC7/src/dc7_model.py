from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import re
import numpy as np
import pandas as pd

from config import AREA_ORDER, CONTROL_GATE_KEYWORDS, HOURS_PER_DAY
from src.xer import parse_xer, to_task_frame

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
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    all_xer = sorted(data_dir.rglob("*.xer"))
    if not all_xer:
        raise FileNotFoundError(f"No XER files found below data directory: {data_dir}")

    exact_bl = [p for p in all_xer if p.name.casefold() == "226021.005.mo-bl.xer"]
    exact_up = [p for p in all_xer if p.name.casefold() == "226021.010.mo-up.xer"]

    if exact_bl and exact_up:
        pairs = [(b, u) for b in exact_bl for u in exact_up if b.parent == u.parent]
        if pairs:
            def pair_rank(pair):
                b, _ = pair
                rel_depth = len(b.parent.relative_to(data_dir).parts) if b.parent != data_dir else 0
                dc7_penalty = 0 if b.parent.name.strip().upper() == "DC7" else 1
                return (dc7_penalty, rel_depth, str(b.parent).lower())
            return sorted(pairs, key=pair_rank)[0]
        if len(exact_bl) == 1 and len(exact_up) == 1:
            return exact_bl[0], exact_up[0]

    roots = []
    if data_dir.name.strip().upper() == "DC7":
        roots.append(data_dir)
    else:
        roots.extend([p for p in data_dir.rglob("*") if p.is_dir() and p.name.strip().upper() == "DC7"])
        roots.append(data_dir)

    seen = set()
    roots = [r for r in roots if not (str(r.resolve()).casefold() in seen or seen.add(str(r.resolve()).casefold()))]

    def eligible(p: Path) -> bool:
        text = " ".join(x.upper() for x in p.parts)
        return "TFO" not in text and "MIL" not in p.stem.upper()

    def is_dc7_main(path: Path) -> bool:
        try:
            t = parse_xer(path, ["PROJECT", "TASK"])
            row = _project_row(t, path)
            short = str(row.get("proj_short_name", "")).upper()
            name = str(row.get("proj_name", "")).upper()
            return short.startswith("226021.") or "DC7" in name
        except Exception:
            return False

    candidates = []
    for root in roots:
        files = [p for p in root.rglob("*.xer") if eligible(p)] if root != data_dir else [p for p in all_xer if eligible(p)]
        for p in files:
            if p not in candidates:
                candidates.append(p)

    bl = [p for p in candidates if re.search(r"(?:^|[._-])BL(?:[._-]|$)", p.stem, re.I) and is_dc7_main(p)]
    up = [p for p in candidates if re.search(r"(?:^|[._-])UP(?:[._-]|$)", p.stem, re.I) and is_dc7_main(p)]

    if not bl or not up:
        names = ", ".join(p.name for p in all_xer[:20])
        suffix = " ..." if len(all_xer) > 20 else ""
        raise FileNotFoundError(
            "DC7 BL/UP pair not found. Expected official files "
            "226021.005.MO-BL.xer and 226021.010.MO-UP.xer either directly "
            f"inside {data_dir} or in a DC7 subfolder. XERs seen: {names}{suffix}"
        )

    def dd_key(path: Path):
        try:
            t = parse_xer(path, ["PROJECT", "TASK"])
            p = _project_row(t, path)
            dd = pd.to_datetime(p.get("data_date"), errors="coerce")
            if pd.isna(dd):
                dd = pd.to_datetime(p.get("last_recalc_date"), errors="coerce")
            return dd if pd.notna(dd) else pd.Timestamp.min
        except Exception:
            return pd.Timestamp.min

    bl_path = max(bl, key=lambda p: (dd_key(p), p.stat().st_mtime))
    up_path = max(up, key=lambda p: (dd_key(p), p.stat().st_mtime))
    return bl_path, up_path


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
        rows = []
        for area in self.areas():
            if area == "MOH" and self.auxiliary_tasks is not None:
                g = self.auxiliary_tasks[self.auxiliary_tasks["Area"].eq(area)].copy()
            else:
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
        """Baseline vs current area spans using a representative start anchor.

        The finish remains the latest finish in the full HELIX area scope.  The
        start is no longer the absolute minimum activity start, because isolated
        early underground/underslab work can distort the apparent start of an
        entire Data Hall.  Instead we select the earliest meaningful QTS-DASH
        activity in the current area (positive duration, non-milestone, not
        marked "No apply", and not in the dashboard-derived Electrical
        Infrastructure & Equipment bucket) and compare that *same task_code*
        against Baseline.  This keeps the Start comparison like-for-like.
        """
        rows = []
        for area in self._main_areas():
            b_all = self.baseline_tasks[self.baseline_tasks["Area"].eq(area)].copy()
            c_all = self.current_tasks[self.current_tasks["Area"].eq(area)].copy()

            # Representative start anchor from the current coded production scope.
            cand = c_all[c_all["Subarea"].ne("Other HELIX Electrical Scope")].copy()
            dur = pd.to_numeric(cand.get("target_drtn_hr_cnt", pd.Series(np.nan, index=cand.index)), errors="coerce").fillna(0)
            typ = cand.get("task_type", pd.Series("", index=cand.index)).fillna("").astype(str).str.upper()
            names = cand.get("task_name", pd.Series("", index=cand.index)).fillna("").astype(str).str.lower()
            cand = cand[(dur > 0) & (~typ.str.contains("MILE", na=False)) & (~names.str.contains("no apply", na=False))].copy()

            anchor_code = ""
            anchor_name = ""
            bs = pd.NaT
            cs = pd.NaT
            if not cand.empty:
                current_start = pd.to_datetime(cand.get("act_start_date"), errors="coerce")
                for col in ["early_start_date", "restart_date", "target_start_date"]:
                    if col in cand.columns:
                        current_start = current_start.where(current_start.notna(), pd.to_datetime(cand[col], errors="coerce"))
                if current_start.notna().any():
                    idx = current_start.idxmin()
                    anchor = cand.loc[idx]
                    cs = pd.Timestamp(current_start.loc[idx])
                    anchor_code = str(anchor.get("task_code", ""))
                    anchor_name = str(anchor.get("task_name", anchor_code))
                    bmatch = b_all[b_all["task_code"].astype(str).eq(anchor_code)] if "task_code" in b_all.columns else pd.DataFrame()
                    if not bmatch.empty:
                        br = bmatch.iloc[0]
                        bs = pd.to_datetime(br.get("target_start_date"), errors="coerce")
                        if pd.isna(bs):
                            bs = pd.to_datetime(br.get("early_start_date"), errors="coerce")

            # Defensive fallback if a representative anchor cannot be identified.
            if pd.isna(bs):
                bs = _date_min(b_all, ["target_start_date", "early_start_date"])
            if pd.isna(cs):
                actuals = pd.to_datetime(c_all.get("act_start_date"), errors="coerce") if "act_start_date" in c_all.columns else pd.Series(pd.NaT, index=c_all.index)
                cs = actuals.dropna().min() if actuals.notna().any() else _date_min(c_all, ["early_start_date", "restart_date", "target_start_date"])

            bf = _date_max(b_all, ["target_end_date", "early_end_date", "reend_date"])
            cf = _date_max(c_all, ["reend_date", "early_end_date", "act_end_date", "target_end_date"])
            rows.append({
                "Area": area,
                "Baseline Start": bs,
                "Baseline Finish": bf,
                "Current Start": cs,
                "Current Forecast Finish": cf,
                "Start Date Shift (d)": (bs.normalize() - cs.normalize()).days if pd.notna(cs) and pd.notna(bs) else np.nan,
                "Finish Date Shift (d)": (bf.normalize() - cf.normalize()).days if pd.notna(cf) and pd.notna(bf) else np.nan,
                "Duration Change (d)": ((bf - bs) - (cf - cs)).days if all(pd.notna(x) for x in [bs, bf, cs, cf]) else np.nan,
                "Activity Completion %": _activity_completion_pct(c_all),
                "Start Anchor ID": anchor_code,
                "Start Anchor": anchor_name,
            })
        return pd.DataFrame(rows)

    def subarea_stats(self, area: str) -> pd.DataFrame:
        if area == "MOH" and self.auxiliary_tasks is not None:
            g = self.auxiliary_tasks[self.auxiliary_tasks["Area"].eq(area)].copy()
            if not g.empty:
                g["Subarea"] = g.get("task_name", pd.Series("", index=g.index)).map(_moh_package)
        else:
            g = self.current_tasks[self.current_tasks["Area"].eq(area)].copy()
        if g.empty:
            return pd.DataFrame()
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
        order = [
            "Priority Rooms", "Other Rooms", "Electrical Rooms", "Data Hall",
            "Galleries", "Corridor", "Electrical Yard", "Mechanical Yard",
            "Commissioning & Start-Up",
            "Switchgear / Main Distribution", "Transformers", "Panels",
            "CIP / Controls", "Transfer Equipment",
            "UPS / ELI / Battery Systems", "MPZ / MMR",
            "Other HELIX Electrical Scope"
        ]
        rank = {x: i for i, x in enumerate(order)}
        out = pd.DataFrame(rows)
        out["_rank"] = out["Area"].map(rank).fillna(50)
        return out.sort_values(["_rank", "Area"]).drop(columns="_rank").reset_index(drop=True)

    def lineup_stats(self, area: str) -> pd.DataFrame:
        """Activity-count status by Equipment Line-Up.

        DC7 line-up detail is sourced from the dedicated HELIX electrical
        schedule (226021-HE.B-4.xer) when available. This avoids the incomplete
        Activity Code assignment seen in the main project update.
        """
        source = self.auxiliary_tasks if self.auxiliary_tasks is not None and not self.auxiliary_tasks.empty else self.current_tasks
        g = source[source["Area"].eq(area)].copy()
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
            "Line-Up / MOH Source": self.auxiliary_path.name if self.auxiliary_path is not None else "Main DC7 update fallback",
            "MOH HELIX Activities": int((self.auxiliary_tasks["Area"].eq("MOH")).sum()) if self.auxiliary_tasks is not None and not self.auxiliary_tasks.empty else 0,
            "Scope Rule": "Main DC7 BL/UP drives project analytics; dedicated HELIX electrical schedule drives Line-Ups and MOH when available",
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
    current = cur_all[cur_all["task_id"].astype(str).isin(helix_ids)].copy()
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
    mapping = current[["task_code", "Area", "Subarea"]].drop_duplicates("task_code")
    baseline = base_all.merge(mapping, on="task_code", how="inner")

    # Dedicated HELIX electrical source for Line-Ups and MOH.
    aux_path = next(iter(sorted(Path(data_dir).rglob("226021-HE.B-4.xer"))), None)
    aux_tasks = pd.DataFrame()
    aux_project = None
    if aux_path is not None:
        at = parse_xer(aux_path, WANTED)
        aux_project = _project_row(at, aux_path)
        apid = str(aux_project["proj_id"])
        a_all = to_task_frame(at["TASK"])
        a_all = a_all[a_all["proj_id"].astype(str).eq(apid)].copy()
        a_helix_ids = _helix_task_ids(at, apid)
        aux_tasks = a_all[a_all["task_id"].astype(str).isin(a_helix_ids)].copy()
        a_area_map = _assignment_map(at, apid, "QTS - AREA", "short_name")
        aux_tasks["Area"] = aux_tasks["task_id"].astype(str).map(a_area_map).fillna("Unclassified")
        aux_tasks["Subarea"] = "Other HELIX Electrical Scope"

    # Updates may add, split, replace, or recode activities.
    # Baseline-vs-current comparisons use matched task_codes only,
    # while current-status analytics retain the full current HELIX scope.
    return DC7Model(
        bl_path, up_path, bp, up, baseline, current, bt, ut,
        auxiliary_path=aux_path,
        auxiliary_tasks=aux_tasks,
        auxiliary_project=aux_project,
    )


def build_suffolk_model(helix_model: DC7Model) -> DC7Model:
    """View of the SUFFOLK main project using the same XER files.

    HELIX filters are deliberately not applied to this view. Only activities
    assigned to the dashboard's approved QTS-AREA list are presented in the
    FOH/BOH/Data Hall summary; the project-level finish remains the official
    SUFFOLK project finish. No XER or scheduling calculations are changed.
    """
    update_project_id = str(helix_model.update_project["proj_id"])
    baseline_project_id = str(helix_model.baseline_project["proj_id"])
    current_all = to_task_frame(helix_model.update_tables["TASK"])
    current_all = current_all[
        current_all["proj_id"].astype(str).eq(update_project_id)
    ].copy()

    area_codes = _assignment_map(
        helix_model.update_tables, update_project_id, "QTS - AREA", "short_name"
    )
    dash_codes = _assignment_map(
        helix_model.update_tables, update_project_id, "QTS - DASH", "actv_code_name"
    )
    current_all["Area"] = current_all["task_id"].astype(str).map(area_codes)
    current_all = current_all[current_all["Area"].isin(AREA_ORDER)].copy()
    current_all["Subarea"] = (
        current_all["task_id"].astype(str)
        .map(dash_codes).map(_clean_subarea)
        .replace("Other HELIX Electrical Scope", "Other SUFFOLK Scope")
    )
    if current_all.empty:
        raise ValueError("No SUFFOLK activities matched QTS - AREA.")
    if current_all["task_code"].duplicated().any():
        raise ValueError("Duplicate activity IDs in SUFFOLK QTS-AREA scope.")

    baseline_all = to_task_frame(helix_model.baseline_tables["TASK"])
    baseline_all = baseline_all[
        baseline_all["proj_id"].astype(str).eq(baseline_project_id)
    ].copy()
    area_mapping = current_all[["task_code", "Area", "Subarea"]].drop_duplicates("task_code")
    baseline = baseline_all.merge(area_mapping, on="task_code", how="inner")

    return DC7Model(
        helix_model.baseline_path, helix_model.update_path,
        helix_model.baseline_project, helix_model.update_project,
        baseline, current_all,
        helix_model.baseline_tables, helix_model.update_tables,
    )
