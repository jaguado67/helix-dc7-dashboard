"""SHA-verified original DC7 P6 schedule sources for Cloud and local runs."""
from __future__ import annotations

import base64
import gzip
import hashlib
import tempfile
from pathlib import Path

SOURCES = {
    "226021.005.MO-BL.xer": "c9c52105d0ab7331fa9e964618986645380ec27a5280cba4799405de619742b2",
    "226021.022.MO-UP-08.xer": "2860a45ccdc71cb70905eaafc9b6cb56fa87985fdd9c448ed8be9f9201c6e73e",
    "226021-HE.B.xer": "1057564634e2392de2f5a3f825d15363a50f5a8f9b152bc1733c128dbf1d8d2b",
    "226021-HE.U01.xer": "e5398c6e17c4797d7e269273e2104971730c7c0e3fd4e010f246924ca3bec472",
}
OPTIONAL_PREVIOUS = {
    "226021.010.MO-UP-C.xer": "91bc8183e75b0e02b130a2eee512d68c054b49deeedf24e0bc07beea67839b2d",
}

def materialize_dc7_sources(data_dir: Path) -> Path:
    """Materialize exactly the pinned schedules. Reject stale or mixed updates.

    Supports original raw XER, the previous gzip+base64 chunk packages,
    and the new raw-base64 chunk package for the 5 MB SUFFOLK update.
    """
    source = Path(data_dir)
    if not source.is_dir():
        raise FileNotFoundError(f"DC7 source directory missing: {source}")
    output = Path(tempfile.gettempdir()) / "dc7_helix_v036_verified" / "DC7"
    output.mkdir(parents=True, exist_ok=True)

    for filename, checksum in {**SOURCES, **OPTIONAL_PREVIOUS}.items():
        path = source / filename
        if path.is_file():
            blob = path.read_bytes()
        else:
            gzip_parts = sorted(source.glob(f"{filename}.gz.b64.part*"))
            base64_parts = sorted(source.glob(f"{filename}.b64.part*"))
            if gzip_parts:
                text = "".join(p.read_text(encoding="ascii").strip() for p in gzip_parts)
                blob = gzip.decompress(base64.b64decode(text))
            elif base64_parts:
                text = "".join(p.read_text(encoding="ascii").strip() for p in base64_parts)
                blob = base64.b64decode(text, validate=True)
            elif filename in OPTIONAL_PREVIOUS:
                continue
            else:
                raise FileNotFoundError(f"Verified DC7 original XER not found: {filename}")
        digest = hashlib.sha256(blob).hexdigest()
        if digest != checksum:
            raise ValueError(f"P6 source checksum mismatch for {filename}: {digest}")
        target = output / filename
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            target.write_bytes(blob)

    for mandatory in SOURCES:
        if not (output / mandatory).is_file():
            raise FileNotFoundError(f"Missing validated DC7 source: {mandatory}")
    return output.parent
