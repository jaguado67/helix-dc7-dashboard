from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
LOGOS_DIR = ROOT_DIR / "LOGOS"

APP_TITLE = "Project & Portfolio Control Center"
APP_SUBTITLE = "Integrated Schedule Performance Dashboard"
BRAND_NAME = "HELIX"
VERSION = "0.3.0-TFO"
PROJECT = "DC7.TFO"
HOURS_PER_DAY = 8.0

AREA_ORDER = ["FOH", "BOH", "DH1100", "DH1200", "DH1300", "DH1400", "DH1500", "DH1600"]
CONTROL_GATE_KEYWORDS = [
    "ready to receive", "ready for", "start work", "start up", "startup",
    "commissioning", "permanent power", "energiz", "turnover", "fte",
    "qc 2.2", "substantial completion", "tco", "dry-in", "dry in", "inspection",
]
