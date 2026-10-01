from pathlib import Path
import os
import base64
import gzip
import tempfile
import streamlit as st

from config_tfo import DATA_DIR
from src.dc7_tfo_model import build_dc7_model
from src.dc7_tfo_view import render_dashboard

st.set_page_config(
    page_title="HELIX Project Dashboard · DC7.TFO",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

def _materialize_cloud_xers(data_root: Path) -> Path:
    data_root = Path(data_root)
    dc7 = data_root / "DC7.TFO"
    official = (
        "DC7.TFO-BL.xer",
        "DC7.TFO-B.xer",
    )

    if all((dc7 / name).exists() for name in official):
        return data_root

    runtime_root = Path(tempfile.gettempdir()) / "helix_dc7_tfo_runtime_data"
    runtime_dc7 = runtime_root / "DC7.TFO"
    runtime_dc7.mkdir(parents=True, exist_ok=True)

    packaged = {name: dc7 / f"{name}.b64" for name in official}
    if all(packaged[name].exists() for name in official):
        for name in official:
            target = runtime_dc7 / name
            if not target.exists():
                encoded = packaged[name].read_text(encoding="ascii").strip()
                target.write_bytes(base64.b64decode(encoded))
        return runtime_root

    chunk_sets = {
        name: sorted(dc7.glob(f"{name}.gz.b64.part*"))
        for name in official
    }
    if not all(chunk_sets[name] for name in official):
        return data_root

    for name in official:
        target = runtime_dc7 / name
        if not target.exists():
            encoded = "".join(
                part.read_text(encoding="ascii").strip()
                for part in chunk_sets[name]
            )
            target.write_bytes(gzip.decompress(base64.b64decode(encoded)))

    return runtime_root

source_data_dir = Path(os.environ.get("HELIX_PROJECT_DATA_DIR", str(DATA_DIR)))
if not source_data_dir.exists():
    st.error(f"HELIX Project data directory was not found: {source_data_dir}")
    st.info(
        "Expected repository folder: data/DC7.TFO with the official DC7.TFO Baseline "
        "and Current XER files, or their packaged cloud chunks."
    )
    st.stop()

data_dir = _materialize_cloud_xers(source_data_dir)

@st.cache_resource(show_spinner="Reading DC7.TFO baseline/update XER and building HELIX scope…")
def load_model(path_text: str):
    return build_dc7_model(Path(path_text))

try:
    model = load_model(str(data_dir))
except Exception as exc:
    st.error(f"DC7.TFO dashboard could not be built: {exc}")
    st.info(
        "DC7.TFO reads the TFO project only. Expected official pair: "
        "DC7.TFO-BL.xer + DC7.TFO-B.xer."
    )
    st.stop()

render_dashboard(model)