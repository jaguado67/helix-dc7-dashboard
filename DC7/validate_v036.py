"""Real-P6-XER smoke tests: two independent pairs, no cross-source leakage."""
from pathlib import Path
import pandas as pd

from src.source_loader import materialize_dc7_sources
from src.dc7_model import build_dc7_model, build_suffolk_model
from src.helix_baseline import (
    lineup_area_status_summary, helix_baseline_overview,
)

folder=Path(__file__).resolve().parents[1]/"data"
data=materialize_dc7_sources(folder)
helix=build_dc7_model(data)
suffolk=build_suffolk_model(helix)

assert suffolk.baseline_path.name=="226021.005.MO-BL.xer"
assert suffolk.update_path.name=="226021.022.MO-UP-08.xer"
assert str(suffolk.data_date.date())=="2026-09-30"
assert helix.auxiliary_path.name=="226021-HE.B.xer"
assert helix.auxiliary_current_path.name=="226021-HE.U01.xer"
assert str(pd.Timestamp(helix.auxiliary_current_project["last_recalc_date"]).date())=="2026-10-14"

b=helix.independent_helix_baseline()
u=helix.independent_helix_current()
assert set(b["_audit"]["Activity ID"]) == set(u["_audit"]["Activity ID"])
assert len(b["_audit"])==len(u["_audit"])==4153
bs=lineup_area_status_summary(b)
us=lineup_area_status_summary(u)
assert int(bs["Completed"].sum())==2
assert int(bs["In Progress"].sum())==0
assert int(us["Completed"].sum())==42
assert int(us["In Progress"].sum())==11
assert int(us["Not Started"].sum())==4100
assert int(us["Total Tasks"].sum())==4153
assert int(sum(us["Completed"]+us["In Progress"]+us["Not Started"]))==4153
assert set(u["_audit"]["QTS - Subcontractor"])=={"HELIX"}
assert "MOH" in set(us["Area"])
assert int(suffolk.status_counts()["Total"])>2000
assert int(suffolk.status_counts()["Total"])<3000
assert len(suffolk.area_windows())==8
print("PASS: official Suffolk and HELIX source files, BL/current, statuses and area audit")
print("SUFFOLK",suffolk.status_counts(),"data date",suffolk.data_date)
print("HELIX",int(us["Total Tasks"].sum()),"statuses",int(us["Completed"].sum()),int(us["In Progress"].sum()),int(us["Not Started"].sum()))
