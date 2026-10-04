"""Demo mode (`run.py --demo`): the fictional dataset in data-demo/, with live actions switched off.

Demo brands are invented, so scanning them on Meta would be pointless and would mix real data
into the demo set. Scans, schedules, AI runs and landing captures are refused with a clear message.
"""

from __future__ import annotations

import os

from fastapi import HTTPException

DEMO_MESSAGE = (
    "Demo mode shows a fictional dataset, so live scans and AI runs are off. Start the app without --demo."
)


def is_demo() -> bool:
    return os.environ.get("ADSPY_DEMO") == "1"


def require_live() -> None:
    if is_demo():
        raise HTTPException(403, DEMO_MESSAGE)
