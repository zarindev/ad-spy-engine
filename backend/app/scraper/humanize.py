"""Human-like pacing: randomized delays, variable scroll distances, occasional longer pauses."""

from __future__ import annotations

import random
import threading
import time
from collections.abc import Sequence


def jitter(bounds: Sequence[float]) -> float:
    low, high = float(bounds[0]), float(bounds[1])
    return random.uniform(min(low, high), max(low, high))


def sleep_range(bounds: Sequence[float], cancel: threading.Event | None = None) -> None:
    """Sleep a random duration; wakes early (returns) if `cancel` is set."""
    duration = jitter(bounds)
    if cancel is not None:
        cancel.wait(duration)
    else:
        time.sleep(duration)


def maybe_long_pause(chance: float, bounds: Sequence[float], cancel: threading.Event | None = None) -> bool:
    if random.random() < chance:
        sleep_range(bounds, cancel)
        return True
    return False


def scroll_distance(bounds: Sequence[int]) -> int:
    return int(jitter(bounds))


def human_scroll(driver, total_px: int, steps: int | None = None) -> None:  # noqa: ANN001
    """Scroll in a few uneven increments instead of one jump."""
    steps = steps or random.randint(2, 4)
    remaining = total_px
    for i in range(steps):
        part = remaining if i == steps - 1 else int(remaining * random.uniform(0.25, 0.55))
        driver.execute_script("window.scrollBy(0, arguments[0]);", part)
        remaining -= part
        time.sleep(random.uniform(0.08, 0.3))
