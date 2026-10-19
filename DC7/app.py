"""HELIX · DC7 dashboard backed by audited SUFFOLK and HELIX XER pairs."""
from pathlib import Path
import os
import streamlit as st

st.set_page_config(
    page_title="HELIX · DC7 Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from config import DATA_DIR
from src.source_loader import materialize_dc7_sources
from src.dc7_model import build_dc7_model, build_suffolk_model
from src.dc7_view import render_dashboard

data_root = Path(os.environ.get("HELIX_PROJECT_DATA_DIR", str(DATA_DIR)))
try:
    verified_root = materialize_dc7_sources(data_root)
except Exception as exc:
    st.error(f"DC7 schedule source verification failed: {exc}")
    st.stop()

MODEL_VERSION = "dc7-2026-10-19-suffolk-up08-helix-u01-v036"

@st.cache_resource(show_spinner="Auditing SUFFOLK UP-08 and HELIX U01 XER schedules…")
def load_model(path_text: str, model_version: str):
    helix_source = build_dc7_model(Path(path_text))
    suffolk = build_suffolk_model(helix_source)
    return helix_source, suffolk

try:
    helix_model, suffolk_model = load_model(str(verified_root), MODEL_VERSION)
except Exception as exc:
    st.error(f"DC7 model audit failed: {exc}")
    st.info(
        "Required: SUFFOLK BL 226021.005.MO-BL / UP-08 226021.022.MO-UP-08 "
        "and HELIX BL 226021-HE.B / U01 226021-HE.U01."
    )
    st.stop()

render_dashboard(helix_model, suffolk_model)
