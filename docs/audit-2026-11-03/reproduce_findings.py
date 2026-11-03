"""Run the regression tests replacing the historical bug reproducer."""
from pathlib import Path
import subprocess
import sys
if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable,"-m","pytest","-q","tests"],cwd=Path(__file__).resolve().parents[2]))
