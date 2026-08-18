"""Download monthly crime GeoJSON files from the Czech Police open-data API.

Iterates every month from START to END (inclusive), downloading
    https://kriminalita.policie.gov.cz/api/v2/downloads/YYYYMM.geojson
into ./data/. Responses are gzip-encoded; urllib handles decoding when we
request it. The endpoint is rate-limited (40 req/window), so we throttle
between requests and back off on HTTP 429.

The script is resumable: an already-present, valid (JSON-parseable) file is
skipped, so you can re-run it after an interruption.
"""

import gzip
import io
import json
import os
import time
import urllib.error
import urllib.request

BASE = "https://kriminalita.policie.gov.cz/api/v2/downloads/{ym}.geojson"
OUT_DIR = "data"
START = (2012, 1)
END = (2026, 6)
DELAY = 1.8  # seconds between requests (~33/min, under the 40 limit)
MAX_RETRIES = 5


def months(start, end):
    y, m = start
    while (y, m) <= end:
        yield f"{y}{m:02d}"
        m += 1
        if m > 12:
            y, m = y + 1, 1


def is_valid(path):
    """True if the file exists and parses as a FeatureCollection."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    try:
        with open(path, encoding="utf-8") as f:
            json.load(f)
        return True
    except (ValueError, UnicodeDecodeError):
        return False


def fetch(ym):
    url = BASE.format(ym=ym)
    req = urllib.request.Request(
        url,
        headers={
            "Accept-Encoding": "gzip",
            "User-Agent": "data-fetch/1.0",
        },
    )
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return raw
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate limited -> back off
                wait = min(60, 5 * attempt)
                print(f"  429 rate-limited, waiting {wait}s (attempt {attempt})")
                time.sleep(wait)
                continue
            if e.code == 404:  # month genuinely missing
                print(f"  404 not found for {ym}")
                return None
            print(f"  HTTP {e.code} for {ym} (attempt {attempt})")
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  network error for {ym}: {e} (attempt {attempt})")
        time.sleep(3 * attempt)
    return None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    all_months = list(months(START, END))
    print(f"{len(all_months)} months: {all_months[0]} .. {all_months[-1]}")

    downloaded = skipped = failed = 0
    for i, ym in enumerate(all_months, 1):
        path = os.path.join(OUT_DIR, f"{ym}.geojson")
        if is_valid(path):
            skipped += 1
            continue
        data = fetch(ym)
        if data is None:
            failed += 1
            print(f"[{i}/{len(all_months)}] FAILED {ym}")
        else:
            with open(path, "wb") as f:
                f.write(data)
            n = len(json.loads(data)["features"])
            downloaded += 1
            print(
                f"[{i}/{len(all_months)}] {ym}: {n} features "
                f"({len(data)//1024} KiB)"
            )
            time.sleep(DELAY)

    print(f"\nDone. downloaded={downloaded} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
