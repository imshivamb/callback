"""Measure how late Callback's 20 ms caller clock runs on this machine.

Runs the real ``TickClock`` with nothing else going on, so the result shows the OS
timer, not model load. Two numbers:

- ``max_lateness_s``: what Callback itself records. It counts ticks that start after
  their due time, and a call logs ``clock_drift`` when it passes 0.1 s.
- wake lateness: how long after its due time each tick actually woke. Audio and chaos
  are sent at wake time, so this is the drift a call would see.

Usage: python scripts/measure_tick_lateness.py [--seconds 30] [--json out.json]
"""

import argparse
import asyncio
import json
import platform
import sys
import time
from pathlib import Path

from callback_voice.audio.format import FRAME_S
from callback_voice.caller.engine.tick_clock import TickClock

LIMIT_S = 0.1


async def measure(seconds: float) -> dict[str, object]:
    clock = TickClock()
    clock.start()
    start = time.monotonic()
    wake: list[float] = []
    ticks = round(seconds / FRAME_S)
    for _ in range(ticks):
        await clock.next()
        wake.append(time.monotonic() - (start + clock.tick * FRAME_S))
    wake.sort()
    worst = max(wake[-1], clock.max_lateness_s)
    return {
        "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
        "python": platform.python_version(),
        "event_loop": type(asyncio.get_running_loop()).__name__,
        "seconds": seconds,
        "ticks": ticks,
        "max_lateness_s": round(clock.max_lateness_s, 4),
        "wake_lateness_p50_s": round(wake[len(wake) // 2], 4),
        "wake_lateness_p99_s": round(wake[int(len(wake) * 0.99)], 4),
        "wake_lateness_max_s": round(wake[-1], 4),
        "limit_s": LIMIT_S,
        "within_limit": worst <= LIMIT_S,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--json", help="also write the result to this file")
    args = parser.parse_args()
    result = asyncio.run(measure(args.seconds))
    for key, value in result.items():
        print(f"{key:22} {value}")
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
