#!/usr/bin/env python3
"""Download and extract IRS 990 TEOS XML batches into datasets/.

Run with the project venv's python (needs zipfile_inflate64 to handle the
Deflate64-compressed batches that stdlib zipfile and the system `unzip`/
`ditto`/`bsdtar` all fail on): .venv/bin/python3 scripts/fetch_2025_batches.py
"""
import shutil
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import zipfile_inflate64  # noqa: F401 - patches zipfile to support Deflate64 (method 9)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASETS_DIR = REPO_ROOT / "datasets"
BASE_URL = "https://apps.irs.gov/pub/epostcard/990/xml/{year}/"

BATCHES_BY_YEAR = {
    2023: [f"2023_TEOS_XML_{m:02d}A" for m in range(1, 13)],
    2024: [f"2024_TEOS_XML_{m:02d}A" for m in range(1, 13)],
    2025: [
        "2025_TEOS_XML_01A", "2025_TEOS_XML_02A", "2025_TEOS_XML_03A", "2025_TEOS_XML_04A",
        "2025_TEOS_XML_05A", "2025_TEOS_XML_05B", "2025_TEOS_XML_06A", "2025_TEOS_XML_07A",
        "2025_TEOS_XML_08A", "2025_TEOS_XML_09A", "2025_TEOS_XML_10A", "2025_TEOS_XML_11A",
        "2025_TEOS_XML_11B", "2025_TEOS_XML_11C", "2025_TEOS_XML_11D", "2025_TEOS_XML_12A",
    ],
}

YEARS = [2023, 2024]


def download(url, dest, retries=3):
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp, open(dest, "wb") as f:
                expected = resp.headers.get("Content-Length")
                shutil.copyfileobj(resp, f, length=1024 * 1024)
            if expected is not None and dest.stat().st_size != int(expected):
                raise IOError(
                    f"truncated download: got {dest.stat().st_size} bytes, expected {expected}"
                )
            return
        except Exception as exc:  # noqa: BLE001
            print(f"    attempt {attempt} failed: {exc}")
            if attempt == retries:
                raise
            time.sleep(5)


def main():
    tmp_zip = REPO_ROOT / "_tmp_batch.zip"
    all_batches = [(year, name) for year in YEARS for name in BATCHES_BY_YEAR[year]]

    for year, name in all_batches:
        target = DATASETS_DIR / name
        if target.exists() and any(target.iterdir()):
            print(f"[skip] {name} already present ({len(list(target.iterdir()))} files)")
            continue

        url = BASE_URL.format(year=year) + name + ".zip"
        print(f"[download] {name} <- {url}")
        start = time.time()
        download(url, tmp_zip)
        size_mb = tmp_zip.stat().st_size / 1_000_000
        print(f"  downloaded {size_mb:.0f}MB in {time.time() - start:.0f}s")

        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(tmp_zip) as zf:
            zf.extractall(target)
        n = len(list(target.iterdir()))
        print(f"  extracted {n} files -> {target}")
        tmp_zip.unlink()

    print("\nDone. Batch directory counts:")
    for year, name in all_batches:
        target = DATASETS_DIR / name
        n = len(list(target.iterdir())) if target.exists() else 0
        print(f"  {name}: {n}")


if __name__ == "__main__":
    main()
