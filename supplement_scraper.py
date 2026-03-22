#!/usr/bin/env python3
"""
Serbian Supplement Store Dashboard - Scraper & Dashboard Generator

Scrapes supplement products from popular Serbian online stores,
saves data as JSON, and generates an HTML dashboard showing discounts.

Usage:
    python supplement_scraper.py                          # Scrape all stores
    python supplement_scraper.py --stores GymBeam FitLab  # Specific stores
    python supplement_scraper.py --discounts-only         # Only discounted products
    python supplement_scraper.py --delay 2.0              # Custom delay between requests
    python supplement_scraper.py --list-stores            # List available stores
"""

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any

from supplement_stores import ALL_SCRAPERS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY_DIR = os.path.join(DATA_DIR, "supplements_history")
OUTPUT_JSON = os.path.join(DATA_DIR, "supplements.json")
DASHBOARD_TEMPLATE = os.path.join(BASE_DIR, "supplement_dashboard.html")
DASHBOARD_OUTPUT = os.path.join(BASE_DIR, "supplement_dashboard_live.html")


def get_store_map() -> Dict[str, type]:
    """Map store names (case-insensitive) to scraper classes."""
    store_map = {}
    for scraper_cls in ALL_SCRAPERS:
        store_map[scraper_cls.STORE_NAME.lower()] = scraper_cls
        # Also map by simplified name
        simple = scraper_cls.STORE_NAME.lower().replace(' ', '').replace('.', '')
        store_map[simple] = scraper_cls
    return store_map


def build_weekly_summary(products: List[Dict[str, Any]], previous_data: dict = None) -> Dict[str, Any]:
    """Build a weekly summary of discounted products."""
    discounted = [p for p in products if p.get("discount_percent", 0) > 0]

    # Summary by store
    by_store = {}
    for p in discounted:
        store = p["store"]
        if store not in by_store:
            by_store[store] = {"count": 0, "total_discount": 0, "store_url": p.get("store_url", "")}
        by_store[store]["count"] += 1
        by_store[store]["total_discount"] += p["discount_percent"]

    for store_data in by_store.values():
        if store_data["count"] > 0:
            store_data["avg_discount"] = round(store_data["total_discount"] / store_data["count"], 1)
        del store_data["total_discount"]

    # Summary by category
    by_category = {}
    for p in discounted:
        cat = p.get("category", "Ostalo") or "Ostalo"
        if cat not in by_category:
            by_category[cat] = {"count": 0, "total_discount": 0}
        by_category[cat]["count"] += 1
        by_category[cat]["total_discount"] += p["discount_percent"]

    for cat_data in by_category.values():
        if cat_data["count"] > 0:
            cat_data["avg_discount"] = round(cat_data["total_discount"] / cat_data["count"], 1)
        del cat_data["total_discount"]

    # Top discounts
    top_discounts = sorted(discounted, key=lambda x: x.get("discount_percent", 0), reverse=True)[:20]

    # Average discount
    avg_discount = 0
    if discounted:
        avg_discount = round(sum(p["discount_percent"] for p in discounted) / len(discounted), 1)

    # Week comparison (new/ended discounts)
    new_discounts = []
    ended_discounts = []
    deeper_discounts = []

    if previous_data and "products" in previous_data:
        prev_discounted_ids = {
            p["id"]: p for p in previous_data["products"]
            if p.get("discount_percent", 0) > 0
        }
        curr_discounted_ids = {p["id"]: p for p in discounted}

        # New discounts: in current but not in previous
        for pid, product in curr_discounted_ids.items():
            if pid not in prev_discounted_ids:
                new_discounts.append(product)

        # Ended discounts: in previous but not in current
        for pid, product in prev_discounted_ids.items():
            if pid not in curr_discounted_ids:
                ended_discounts.append(product)

        # Deeper discounts: discount increased
        for pid, product in curr_discounted_ids.items():
            if pid in prev_discounted_ids:
                prev_pct = prev_discounted_ids[pid].get("discount_percent", 0)
                curr_pct = product.get("discount_percent", 0)
                if curr_pct > prev_pct:
                    product["previous_discount_percent"] = prev_pct
                    deeper_discounts.append(product)

    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())

    return {
        "week_of": week_start.strftime("%Y-%m-%d"),
        "generated_at": today.strftime("%Y-%m-%d %H:%M"),
        "total_products": len(products),
        "total_discounted": len(discounted),
        "avg_discount_percent": avg_discount,
        "top_discounts": top_discounts,
        "by_store": by_store,
        "by_category": by_category,
        "new_discounts_count": len(new_discounts),
        "ended_discounts_count": len(ended_discounts),
        "deeper_discounts_count": len(deeper_discounts),
        "new_discounts": new_discounts[:10],
        "ended_discounts": ended_discounts[:10],
        "deeper_discounts": deeper_discounts[:10],
    }


def load_previous_data() -> dict:
    """Load the most recent historical snapshot for comparison."""
    if not os.path.exists(HISTORY_DIR):
        return {}

    files = sorted([
        f for f in os.listdir(HISTORY_DIR)
        if f.startswith("supplements_") and f.endswith(".json")
    ], reverse=True)

    # Skip today's file if it exists, get the previous one
    today_file = f"supplements_{datetime.now().strftime('%Y-%m-%d')}.json"
    for f in files:
        if f != today_file:
            try:
                with open(os.path.join(HISTORY_DIR, f), 'r', encoding='utf-8') as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, IOError):
                continue
    return {}


def save_json(data: dict, path: str):
    """Save data to JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved data to {path}")


def save_history_snapshot(data: dict):
    """Save a dated snapshot to history directory."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(HISTORY_DIR, f"supplements_{date_str}.json")
    save_json(data, path)


def generate_dashboard(data: dict):
    """Generate the live dashboard HTML by embedding JSON data into the template."""
    if not os.path.exists(DASHBOARD_TEMPLATE):
        logger.warning(f"Dashboard template not found at {DASHBOARD_TEMPLATE}")
        return

    with open(DASHBOARD_TEMPLATE, 'r', encoding='utf-8') as f:
        template = f.read()

    # Embed the JSON data
    json_str = json.dumps(data, ensure_ascii=False)
    # Replace the placeholder in the template
    output = template.replace('/* __SUPPLEMENT_DATA_PLACEHOLDER__ */', json_str)

    with open(DASHBOARD_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(output)

    logger.info(f"Dashboard generated at {DASHBOARD_OUTPUT}")


def main():
    parser = argparse.ArgumentParser(
        description="Serbian Supplement Store Scraper & Dashboard Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--stores", nargs="*",
        help="Scrape only specific stores (by name). Use --list-stores to see options."
    )
    parser.add_argument(
        "--discounts-only", action="store_true",
        help="Only save products that have a discount."
    )
    parser.add_argument(
        "--delay", type=float, default=1.5,
        help="Delay in seconds between requests (default: 1.5)."
    )
    parser.add_argument(
        "--output", default=OUTPUT_JSON,
        help=f"Output JSON path (default: {OUTPUT_JSON})."
    )
    parser.add_argument(
        "--no-dashboard", action="store_true",
        help="Skip generating the HTML dashboard."
    )
    parser.add_argument(
        "--list-stores", action="store_true",
        help="List all available store scrapers and exit."
    )
    parser.add_argument(
        "--serve", action="store_true",
        help="Start a local web server to view the dashboard after scraping."
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port for the web server (default: 8000). Used with --serve."
    )

    args = parser.parse_args()

    if args.list_stores:
        print("\nAvailable store scrapers:\n")
        for s in ALL_SCRAPERS:
            print(f"  {s.STORE_NAME:<25} {s.BASE_URL}")
        print(f"\nTotal: {len(ALL_SCRAPERS)} stores\n")
        sys.exit(0)

    # Determine which stores to scrape
    store_map = get_store_map()
    scrapers_to_run = []

    if args.stores:
        for name in args.stores:
            key = name.lower().replace(' ', '').replace('.', '')
            if key in store_map:
                scrapers_to_run.append(store_map[key])
            else:
                logger.error(f"Unknown store: '{name}'. Use --list-stores to see options.")
                sys.exit(1)
    else:
        scrapers_to_run = list(ALL_SCRAPERS)

    # Create shared session
    import requests
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "sr-Latn-RS,sr;q=0.9,en;q=0.8",
    })

    # Scrape
    all_products = []
    stores_scraped = []
    stores_failed = []

    print(f"\n{'='*60}")
    print(f"  Serbian Supplement Store Scraper")
    print(f"  Scraping {len(scrapers_to_run)} store(s)...")
    print(f"{'='*60}\n")

    for scraper_cls in scrapers_to_run:
        try:
            scraper = scraper_cls(session=session, delay=args.delay)
            products = scraper.scrape_all()
            all_products.extend(products)
            stores_scraped.append(scraper_cls.STORE_NAME)
            print(f"  ✓ {scraper_cls.STORE_NAME}: {len(products)} products")
        except Exception as e:
            logger.error(f"Failed to scrape {scraper_cls.STORE_NAME}: {e}")
            stores_failed.append(scraper_cls.STORE_NAME)
            print(f"  ✗ {scraper_cls.STORE_NAME}: FAILED ({e})")

    # Filter discounts only if requested
    if args.discounts_only:
        all_products = [p for p in all_products if p.get("discount_percent", 0) > 0]
        logger.info(f"Filtered to {len(all_products)} discounted products")

    # Deduplicate by ID (keep first occurrence)
    seen_ids = set()
    unique_products = []
    for p in all_products:
        if p["id"] not in seen_ids:
            seen_ids.add(p["id"])
            unique_products.append(p)
    all_products = unique_products

    # Load previous data for weekly comparison
    previous_data = load_previous_data()

    # Build weekly summary
    summary = build_weekly_summary(all_products, previous_data)

    # Compile output
    output_data = {
        "scraped_at": datetime.now().isoformat(),
        "stores_scraped": stores_scraped,
        "stores_failed": stores_failed,
        "total_products": len(all_products),
        "total_discounted": summary["total_discounted"],
        "products": all_products,
        "weekly_summary": summary,
    }

    # Save
    save_json(output_data, args.output)
    save_history_snapshot(output_data)

    # Generate dashboard
    if not args.no_dashboard:
        generate_dashboard(output_data)

    # Print summary
    discounted_count = summary["total_discounted"]
    print(f"\n{'='*60}")
    print(f"  Scraping Complete!")
    print(f"  Total products: {len(all_products)}")
    print(f"  On discount:    {discounted_count}")
    if discounted_count > 0:
        print(f"  Avg discount:   {summary['avg_discount_percent']}%")
    print(f"  Stores OK:      {len(stores_scraped)}")
    if stores_failed:
        print(f"  Stores failed:  {len(stores_failed)} ({', '.join(stores_failed)})")
    print(f"\n  Data saved to:  {args.output}")
    if not args.no_dashboard:
        print(f"  Dashboard at:   {DASHBOARD_OUTPUT}")
    print(f"{'='*60}\n")

    # Start web server if requested
    if args.serve and not args.no_dashboard:
        import functools
        import http.server
        import socketserver

        dashboard_dir = os.path.dirname(DASHBOARD_OUTPUT) or "."
        dashboard_filename = os.path.basename(DASHBOARD_OUTPUT)
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=dashboard_dir)

        try:
            with socketserver.TCPServer(("0.0.0.0", args.port), handler) as httpd:
                url = f"http://localhost:{args.port}/{dashboard_filename}"
                print(f"  Dashboard server running at: {url}")
                print(f"  Press Ctrl+C to stop.\n")
                httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server stopped.")
        except OSError as e:
            logger.error(f"Could not start server on port {args.port}: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
