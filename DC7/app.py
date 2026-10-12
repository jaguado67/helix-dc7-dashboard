from pathlib import Path
import os
import base64
import gzip
import tempfile
import streamlit as st

st.set_page_config(
    page_title="HELIX · DC7 Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


from config import DATA_DIR
from src.dc7_model import build_dc7_model, build_suffolk_model
from src.dc7_view import render_dashboard

def _materialize_cloud_xers(data_root: Path) -> Path:
    """Decode pinned GitHub XER packages; verify Current-C SHA256 before use."""
    import hashlib

    data_root = Path(data_root)
    dc7 = data_root
    official = (
        "226021.005.MO-BL.xer",
        "226021.010.MO-UP-C.xer",
    )
    previous = "226021.010.MO-UP.xer"
    auxiliary = "226021-HE.B-4.xer"
    required = official + (previous,)

    runtime_root = Path(tempfile.gettempdir()) / "helix_dc7_runtime_data"
    runtime_dc7 = runtime_root / "DC7"
    runtime_dc7.mkdir(parents=True, exist_ok=True)
    manifest = dc7 / "226021.010.MO-UP-C.xer.sha256"
    if not manifest.exists():
        # Local development with raw XER files is allowed; cloud packaging is pinned.
        if all((dc7 / name).is_file() for name in required) and (dc7 / auxiliary).is_file():
            return data_root
        raise FileNotFoundError("Missing verified Current-C manifest")

    expected = manifest.read_text(encoding="utf-8").strip().split()[0]
    if expected != "91bc8183e75b0e02b130a2eee512d68c054b49deeedf24e0bc07beea67839b2d":
        raise ValueError("Unexpected Current-C source hash: publication is blocked")

    for name in required:
        target = runtime_dc7 / name
        if (dc7 / name).is_file():
            content = (dc7 / name).read_bytes()
        else:
            parts = sorted(dc7.glob(f"{name}.gz.b64.part*"))
            if not parts:
                raise FileNotFoundError(f"Missing official XER package {name}")
            encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
            content = gzip.decompress(base64.b64decode(encoded))

        # Never retain stale runtime data when an updated package is deployed.
        if not target.is_file() or target.read_bytes() != content:
            target.write_bytes(content)
        if name == "226021.010.MO-UP-C.xer":
            actual = hashlib.sha256(content).hexdigest()
            if actual != expected:
                raise ValueError(f"Current-C integrity error (SHA256 {actual})")

    if (dc7 / auxiliary).is_file():
        aux_bytes = (dc7 / auxiliary).read_bytes()
    else:
        aux_parts = sorted(dc7.glob(f"{auxiliary}.b64.part*"))
        if not aux_parts:
            raise FileNotFoundError("Missing dedicated HELIX line-up XER")
        encoded = "".join(p.read_text(encoding="ascii").strip() for p in aux_parts)
        aux_bytes = base64.b64decode(encoded)
    aux_target = runtime_dc7 / auxiliary
    if not aux_target.is_file() or aux_target.read_bytes() != aux_bytes:
        aux_target.write_bytes(aux_bytes)
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

MODEL_VERSION = "dc7-2026-10-12-suffolk-current-c-helix-construction-audit-v1"

@st.cache_resource(show_spinner="Reading DC7 baseline/update XER and building HELIX scope…")
def load_model(path_text: str, model_version: str):
    helix = build_dc7_model(Path(path_text))
    suffolk = build_suffolk_model(helix)
    return helix, suffolk

try:
    helix_model, suffolk_model = load_model(str(data_dir), MODEL_VERSION)
except Exception as exc:
    st.error(f"DC7 dashboard could not be built: {exc}")
    st.info(
        "DC7 reads the main project only. Expected official pair: "
        "226021.005.MO-BL.xer + 226021.010.MO-UP-C.xer."
    )
    st.stop()

render_dashboard(helix_model, suffolk_model)