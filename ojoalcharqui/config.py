"""Paths and global knobs."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
IMAGE_DIR = DATA_DIR / "images"

for _d in (DATA_DIR, SNAPSHOT_DIR, IMAGE_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def db_path(store_slug: str) -> Path:
    """The live, append-only DB for one store."""
    return DATA_DIR / f"{store_slug}.sqlite"
