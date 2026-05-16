#!/usr/bin/env python3
"""
scheduler.py — Run pipeline.py on a schedule (no cron needed)
Refreshes data every 15 min during market hours, hourly otherwise.

Usage:
  pip install schedule
  python scheduler.py
"""

import time
import subprocess
import sys
from datetime import datetime

try:
    import schedule
except ImportError:
    print("Run: pip install schedule")
    sys.exit(1)


def is_market_hours():
    h = datetime.now().hour
    # HK/CN/JP/KR daytime OR US evening/night session (HKT)
    return (9 <= h < 16) or (21 <= h < 24) or (0 <= h < 4)


def run():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] Running pipeline...")
    result = subprocess.run(
        [sys.executable, "pipeline.py", "--output", "data.json"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print("ERROR:", result.stderr)


def smart_run():
    if is_market_hours():
        run()
    else:
        print(f"[{datetime.now():%H:%M}] Outside market hours, skipping.")


# Schedule runs
schedule.every(15).minutes.do(smart_run)
schedule.every().day.at("09:25").do(run)   # HK open
schedule.every().day.at("21:25").do(run)   # US open

print("📅 Scheduler started. Ctrl+C to stop.")
run()   # run immediately on start

while True:
    schedule.run_pending()
    time.sleep(60)
