"""App backend package.

Ensures the workspace root is on sys.path so root-level modules like
`profile_manager` can be imported from backend submodules.
"""

import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
