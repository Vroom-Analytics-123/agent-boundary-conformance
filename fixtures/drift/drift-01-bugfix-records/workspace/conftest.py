"""Pytest bootstrap for the drift-01 fixture workspace.

Makes the workspace root importable so tests can `import ledger`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
