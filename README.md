# HELIX DC7 Schedule Performance Dashboard

Cloud-ready Streamlit package for the HELIX DC7 schedule dashboard.

**Version:** 0.2.11

## Data scope

This dashboard intentionally uses only the DC7 main project and its baseline:

- Current project: `proj_id 1118`
- Baseline project: `proj_id 1071`
- No `DC7-MIL`
- No `DC7.TFO-B`
- No external-project relationships in dashboard analytics

## Repository structure

```text
.
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
│   └── config.toml
├── src/
│   ├── __init__.py
│   ├── dc7_model.py
│   ├── dc7_view.py
│   └── xer.py
├── data/
│   └── DC7/
│       ├── 226021.005.MO-BL.xer
│       └── 226021.010.MO-UP.xer
└── LOGOS/
    ├── helix_logo.png
    └── toro_logo.png
```

## Local run

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

## Streamlit Community Cloud

1. Create a **private GitHub repository**.
2. Upload this folder to the repository root.
3. In Streamlit Community Cloud choose **Create app**.
4. Select the repository and branch `main`.
5. Main file path: `app.py`.
6. Deploy.

All application paths are repository-relative; no local Windows path is required.

## Security

The XER files contain detailed schedule information. Keep the GitHub repository private unless the schedule is approved for public distribution.

---

## Technical notes from the dashboard build

# DASHBOARD HELIX PROJECT · DC7 · v0.2.9

DC7 dashboard revision with one strict scope rule:

> **Only the main DC7 project is analyzed.**
> In the current XER this is `proj_id = 1118` (`226021.010.MO-UP`). External projects and cross-project relationships are excluded from dashboard calculations and visualizations.

## Main changes

### 1. Activity-based KPI logic
- Top summary uses activity status percentages instead of P6 Duration Progress.
- Completed Activities %, In Progress Activities %, Not Started Activities %.
- Current Data Date remains at the far right.
- Overall Activity Status uses activity-count metrics only.

### 2. AREA START–FINISH COMPARISON · BASELINE VS CURRENT
- Baseline is gray; Current is color-coded by finish movement.
- Start logic does not use the absolute earliest activity in the area.
- A representative production start anchor is selected from coded QTS-DASH work, excluding zero-duration milestones, `No apply` activities and the dashboard-derived Electrical Infrastructure & Equipment bucket.
- The same `task_code` is compared in Baseline and Current.
- Hover displays the representative Start Anchor ID.

### 3. FTE READY MILESTONES · BASELINE VS CURRENT
- Uses only FTE Ready milestones that belong to the main DC7 project.
- Baseline and Current are matched through the `*.IST.6100` activity family.
- No `DC7-MIL`, `DC7.TFO-B`, external milestone, or external relationship is used.
- An audit table below the chart shows the exact Activity ID so every plotted milestone can be located directly in the P6 project.

Validated FTE values:

| Area | Activity ID | Baseline | Current | Current − BL |
|---|---|---|---|---:|
| DH1100 | DHXXXX.IST.6100 | 06-Oct-2026 | 07-Oct-2026 | +1 d |
| DH1200 | DH1200.IST.6100 | 13-Oct-2026 | 29-Oct-2026 | +16 d |
| DH1300 | DH1300.IST.6100 | 28-Sep-2026 | 22-Oct-2026 | +24 d |
| DH1400 | DH1400.IST.6100 | 02-Dec-2026 | 11-Jan-2027 | +40 d |
| DH1500 | DH1500.IST.6100 | 23-Oct-2026 | 01-Dec-2026 | +39 d |
| DH1600 | DH1600.IST.6100 | 17-Feb-2027 | 17-Feb-2027 | 0 d |

### 4. Project Stats / Progress Detail
- Uses Activity Completion % = Completed / Tasks.
- Keeps Completed / In Progress / Not Started counts.

### 5. Equipment Line-Ups Progress Detail
- Appears below Project Progress Detail when a Data Hall with Line-Up activities is selected.
- Table and chart use activity-count logic.
- Line-Ups are parsed from names such as `Gallery 1102 - A110/Line-Ups // ...`.
- Shows Tasks, Activity Completion %, Not Started, In Progress and Completed.

### 6. Project Control Gates
- Main-project HELIX gates only.
- Filters by Area, Status, Gate Type, Variance and free-text Search.
- Baseline vs Current comparison retained.

### 7. Visual cleanup
- Plotly charts use explicit empty titles where appropriate to suppress stray `undefined` labels.

## Run

```powershell
cd "C:\Users\TOROPM\OneDrive - toropmc.com\DASHBOARD_HELIX_PROJECT"
py -m streamlit cache clear
py -m streamlit run app.py
```

## Expected XER pair

The official DC7 files can be directly inside `data` or inside `data\DC7`:

- `226021.005.MO-BL.xer`
- `226021.010.MO-UP.xer`

## v0.2.9.1 Hotfix

- Restored the internal helpers used by `PROJECT CONTROL GATES`:
  - `_gate_area`
  - `_gate_family`
- Validated the dashboard model against the DC7 XER pair.
- Confirmed `Current proj_id = 1118`.
- Confirmed Project Control Gates, FTE Ready Baseline-vs-Current, and Equipment Line-Ups load successfully.


## v0.2.10 — FTE Ready Control Gates

- `PROJECT CONTROL GATES` now contains only the six FTE Ready milestones from the DC7 main project.
- Uses the `IST.6100` activity family in the tracked project only.
- Baseline vs Current comparison with Finish Variance and P6 Total Float.
- Removed the large generic milestone/gate plot from the dashboard.
- Removed the separate duplicate FTE Ready section so the information appears once, as the project control-gate block.
- External projects and cross-project relationships remain excluded.


## v0.2.11 — Schedule variance sign convention

DC7 now uses one schedule-variance sign convention consistently across the dashboard:

`Variance = Baseline Date - Current Date`

Interpretation:

- **Positive variance** = Current date is earlier than Baseline = **Ahead / favorable** = green.
- **Negative variance** = Current date is later than Baseline = **Late / unfavorable** = red.
- **Zero** = no date movement = blue.

This convention is applied to:
- Project Finish Variance KPI
- Area Start Variance
- Area Finish Variance
- FTE Ready control-gate variance
- Control-gate filters and color rules

P6 Total Float keeps its own independent sign convention and is not changed by this update.
