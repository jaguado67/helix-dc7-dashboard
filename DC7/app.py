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
    # Only the official HELIX project baseline is authorized as a separate source.
    # The historical "-4" copy must never be materialized or silently substituted.
    helix_baseline = "226021-HE.B.xer"
    suffolk_update = "226021.025.MO-UP-09.xer"
    suffolk_update_sha = "71a469ad623a751295e00874b5c82ddd58c7a94aac06c3e8f5f07ce25f6ad18f"
    helix_update = "226021-HE.U02.xer"
    helix_update_sha = "bbe3545be853972e745e96f8072cca9cc1561486ce24b51d5d2fa0519f7c8d14"
    required = official + (previous,)

    runtime_root = Path(tempfile.gettempdir()) / "helix_dc7_runtime_data"
    runtime_dc7 = runtime_root / "DC7"
    runtime_dc7.mkdir(parents=True, exist_ok=True)
    manifest = dc7 / "226021.010.MO-UP-C.xer.sha256"
    if not manifest.exists():
        # Local development with raw XER files is allowed; cloud packaging is pinned.
        if all((dc7 / name).is_file() for name in required):
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

    # Approved Suffolk baseline source, including QTS Subcontractor codes.
    suffolk_bl = runtime_dc7 / "226021.005.MO-BL.xer"
    if hashlib.sha256(suffolk_bl.read_bytes()).hexdigest() != "c63ae17acdba3b6ee36f8a14aefa10cceaf25fa0758a02a9f31a35f104821f41":
        raise ValueError("Suffolk Baseline SHA-256 mismatch")

    # Import SHA-verified original HELIX P6 Baseline; never the rejected -4.
    approved_baseline = dc7 / helix_baseline
    approved_manifest = dc7 / f"{helix_baseline}.sha256"
    pinned = "e7b6ed260af314eb34e51d7ac504edfe577051b21eca7ea6efe13ac98d110dc3"
    if not approved_manifest.is_file():
        raise FileNotFoundError("Official HELIX Baseline checksum manifest missing")
    if approved_manifest.read_text(encoding="ascii").split()[0] != pinned:
        raise ValueError("HELIX baseline SHA-256 manifest mismatch")
    if approved_baseline.is_file():
        payload = approved_baseline.read_bytes()
    else:
        parts = sorted(dc7.glob(f"{helix_baseline}.gz.b64.part*"))
        if not parts:
            raise FileNotFoundError("Official HELIX baseline encoded XER package missing")
        encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
        payload = gzip.decompress(base64.b64decode(encoded))
    if len(payload) != 3042490 or hashlib.sha256(payload).hexdigest() != pinned:
        raise ValueError("Official HELIX Baseline failed size or SHA-256 verification")
    baseline_target = runtime_dc7 / helix_baseline
    if not baseline_target.is_file() or baseline_target.read_bytes() != payload:
        baseline_target.write_bytes(payload)

    # Independent HELIX U02 (14-Oct-2026 Data Date) is a separate P6
    # schedule from Suffolk Current-C. Preserve the exact XER byte stream.
    source_update = dc7 / helix_update
    encoded_parts = sorted(dc7.glob(f"{helix_update}.raw.b64.part*"))
    if source_update.is_file():
        current_payload = source_update.read_bytes()
    elif encoded_parts:
        current_payload = base64.b64decode(
            "".join(part.read_text(encoding="ascii").strip() for part in encoded_parts),
            validate=True,
        )
    else:
        raise FileNotFoundError("Official HELIX U02 XER not found (no Suffolk substitution)")
    if len(current_payload) != 3044697 or hashlib.sha256(current_payload).hexdigest() != helix_update_sha:
        raise ValueError("Independent HELIX U02 failed byte-size or SHA-256 verification")
    update_target = runtime_dc7 / helix_update
    if not update_target.is_file() or update_target.read_bytes() != current_payload:
        update_target.write_bytes(current_payload)

    # Suffolk UP09 is the new independent Construction Current, and the
    # former Current-C stays available for exact update-to-update audits.
    source_suffolk = dc7 / suffolk_update
    suffolk_parts = sorted(dc7.glob(f"{suffolk_update}.raw.b64.part*"))
    if source_suffolk.is_file():
        suffolk_payload = source_suffolk.read_bytes()
    elif suffolk_parts:
        suffolk_payload = base64.b64decode(
            "".join(p.read_text(encoding="ascii").strip() for p in suffolk_parts),
            validate=True,
        )
    else:
        raise FileNotFoundError("Official Suffolk UP09 not found")
    if len(suffolk_payload) != 4632544 or hashlib.sha256(suffolk_payload).hexdigest() != suffolk_update_sha:
        raise ValueError("Suffolk UP09 byte-size/SHA-256 verification failed")
    suffolk_target = runtime_dc7 / suffolk_update
    if not suffolk_target.is_file() or suffolk_target.read_bytes() != suffolk_payload:
        suffolk_target.write_bytes(suffolk_payload)
    # Retain original U01 exclusively for optional historical S-curve overlay.
    previous_name = "226021-HE.U01.xer"
    previous_parts = sorted(dc7.glob(f"{previous_name}.raw.b64.part*"))
    if previous_parts:
        previous_bytes = base64.b64decode("".join(p.read_text(encoding="ascii").strip() for p in previous_parts), validate=True)
        if hashlib.sha256(previous_bytes).hexdigest() != "25c2147a28092762e375d9ae6afb39bc8e34890f806046be229e6b8239943e7a":
            raise ValueError("HELIX historical U01 checksum mismatch")
        (runtime_dc7 / previous_name).write_bytes(previous_bytes)
    # Preserve Suffolk UP08 for update-to-update comparison against UP09.
    prior_suffolk = "226021.022.MO-UP-08.xer"
    prior_source = dc7 / prior_suffolk
    if prior_source.is_file():
        previous_payload = prior_source.read_bytes()
        if hashlib.sha256(previous_payload).hexdigest() != "c1d04c9b13a7504dc9f20b279398a6c4cb57cd346d87b4157d42bf175dbc73ac":
            raise ValueError("Historical Suffolk UP08 checksum mismatch")
        (runtime_dc7 / prior_suffolk).write_bytes(previous_payload)
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

MODEL_VERSION = "dc7-2026-10-28-l3-optional-baseline-v043"

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
        "Required schedules: SUFFOLK 226021.005.MO-BL / 226021.025.MO-UP-09 "
        "and independent HELIX 226021-HE.B / 226021-HE.U02."
    )
    st.stop()

render_dashboard(helix_model, suffolk_model)