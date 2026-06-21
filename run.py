#!/usr/bin/env python3
"""Zero-terminal bootstrap for ojo al charqui.

Double-click start.bat (Windows) or start.command (macOS/Linux) — both call this.
On first run it creates a private .venv and installs dependencies (1-2 min);
after that it launches instantly. Re-installs only when a requirements.txt changes.

You can also just run:  python run.py
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
STAMP = VENV / ".deps-hash"
APP_MODULE = "ojoalcharqui"          # launched as `python -m ojoalcharqui`


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def requirements_files() -> list[Path]:
    """Every requirements.txt under the repo (parent + subdirs), excluding .venv."""
    return sorted(p for p in ROOT.rglob("requirements.txt") if ".venv" not in p.parts)


def deps_hash(reqs: list[Path]) -> str:
    h = hashlib.sha256()
    for r in reqs:
        h.update(r.read_bytes())
    return h.hexdigest()


def log(msg: str) -> None:
    print(f"  ojo al charqui · {msg}", flush=True)


def ensure_venv() -> None:
    if not venv_python().exists():
        log("primera vez: creando entorno (.venv)… (1-2 min)")
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)


def ensure_deps() -> None:
    reqs = requirements_files()
    if not reqs:
        return
    current = deps_hash(reqs)
    if STAMP.exists() and STAMP.read_text(encoding="utf-8").strip() == current:
        return  # deps unchanged -> skip (instant)
    py = str(venv_python())
    log("instalando dependencias…")
    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip", "--quiet"], check=False)
    for r in reqs:
        log(f"  pip install -r {r.relative_to(ROOT)}")
        subprocess.run([py, "-m", "pip", "install", "-r", str(r), "--quiet"], check=True)
    STAMP.write_text(current, encoding="utf-8")


def launch() -> int:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"              # emojis/acentos en consola y archivos
    env["PYTHONIOENCODING"] = "utf-8"
    log("abriendo la app en el navegador…")
    return subprocess.run([str(venv_python()), "-m", APP_MODULE], cwd=str(ROOT), env=env).returncode


def main() -> int:
    try:
        ensure_venv()
        ensure_deps()
        return launch()
    except subprocess.CalledProcessError as e:
        log(f"error: {e}")
        if os.name == "nt":
            input("Presiona Enter para cerrar…")
        return e.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
