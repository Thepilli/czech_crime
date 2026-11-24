"""Download monthly crime GeoJSON files from the Czech Police open-data API.

Iterates every month from START to END (inclusive), downloading
    https://kriminalita.policie.gov.cz/api/v2/downloads/YYYYMM.geojson
into data/raw/. The endpoint is rate-limited (40 req/window), so we throttle
between requests and back off on HTTP 429.

Resumable: an already-present, valid (JSON-parseable) file is skipped.
"""
import gzip
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..config import END, RAW_DIR, START

BASE = "https://kriminalita.policie.gov.cz/api/v2/downloads/{ym}.geojson"
DELAY = 1.8  # seconds between requests (~33/min, under the 40 limit)
MAX_RETRIES = 5


def months(start, end):
    """Yield 'YYYYMM' for every month from start to end, inclusive."""
    y, m = start
    while (y, m) <= end:
        yield f"{y}{m:02d}"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def is_valid(path: Path) -> bool:
    """True if the file exists and parses as JSON."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True
    except (ValueError, UnicodeDecodeError):
        return False


def fetch(ym: str):
    """Return the response body for one month, or None on 404 / retries exhausted."""
    req = urllib.request.Request(
        BASE.format(ym=ym),
        headers={"Accept-Encoding": "gzip", "User-Agent": "data-fetch/1.0"},
    )
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return raw
        except urllib.error.HTTPError as e:
            if e.code == 404:  # month genuinely missing
                print(f"  404 not found for {ym}")
                return None
            if e.code == 429:  # rate limited -> back off
                wait = min(60, 5 * attempt)
                print(f"  429 rate-limited, waiting {wait}s (attempt {attempt})")
                time.sleep(wait)
                continue
            print(f"  HTTP {e.code} for {ym} (attempt {attempt})")
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  network error for {ym}: {e} (attempt {attempt})")
        time.sleep(3 * attempt)
    return None


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    all_months = list(months(START, END))
    print(f"{len(all_months)} months: {all_months[0]} .. {all_months[-1]}")

    downloaded = skipped = failed = 0
    for i, ym in enumerate(all_months, 1):
        path = RAW_DIR / f"{ym}.geojson"
        if is_valid(path):
            skipped += 1
            continue
        data = fetch(ym)
        if data is None:
            failed += 1
            print(f"[{i}/{len(all_months)}] FAILED {ym}")
            continue
        # write-then-rename so an interrupted run never leaves a truncated file
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        downloaded += 1
        n = len(json.loads(data)["features"])
        print(f"[{i}/{len(all_months)}] {ym}: {n} features ({len(data) // 1024} KiB)")
        time.sleep(DELAY)

    print(f"\nDone. downloaded={downloaded} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
