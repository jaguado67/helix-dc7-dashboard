# HELIX DC7 Schedule Performance Dashboard

Cloud-ready Streamlit package for the HELIX DC7 schedule dashboard.

**Version:** 0.2.19

## Data scope

This release has two selectable views. SUFFOLK displays the main DC7 project scope grouped by QTS - AREA, while HELIX preserves the existing subcontractor-coded analytics and dedicated HELIX electrical Line-Ups. The main source projects are:

- Current project: `proj_id 1118`
- Baseline project: `proj_id 1071`
- No `DC7-MIL`
- No `DC7.TFO-B`
- No external-project relationships in dashboard analytics

## v0.2.19 — DC7 HELIX official baseline only; historical B-4 rejected

The independent electrical DC7 HELIX reference must be the actual
Primavera P6 **`226021-HE.B` Baseline**, exported as the exact
`226021-HE.B.xer` file. The historical
`226021-HE.B-4.xer` copy is explicitly **not authorized**.

At the time of this release, the connected Drive folder
`DASHBOARD HELIX / DH / DC7` has **only the B-4 XER**, not the exact
original B XER. Until the official baseline is supplied, the dashboard:

- Does **not** ingest the historical B-4 file or its encoded repo chunks;
- Does **not** infer Line-Ups or MOH from the SUFFOLK update as fallback;
- Omits standalone MOH and marks Equipment Line-Ups **unavailable until
  official HELIX Baseline is loaded**;
- Labels HELIX current progress as the **HELIX-coded Construction slice
  from SUFFOLK Current-C**, not a standalone HELIX schedule update;
- Restricts any future independent HELIX import to the exact filename
  `226021-HE.B.xer` and the exact Primavera project
  `proj_short_name = 226021-HE.B`. The baseline cannot be substituted
  with a renamed B-4 file.

The 2,545 SUFFOLK HELIX Construction activities, 31 historical
departures, 149 classified-WBS display exceptions, FOH/BOH, Data Halls,
date comparisons and all other SUFFOLK analyses are unchanged.
There is **no independent HELIX Current** and **no independent HELIX
Baseline XER yet loaded in the published deployment**. A P6 screenshot
showing Data Date 29-Sep-2026 and Date Added 01-Oct-2026 is not by itself
sufficient to authenticate a substitute XER.

## v0.2.18 — Seven native-P6 WBS groups for SUFFOLK Data Halls

Within **SUFFOLK PROJECT PROGRESS DETAIL** for DH1100 through DH1600, 
the previous QTS-DASH grouping was replaced by the following seven
WBS-derived functional categories, in order:

1. Electrical Yard — from P6 \`Exterior Build Out / Electrical Yard\`.
2. Mechanical Yard — from P6 \`Exterior Build Out / Mechanical Yard\`.
3. Electrical Rooms — all \`Electrical Room #...\` branches together
   (including P6's \`Electrcal Room\` spelling).
4. Data Hall — from the matching \`Interior Build Out / Data Hall ####\`.
5. Galleries — consolidated \`PDU Gallery\` and \`CRAH/CDU Galleries\`.
6. Corridors — the original \`Interior Build Out / Corridors\`.
7. Energization, Start-up & Commissioning — original matching WBS branch,
   displayed even when **zero** active HELIX Construction tasks are assigned.

**Important scope control:** every count is restricted to active
\`QTS - Subcontractor = HELIX\` activities under the SUFFOLK
\`Construction\` WBS. No \`Procurement\` or archived tasks are included.
The grouping uses **native P6 PROJWBS ancestry**, not activity-name
keywords or reassignments of QTS-DASH codes.

### Exact reconciliation (SUFFOLK Current-C, P6 Data Date 26-Aug-2026)

| Area | Seven displayed WBS groups | WBS exceptions in audit | Original HELIX Construction |
|---|---:|---:|---:|
| DH1100 | 363 | 32 | 395 |
| DH1200 | 340 | 32 | 372 |
| DH1300 | 339 | 20 | 359 |
| DH1400 | 346 | 20 | 366 |
| DH1500 | 348 | 23 | 371 |
| DH1600 | 337 | 20 | 357 |
| **Total Data Halls** | **2073** | **147** | **2220** |

The 147 other active HELIX Construction tasks have different original
P6 WBS parents (e.g. \`Roof - RTUs\`, Flex, IDF, Preaction,
Restroom-Dock & Janitor and Shell/Foundations). They are not falsely
included in the seven requested categories, nor dropped from the original
**2545** HELIX Construction source activities. They appear as a **separate
Data Hall WBS classification-exceptions** table under
**SUFFOLK · HELIX CONSTRUCTION | ACTIVITY AUDIT**, downloadable by
exact Activity ID, P6 WBS path and current status. This is not the same
as the 31 departed or archived activities.

**Unchanged:** FOH/BOH WBS presentation (the two original FDN exceptions
remain audited), SUFFOLK area summary and Start-Finish windows,
HELIX VIEW, the dedicated Equipment Line-Ups and MOH, source XER
records and P6 scheduling calculations.

## v0.2.17 — Full original P6 FOH/BOH WBS displayed

**SUFFOLK PROJECT PROGRESS DETAIL** now displays **all four native direct
child WBS branches** beneath both `Front of House (FOH)` and
`Back of House (BOH)`, in original `PROJWBS.seq_num` order and
with exact P6 names. Unlike the previous version, branches with zero
HELIX Construction activities are **not hidden**.

| Native P6 WBS child | FOH: HELIX Construction tasks | BOH: HELIX Construction tasks |
|---|---:|---:|
| Priority Walls | 34 | 35 |
| Other Rooms | 145 | 81 |
| Equipment | 11 | 13 |
| Commissioning & Start Up | **0** | 4 |
| **Visible native-WBS subtotals** | **190** | **133** |

The WBS structure comes from P6; quantities are **only** HELIX-coded
active `Construction` tasks, not all subcontractors in P6.
`FDN.1296` (FOH) and `FDN.1300` (BOH) remain **outside these WBS
rows** and are visible in **SUFFOLK · HELIX CONSTRUCTION | ACTIVITY AUDIT**
under their actual `Construction / Shell / Foundations` ancestry.
The global 2,545-activity universe, original status/date values,
Line-Ups, DH sections and P6 source files remain unchanged.

## v0.2.16 — FOH/BOH Foundations WBS exceptions moved to Activity Audit

The two construction activities \`FDN.1296\` (QTS-AREA FOH) and
\`FDN.1300\` (QTS-AREA BOH) have their **actual P6 WBS ancestry**
under \`Construction / Shell / Foundations\`, outside the House Systems
FOH/BOH WBS branches. They are now **excluded from SUFFOLK FOH/BOH
PROJECT PROGRESS DETAIL tables and charts** rather than displayed as a
Foundations category:

| FOH/BOH WBS detail | FOH | BOH |
|---|---:|---:|
| P6 House Systems WBS child activities included | 190 | 133 |
| Shell / Foundations exceptions excluded from WBS detail | 1 | 1 |
| Unmodified source QTS-AREA populations | 191 | 134 |

Both activities remain **active HELIX Construction** records in the
original XER. Therefore the **2,545 HELIX Construction source count,
area summary, activity-level audit, and contractual date/area windows
are not changed**. The 2 exceptions are **not** part of the 31
departed/archived activity IDs.

Under **SUFFOLK · HELIX CONSTRUCTION | ACTIVITY AUDIT**, a distinct
**FOH/BOH WBS classification exceptions** table and downloadable CSV
now identify the two Activity IDs, QTS-AREA, original P6 WBS path,
current activity status and reason for exclusion from WBS detail.
The complete construction activity audit CSV flags both IDs for
reconciliation. No P6 codes, source files or schedules have been altered.

## v0.2.15 — FOH/BOH original P6 WBS grouping

**SUFFOLK PROJECT PROGRESS DETAIL** uses original Primavera P6 `PROJWBS`
names for **FOH** and **BOH**, rather than QTS-DASH, with no changes to
source P6 activity coding. The activity inclusion rule remains **strictly
`QTS - Subcontractor = HELIX` within `Construction` WBS and descendants**,
including commissioning and excluding procurement and archived activities.

| Exact P6 WBS name | FOH tasks | BOH tasks |
|---|---:|---:|
| Priority Walls | 34 | 35 |
| Other Rooms | 145 | 81 |
| Equipment | 11 | 13 |
| Commissioning & Start Up | 0 | 4 |
| Foundations | 1 | 1 |
| **Total** | **191** | **134** |

The `Foundations` row preserves two HELIX underslab electrical tasks
(`FDN.1296` in FOH and `FDN.1300` in BOH). Their `QTS - AREA` coding
is FOH/BOH, but their native WBS ancestry is under
`Construction / Shell / Foundations`, **not** within the P6 House Systems
FOH/BOH WBS. The dashboard makes this exception explicit rather than silently
dropping activities or renaming their original P6 WBS.

Each area offers a downloadable CSV containing all relevant Activity IDs,
P6 WBS group, full WBS path, original QTS - AREA and current P6 status.
FOH/BOH task counts and overall 2,545 HELIX Construction scope are unchanged.
All Data Halls, HELIX view, Line-Ups, and contractual finish logic remain
unchanged. CI tests verify totals, unique IDs, status reconciliation, and
the two Foundation Activity IDs.

## v0.2.14 — Verified SUFFOLK Current-C with auditable HELIX Construction

**Data sources (same independent Primavera P6 project):**

- Baseline: `226021.005.MO-BL.xer`.
- Previous: `226021.010.MO-UP.xer`.
- Current: `226021.010.MO-UP-C.xer`, verified SHA-256:
  `91bc8183e75b0e02b130a2eee512d68c054b49deeedf24e0bc07beea67839b2d`.
- Dedicated HELIX electrical line-ups/MOH: `226021-HE.B-4.xer` (unchanged).

**Strict activity selection in the SUFFOLK and HELIX views:** P6 Activity Code
`QTS - Subcontractor = HELIX` AND membership in the WBS `Construction`
or any descendant. This includes construction commissioning, excludes
Procurement, Preconstruction, BIM, milestones outside Construction, and
Archived (Deleted) Activities. Both views present **HELIX execution within
the SUFFOLK schedule**; the project finish KPI continues to read the complete
SUFFOLK PROJECT finish, and is labelled accordingly.

**Control totals at P6 Data Date 26-Aug-2026:**

| Audit | Count |
|---|---:|
| Previous HELIX Construction activities | 2576 |
| Current HELIX active Construction activities | 2545 |
| Completed | 187 |
| In Progress | 32 |
| Not Started | 2326 |
| Matched to Baseline by exact Activity ID | 2545 |
| Departed active scope | 31 |
| Of departed, now archived/outside Construction | 18 |
| Of departed, no longer in HELIX active Construction/current | 13 |
| Newly added HELIX active IDs | 0 |

Six prior `*.IST.6100` FTE milestones are now located in archived WBS;
they are **not drawn as current construction milestones**. The FTE panel
reports that comparable active milestones are missing, rather than silently
using archived data.

A new **SUFFOLK · HELIX CONSTRUCTION | ACTIVITY AUDIT** panel displays
reconciliation metrics and exports two CSV audit files:
the full 2545-Activity construction listing (BL/Previous/Current dates and
status) and 31 exited Activity IDs with their reason. No changes to P6 XER
records, codes or calendars were made.

**Important:** The file arrived in Google Drive on 12-Oct-2026, but its P6
Data Date is **26-Aug-2026**. It must never be labelled as an October
progress cutoff solely because of the upload timestamp.

## v0.2.13 — Consolidated HELIX Data Hall functional groups

The **HELIX PROJECT PROGRESS DETAIL** matrix and chart use a presentation-only
functional classification for DH1100–DH1600, reducing nine displayed categories
to seven without changing QTS-DASH assignments or any TASK records:

1. **Technical & Auxiliary Rooms** = Other Rooms + Electrical Rooms.
2. **Data Hall** = existing Data Hall category.
3. **Galleries** = existing Galleries category.
4. **Corridor** = existing Corridor category.
5. **Electrical Infrastructure & Yard** = Electrical Yard + unassigned under-slab
   electrical installation activities identified by their activity names.
6. **Mechanical Systems & Yard** = Mechanical Yard + unassigned roof RTU
   electrical-system activities identified by their activity names.
7. **Commissioning & Start-Up** = existing commissioning category.

For the published update, DH1100 remains **402 total / 8 completed /
1 in progress / 393 not started**, with an unchanged completion ratio of
about **2.0%**. The other five Data Halls use the same rule. Unknown
unassigned activity names remain in a visibly separate residual category
rather than being silently assigned to a functional bucket.

The **SUFFOLK VIEW**, HELIX total KPIs and S-curve, Equipment Line-Ups,
FTE Ready milestones, and source XER files remain unchanged. The field
QTS - DASH retains the original Primavera P6 values; only the grouped
presentation in the HELIX Data Hall detail is modified.

## v0.2.12 — Two views: SUFFOLK and HELIX

Use the **SUFFOLK / HELIX** selector immediately below the header.

- **SUFFOLK VIEW:** main DC7 project activity status in approved FOH, BOH and Data Hall QTS-AREA assignments; area-status matrix and chart; Area Start–Finish Baseline/Current comparison; SUFFOLK Project Progress Detail. No HELIX Line-Ups or FTE chart in this view.
- **HELIX VIEW:** existing QTS - Subcontractor = HELIX activity S-curve and overall status; HELIX area matrix; HELIX progress detail including MOH; dedicated Equipment Line-Ups and FTE Ready milestones. The old duplicated lower status matrix is not shown in SUFFOLK.
- **Sources:** no XER files, actual dates, or scheduling mathematics have been changed. SUFFOLK and HELIX coded progress still derive from the existing main DC7 BL/UP pair; dedicated Line-Ups/MOH derive from \`226021-HE.B-4.xer\`. The independent HELIX BL XER \`226021-HE.B\` is not present in the connected data source and is not represented as though loaded.
- **Meaning of percent:** Activity Completion % = Completed Tasks / Total Tasks, not weighted physical progress.

Automated CI validates Python compilation plus both scope models, HELIX S-curve, SUFFOLK area windows, HELIX line-ups and FTE milestones using the packaged XER files.

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

## Cloud data packaging

For Streamlit Community Cloud, the two official XER files are stored in the repository as
gzip-compressed Base64 text chunks under `data/DC7/`. At runtime `app.py` reconstructs the
original XER files into a temporary directory and passes that directory to the existing DC7
model. This changes only storage/transport; the dashboard still parses the same official XER
bytes and the same main-project scope.


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

## DC7 data-source architecture

The DC7 dashboard uses three schedule sources with separate roles:

- `DC7/data/226021.005.MO-BL.xer` — project Baseline.
- `DC7/data/226021.010.MO-UP.xer` — project Current/Update for main DC7 analytics.
- `DC7/data/226021-HE.B-4.xer` — dedicated HELIX electrical source for Equipment Line-Ups and MOH.

The dedicated HELIX electrical source is intentionally used only where it provides the cleaner coding structure:
- Equipment Line-Ups by Data Hall.
- MOH (Middle of the House) HELIX activity scope.

Main project KPIs, S-Curve, finish dates, FTE Ready milestones and Baseline-vs-Current comparisons continue to use the official DC7 Baseline/Current pair.

The dashboard filters HELIX scope through P6 Activity Code `QTS - Subcontractor = HELIX`.
