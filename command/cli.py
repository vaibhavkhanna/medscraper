#!/usr/bin/env python3
"""
Hospital Scraper CLI
Usage:
  python cli.py --url https://hospital.com
  python cli.py --url hospital.com --cap 100 --output ./my_results.csv
"""

import argparse
import csv
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from crawler import crawl
from extractor import extract_from_page


def main():
    parser = argparse.ArgumentParser(description="Hospital Doctor Scraper")
    parser.add_argument("--url", required=True, help="Target website URL or domain")
    parser.add_argument("--cap", type=int, default=150, help="Max pages to crawl (default: 150)")
    parser.add_argument("--output", default="doctors.csv", help="Output CSV path")
    args = parser.parse_args()

    url = args.url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    output_path = Path(args.output)
    seen_fps: set = set()
    total_doctors = 0

    print(f"\n🏥 Hospital Scraper Starting")
    print(f"   URL     : {url}")
    print(f"   Page cap: {args.cap}")
    print(f"   Output  : {output_path}\n")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["name", "specialty", "email", "phone", "source_url"],
        )
        writer.writeheader()

        def on_progress(crawled, queued):
            print(f"  [{crawled}/{crawled+queued}] pages crawled | {total_doctors} doctors found", end="\r")

        for page_url, html in crawl(url, page_cap=args.cap, progress_callback=on_progress):
            doctors = extract_from_page(html, page_url)
            new_found = 0
            for doc in doctors:
                fp = doc.fingerprint()
                if fp not in seen_fps:
                    seen_fps.add(fp)
                    writer.writerow({
                        "name": doc.name,
                        "specialty": doc.specialty,
                        "email": doc.email,
                        "phone": doc.phone,
                        "source_url": doc.source_url,
                    })
                    f.flush()
                    new_found += 1
                    total_doctors += 1

            if new_found:
                print(f"\n  ✓ {page_url}  → {new_found} doctor(s)")

    print(f"\n\n✅ Done! {total_doctors} unique doctors saved to {output_path}\n")


if __name__ == "__main__":
    main()
