"""Shared pytest configuration."""
import sys
from pathlib import Path

# Ensure packages and apps are importable in tests
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps"))
