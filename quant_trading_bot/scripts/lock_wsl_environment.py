"""Record the independently installed Linux dependency closure."""
from pathlib import Path
import platform
import subprocess
import sys

if platform.system() != "Linux":
    raise RuntimeError("Run this script inside the verified WSL environment")
root = Path(__file__).resolve().parents[1]
installed = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
lines = [line for line in installed.splitlines() if not line.startswith(("-e ", "mes-mnq-research", "#"))]
(root/"requirements-wsl.lock").write_text(f"# Verified {platform.platform()} Python {platform.python_version()}\n"+"\n".join(lines)+"\n")
print(f"Pinned {len(lines)} Linux packages")
