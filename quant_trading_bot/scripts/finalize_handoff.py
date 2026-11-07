"""Publish the current real-data handoff after verification and research."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("publish_current_handoff.py")), run_name="__main__")
