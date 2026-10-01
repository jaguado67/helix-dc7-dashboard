from pathlib import Path
import os
import sys
import base64
import gzip
import tempfile
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
for _name in list(sys.modules):
    if _name == "config" or _name == "src" or _name.startswith("src."):
        del sys.modules[_name]
if str(APP_DIR) in sys.path:
    sys.path.remove(str(APP_DIR))
sys.path.insert(0, str(APP_DIR))

from config import DATA_DIR
from src.dc7_model import build_dc7_model
from src.dc7_view import render_dashboard

def _materialize_cloud_xers(data_root: Path) -> Path:
    data_root = Path(data_root)
    dc7 = data_root
    official = (
        "226021.005.MO-BL.xer",
        "226021.010.MO-UP.xer",
    )

    if all((dc7 / name).exists() for name in official):
        return data_root

    chunk_sets = {
        name: sorted(dc7.glob(f"{name}.gz.b64.part*"))
        for name in official
    }
    if not all(chunk_sets[name] for name in official):
        return data_root

    runtime_root = Path(tempfile.gettempdir()) / "helix_dc7_runtime_data"
    runtime_dc7 = runtime_root / "DC7"
    runtime_dc7.mkdir(parents=True, exist_ok=True)

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
        "Expected application folder: DC7/data with the official DC7 Baseline "
        "and Current XER files, or their packaged cloud chunks."
    )
    st.stop()

data_dir = _materialize_cloud_xers(source_data_dir)

@st.cache_resource(show_spinner="Reading DC7 baseline/update XER and building HELIX scope…")
def load_model(path_text: str):
    return build_dc7_model(Path(path_text))

try:
    model = load_model(str(data_dir))
except Exception as exc:
    st.error(f"DC7 dashboard could not be built: {exc}")
    st.info(
        "DC7 reads the main project only. Expected official pair: "
        "226021.005.MO-BL.xer + 226021.010.MO-UP.xer."
    )
    st.stop()

render_dashboard(model)