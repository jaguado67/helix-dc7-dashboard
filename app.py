from pathlib import Path
import os
import streamlit as st

from config import DATA_DIR
from src.dc7_model import build_dc7_model
from src.dc7_view import render_dashboard

st.set_page_config(page_title="HELIX Project Dashboard · DC7",page_icon="📊",layout="wide",initial_sidebar_state="collapsed")
data_dir=Path(os.environ.get("HELIX_PROJECT_DATA_DIR",str(DATA_DIR)))
if not data_dir.exists():
    st.error(f"HELIX Project data directory was not found: {data_dir}")
    st.info("Expected repository folder: data/DC7 with the official DC7 Baseline and Current XER files.")
    st.stop()

@st.cache_resource(show_spinner="Reading DC7 baseline/update XER and building HELIX scope…")
def load_model(path_text:str):
    return build_dc7_model(Path(path_text))

try:
    model=load_model(str(data_dir))
except Exception as exc:
    st.error(f"DC7 dashboard could not be built: {exc}")
    st.info("DC7 reads the main project only. Expected XER pair: 226021.005.MO-BL.xer + 226021.010.MO-UP.xer, directly inside data or inside data/DC7.")
    st.stop()
render_dashboard(model)
