import sys
from pathlib import Path

# make `aegis_omega` importable when pytest is run from clients/python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
