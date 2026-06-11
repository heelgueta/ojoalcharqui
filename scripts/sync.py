"""Move scraped data between computers without re-scraping.

The DBs are merge-friendly by design (UUID run ids, store-native product keys),
so two machines that scraped independently can union their history with no
collisions. This script wraps three steps:

  snapshot   -> freeze each live store DB into data/snapshots/<store>_<stamp>.sqlite
  merge <P>  -> fold snapshot/exported DBs from another machine into local live DBs
  push/pull  -> (optional) move the snapshots folder via rclone to a cloud remote

Transport is your choice — rclone (any of ~70 clouds), a Dropbox/Drive synced
folder, a private Git-LFS repo, or a plain USB copy. `merge` is what makes any of
them safe: it's idempotent and keyed on run id.

Usage:
  python scripts/sync.py snapshot                 # freeze all stores
  python scripts/sync.py merge path/to/dir_or.sqlite   # merge in others' data
  python scripts/sync.py push                     # rclone -> remote (needs setup)
  python scripts/sync.py pull                      # rclone <- remote
"""
import glob
import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ojoalcharqui import config, adapters
from ojoalcharqui.db import StoreDB
from ojoalcharqui import queries

# rclone remote:path — override via env OAC_RCLONE_REMOTE (e.g. "b2:oac-data")
RCLONE_REMOTE = os.environ.get("OAC_RCLONE_REMOTE", "oac:ojoalcharqui")


def snapshot_all():
    made = []
    for s in queries.available_stores():
        if not s["n_products"]:
            continue
        info = queries.make_snapshot(s["slug"])
        made.append(info["snapshot"])
        print(f"  snapshot {info['snapshot']} ({info['bytes']//1024} KB)")
    if not made:
        print("  nothing to snapshot")
    return made


def merge(path: str):
    """Merge one DB file, or every *.sqlite under a directory, into local DBs."""
    p = Path(path)
    files = sorted(glob.glob(str(p / "*.sqlite"))) if p.is_dir() else [str(p)]
    if not files:
        print(f"  no .sqlite found at {path}")
        return
    for f in files:
        slug = _slug_of(f)
        if not slug:
            print(f"  skip {os.path.basename(f)} (no store identity)")
            continue
        try:
            a = adapters.get(slug)
            name, plat = a.name, a.platform
        except KeyError:
            name, plat = slug, ""
        db = StoreDB(config.db_path(slug), slug, name, plat)
        res = db.merge_from(f)
        db.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db.close()
        print(f"  merged {os.path.basename(f)} -> {slug}: +{res['new_runs']} new run(s)")


def _slug_of(dbfile: str) -> str | None:
    import sqlite3
    try:
        con = sqlite3.connect(f"file:{dbfile}?mode=ro", uri=True)
        row = con.execute("SELECT value FROM meta WHERE key='store_slug'").fetchone()
        con.close()
        return row[0] if row else None
    except Exception:
        return None


def _rclone(direction: str):
    src, dst = (str(config.SNAPSHOT_DIR), RCLONE_REMOTE)
    if direction == "pull":
        src, dst = dst, src
    print(f"  rclone sync {src} -> {dst}")
    try:
        subprocess.run(["rclone", "sync", src, dst, "--progress"], check=True)
    except FileNotFoundError:
        print("  rclone not installed. See https://rclone.org/install/ , then "
              "`rclone config` a remote and set OAC_RCLONE_REMOTE.")
    except subprocess.CalledProcessError as e:
        print(f"  rclone failed: {e}")


def main(argv):
    cmd = argv[0] if argv else "help"
    if cmd == "snapshot":
        snapshot_all()
    elif cmd == "merge" and len(argv) > 1:
        merge(argv[1])
    elif cmd == "push":
        snapshot_all(); _rclone("push")
    elif cmd == "pull":
        _rclone("pull")
        print("  now run: python scripts/sync.py merge", config.SNAPSHOT_DIR)
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
