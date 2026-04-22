import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Add storebox directory for hoc app (AYY-30 HO Console)
STOREBOX = ROOT.parent / "storebox"
if STOREBOX.exists() and str(STOREBOX) not in sys.path:
    sys.path.insert(0, str(STOREBOX))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "conf.settings")

import django  # noqa: E402

django.setup()
