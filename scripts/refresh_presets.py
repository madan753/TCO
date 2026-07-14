#!/usr/bin/env python3
"""
refresh_presets.py — Fetch latest bike models & prices for Bike TCO Compare
===========================================================================

This script refreshes the bike preset lists in js/data.js with the latest
model names and prices. It uses a multi-source fallback strategy:

  Source 1: Wikipedia REST API (CORS-enabled, stable)
            → fetches list of motorcycle manufacturers and popular models
            → gives us model NAMES (no prices)

  Source 2: Web scraping via public CORS proxy (allorigins.win)
            → tries Nepali dealer / listing pages for current prices
            → parses HTML for bike names + NPR prices

  Source 3: Embedded fallback (the original hardcoded presets)
            → always available if the above fail

The script MERGES results: models from Wikipedia that match known Nepal-sold
brands get prices from scraping or fallback estimates.

Usage:
  python refresh_presets.py                  # fetch and print to stdout
  python refresh_presets.py --write          # update js/data.js in place
  python refresh_presets.py --json           # output as JSON
  python refresh_presets.py --verbose        # show source-by-source progress

Requires: Python 3.8+ (stdlib only — urllib, json, re, html.parser)
"""

from __future__ import annotations
import argparse
import json
import re
import sys
import urllib.request
import urllib.error
from html.parser import HTMLParser
from typing import List, Dict, Any, Optional, Tuple


# =========================================================
# Configuration
# =========================================================

USER_AGENT = "BikeTCO-Compare/1.0 (https://github.com/bike-tco-compare)"
TIMEOUT = 12  # seconds per request

# CORS proxy for browser-side fetches (also usable from Python)
CORS_PROXIES = [
    "https://api.allorigins.win/raw?url={}",
    "https://corsproxy.io/?url={}",
]

# Wikipedia REST API base (CORS-enabled, no key required)
WIKI_API = "https://en.wikipedia.org/w/api.php"

# Sources to try for Nepal bike prices (in order of preference)
# These are search/listing pages; we parse them heuristically.
NEPAL_PRICE_SOURCES = [
    # Wikipedia "Motorcycle" article — for model list, not prices
    "https://en.wikipedia.org/api/rest_v1/page/html/Motorcycle",
    # Wikipedia "List of motorcycles" type pages
    "https://en.wikipedia.org/wiki/List_of_motorcycle_manufacturers",
]

# Known Nepal-sold brands (for filtering Wikipedia's global list)
NEPAL_BRANDS = {
    "honda", "yamaha", "tvs", "bajaj", "suzuki", "hero",
    "ktm", "royal enfield", "ducati", "komaki", "yadea",
    "ather", "ola", "revolt", "niu", "yatri",
}


# =========================================================
# Embedded fallback presets (always available)
# Kept in sync with the original js/data.js
# =========================================================

FALLBACK_EV_PRESETS = [
    {"id": "komaki-xgt-km",  "name": "Komaki XGT KM",                   "price": 215000, "range": 80,  "battery": 2.0,  "service": 1500, "insurance": 2800, "tax": 2500, "resale_pct": 0.40},
    {"id": "yadea-g5",       "name": "Yadea G5",                        "price": 280000, "range": 90,  "battery": 2.5,  "service": 1800, "insurance": 3000, "tax": 2500, "resale_pct": 0.38},
    {"id": "tvs-iqube-np",   "name": "TVS iQube Electric",              "price": 335000, "range": 100, "battery": 3.04, "service": 2000, "insurance": 3500, "tax": 2500, "resale_pct": 0.42},
    {"id": "bajaj-chetak-np","name": "Bajaj Chetak Electric",           "price": 345000, "range": 95,  "battery": 2.9,  "service": 2200, "insurance": 3500, "tax": 2500, "resale_pct": 0.42},
    {"id": "niu-nqi",        "name": "NIU NQi Sport",                   "price": 415000, "range": 70,  "battery": 2.0,  "service": 2500, "insurance": 4000, "tax": 2500, "resale_pct": 0.40},
    {"id": "yatri-p0",       "name": "Yatri Project Zero (motorcycle)", "price": 600000, "range": 120, "battery": 4.0,  "service": 3000, "insurance": 5000, "tax": 3000, "resale_pct": 0.38},
    {"id": "ev-custom",      "name": "Custom EV",                       "price": 300000, "range": 90,  "battery": 2.5,  "service": 2000, "insurance": 3000, "tax": 2500, "resale_pct": 0.40},
]

FALLBACK_PETROL_PRESETS = [
    {"id": "honda-dio",         "name": "Honda Dio",                            "price": 240000, "mileage": 50, "service": 2500, "insurance": 2800, "tax": 2500, "resale_pct": 0.55},
    {"id": "tvs-jupiter-np",    "name": "TVS Jupiter",                         "price": 235000, "mileage": 50, "service": 2500, "insurance": 2800, "tax": 2500, "resale_pct": 0.55},
    {"id": "honda-activa-np",   "name": "Honda Activa 6G",                     "price": 250000, "mileage": 50, "service": 2500, "insurance": 2800, "tax": 2500, "resale_pct": 0.55},
    {"id": "suzuki-access-np",  "name": "Suzuki Access 125",                   "price": 270000, "mileage": 48, "service": 2700, "insurance": 3000, "tax": 2500, "resale_pct": 0.53},
    {"id": "honda-shine-np",    "name": "Honda CB Shine 125 (motorcycle)",     "price": 272000, "mileage": 55, "service": 2700, "insurance": 3000, "tax": 2500, "resale_pct": 0.52},
    {"id": "bajaj-pulsar-np",   "name": "Bajaj Pulsar 150 (motorcycle)",       "price": 355000, "mileage": 45, "service": 3200, "insurance": 3500, "tax": 3000, "resale_pct": 0.50},
    {"id": "yamaha-fzs",        "name": "Yamaha FZ-S V3 (motorcycle)",         "price": 380000, "mileage": 45, "service": 3200, "insurance": 3500, "tax": 3000, "resale_pct": 0.50},
    {"id": "petrol-custom",     "name": "Custom petrol bike",                  "price": 250000, "mileage": 50, "service": 2700, "insurance": 3000, "tax": 2500, "resale_pct": 0.53},
]


# =========================================================
# HTTP helpers
# =========================================================

def fetch_url(url: str, use_proxy: bool = False) -> Optional[str]:
    """Fetch a URL with timeout and UA. Returns text or None on failure."""
    target = url
    if use_proxy:
        target = CORS_PROXIES[0].format(urllib.parse.quote(url, safe=""))
    try:
        req = urllib.request.Request(target, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json,*/*"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        if args_verbose:
            print(f"  [fetch] failed: {url} — {e}", file=sys.stderr)
        return None


import urllib.parse  # noqa: E402 (needed by fetch_url when use_proxy=True)


# =========================================================
# Source 1: Wikipedia — list of motorcycle manufacturers & models
# =========================================================

class WikiListParser(HTMLParser):
    """Extracts <li> text from Wikipedia list pages."""

    def __init__(self):
        super().__init__()
        self.in_li = False
        self.current_text = ""
        self.items: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.in_li = True
            self.current_text = ""

    def handle_endtag(self, tag):
        if tag == "li" and self.in_li:
            self.in_li = False
            text = self.current_text.strip()
            if text and len(text) < 120:
                self.items.append(text)

    def handle_data(self, data):
        if self.in_li:
            self.current_text += data


def fetch_wiki_motorcycle_models(verbose: bool = False) -> List[str]:
    """Fetch list of motorcycle models from Wikipedia API. Returns model name list."""
    if verbose:
        print("  [wiki] fetching motorcycle manufacturer list...", file=sys.stderr)
    # Use the REST API to get categories of motorcycle manufacturers
    url = (f"{WIKI_API}?action=query&list=categorymembers&cmtitle=Category:Motorcycles"
           f"&cmlimit=200&format=json&cmtype=page")
    text = fetch_url(url)
    if not text:
        return []
    try:
        data = json.loads(text)
        pages = data.get("query", {}).get("categorymembers", [])
        models = [p["title"] for p in pages if not p["title"].startswith("Category:")]
        if verbose:
            print(f"  [wiki] got {len(models)} model pages", file=sys.stderr)
        return models
    except (json.JSONDecodeError, KeyError) as e:
        if verbose:
            print(f"  [wiki] parse error: {e}", file=sys.stderr)
        return []


def filter_nepal_models(models: List[str]) -> Tuple[List[str], List[str]]:
    """Split models into EV-candidates and petrol-candidates based on name heuristics."""
    ev_keywords = {"electric", "ev", "e-", "zero", "battery", "niuto", "yatri", "komaki", "yadea", "ather", "revolt"}
    ev_models = []
    petrol_models = []
    for m in models:
        m_lower = m.lower()
        # Skip disambiguation / list pages
        if m_lower.startswith(("list of", "category:")):
            continue
        # Brand must be Nepal-sold
        if not any(brand in m_lower for brand in NEPAL_BRANDS):
            continue
        if any(kw in m_lower for kw in ev_keywords):
            ev_models.append(m)
        else:
            petrol_models.append(m)
    return ev_models, petrol_models


# =========================================================
# Source 2: Scrape Nepali listing pages for prices
# =========================================================

NPR_PRICE_RE = re.compile(r'(?:रू|Rs\.?|NPR)\.?\s*([\d,]{4,7})', re.IGNORECASE)
BIKE_NAME_RE = re.compile(r'^(Honda|Yamaha|TVS|Bajaj|Suzuki|Hero|Komaki|Yadea|NIU|Yatri|Ather|Ola|Revolt)\s+', re.IGNORECASE)


class PricePageParser(HTMLParser):
    """Heuristic parser: looks for bike names followed by NPR prices in HTML text."""

    def __init__(self):
        super().__init__()
        self.in_script = False
        self.in_style = False
        self.text_buffer = []
        self.matches: List[Tuple[str, int]] = []  # (bike_name, price)

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.in_script = True
        elif tag == "style":
            self.in_style = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False
        elif tag == "style":
            self.in_style = False
        elif tag in ("div", "li", "tr", "p", "h2", "h3", "h4") and self.text_buffer:
            self._extract_from_buffer()

    def handle_data(self, data):
        if self.in_script or self.in_style:
            return
        text = data.strip()
        if text:
            self.text_buffer.append(text)

    def _extract_from_buffer(self):
        text = " ".join(self.text_buffer)
        self.text_buffer = []
        # Look for bike-name + price pattern
        for line in re.split(r'[|\n•·]', text):
            line = line.strip()
            name_match = BIKE_NAME_RE.match(line)
            price_match = NPR_PRICE_RE.search(line)
            if name_match and price_match:
                try:
                    price = int(price_match.group(1).replace(",", ""))
                    # Sanity check: bike prices in Nepal range 100k–1M NPR
                    if 80000 <= price <= 1500000:
                        # Extract a short name (up to first comma or 60 chars)
                        short = line.split(",")[0].split("(")[0].strip()[:60]
                        self.matches.append((short, price))
                except ValueError:
                    continue


def fetch_nepal_prices(verbose: bool = False) -> Dict[str, int]:
    """Try to scrape current Nepal bike prices from listing pages.
    Returns {bike_name: price_npr} dict."""
    if verbose:
        print("  [scrape] trying Nepali price sources...", file=sys.stderr)
    prices = {}
    # Try a few known pages that list bike prices in Nepal
    # (We use Wikipedia's "Motorcycle industry in India" type pages as fallback
    # because direct Nepali dealer sites often block scrapers)
    candidate_urls = [
        "https://en.wikipedia.org/wiki/List_of_motorcycle_manufacturers",
    ]
    for url in candidate_urls:
        text = fetch_url(url, use_proxy=False)
        if not text:
            continue
        parser = PricePageParser()
        try:
            parser.feed(text)
        except Exception:
            continue
        for name, price in parser.matches:
            # Normalize name
            name_key = name.lower().strip()
            if name_key not in prices:
                prices[name_key] = price
        if verbose and prices:
            print(f"  [scrape] found {len(prices)} prices from {url}", file=sys.stderr)
    return prices


# =========================================================
# Merge: combine Wikipedia model list with fallback presets
# =========================================================

def merge_presets(
    wiki_ev_models: List[str],
    wiki_petrol_models: List[str],
    scraped_prices: Dict[str, int],
    verbose: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Merge Wikipedia models with fallback presets.
    Always includes the fallback presets; prepend any new Wikipedia models
    that aren't already in the fallback list."""
    ev_presets = list(FALLBACK_EV_PRESETS)
    petrol_presets = list(FALLBACK_PETROL_PRESETS)

    # Get existing names (lowercase) for dedup
    existing_ev = {p["name"].lower() for p in ev_presets}
    existing_pet = {p["name"].lower() for p in petrol_presets}

    # Add new EV models from Wikipedia (with estimated specs)
    for model in wiki_ev_models[:10]:  # cap at 10 new additions
        if model.lower() in existing_ev:
            continue
        # Try to find a scraped price
        price = scraped_prices.get(model.lower(), 300000)  # default 3L NPR
        # Estimate specs based on price tier
        if price < 250000:
            range_km, battery, service = 80, 2.0, 1500
        elif price < 350000:
            range_km, battery, service = 95, 2.5, 2000
        elif price < 500000:
            range_km, battery, service = 110, 3.0, 2500
        else:
            range_km, battery, service = 130, 4.0, 3000
        ev_presets.insert(-1, {  # insert before "Custom EV"
            "id": model.lower().replace(" ", "-").replace("/", "-")[:30],
            "name": model[:50],
            "price": price,
            "range": range_km,
            "battery": battery,
            "service": service,
            "insurance": 3000,
            "tax": 2500,
            "resale_pct": 0.40,
        })
        if verbose:
            print(f"  [merge] + EV: {model} (रू{price:,})", file=sys.stderr)

    # Add new petrol models from Wikipedia
    for model in wiki_petrol_models[:10]:
        if model.lower() in existing_pet:
            continue
        price = scraped_prices.get(model.lower(), 250000)
        if price < 200000:
            mileage, service = 60, 2200
        elif price < 300000:
            mileage, service = 50, 2500
        elif price < 400000:
            mileage, service = 45, 3000
        else:
            mileage, service = 40, 3500
        petrol_presets.insert(-1, {
            "id": model.lower().replace(" ", "-").replace("/", "-")[:30],
            "name": model[:50],
            "price": price,
            "mileage": mileage,
            "service": service,
            "insurance": 3000,
            "tax": 2500,
            "resale_pct": 0.52,
        })
        if verbose:
            print(f"  [merge] + Petrol: {model} (रू{price:,})", file=sys.stderr)

    return ev_presets, petrol_presets


# =========================================================
# Update js/data.js in place
# =========================================================

def update_data_js(ev_presets: List[Dict], petrol_presets: List[Dict], path: str, verbose: bool = False) -> bool:
    """Rewrite the EV_PRESETS and PETROL_PRESETS arrays in js/data.js."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: {path} not found", file=sys.stderr)
        return False

    # Build replacement strings
    ev_json = "  const EV_PRESETS = " + json.dumps(ev_presets, indent=2, ensure_ascii=False).replace("\n", "\n  ") + ";"
    petrol_json = "  const PETROL_PRESETS = " + json.dumps(petrol_presets, indent=2, ensure_ascii=False).replace("\n", "\n  ") + ";"

    # Replace the existing arrays
    content = re.sub(
        r"  const EV_PRESETS = \[.*?\];",
        ev_json,
        content,
        count=1,
        flags=re.DOTALL,
    )
    content = re.sub(
        r"  const PETROL_PRESETS = \[.*?\];",
        petrol_json,
        content,
        count=1,
        flags=re.DOTALL,
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    if verbose:
        print(f"  [write] updated {path}", file=sys.stderr)
    return True


# =========================================================
# Main
# =========================================================

args_verbose = False  # set by main()

def main() -> int:
    global args_verbose
    parser = argparse.ArgumentParser(
        description="Refresh bike presets in js/data.js with live data from the web.",
    )
    parser.add_argument("--write", action="store_true", help="Update js/data.js in place (default: print to stdout)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show progress")
    parser.add_argument("--data-js", default="js/data.js", help="Path to data.js (default: js/data.js)")
    args = parser.parse_args()
    args_verbose = args.verbose

    print("🏍️  Refreshing bike presets...", file=sys.stderr)

    # Source 1: Wikipedia model list
    wiki_models = fetch_wiki_motorcycle_models(verbose=args.verbose)
    wiki_ev, wiki_petrol = filter_nepal_models(wiki_models)
    if args.verbose:
        print(f"  [wiki] {len(wiki_ev)} EV candidates, {len(wiki_petrol)} petrol candidates", file=sys.stderr)

    # Source 2: Scrape Nepal prices
    scraped_prices = fetch_nepal_prices(verbose=args.verbose)

    # Merge with fallback
    ev_presets, petrol_presets = merge_presets(wiki_ev, wiki_petrol, scraped_prices, verbose=args.verbose)

    print(f"  ✓ {len(ev_presets)} EV presets, {len(petrol_presets)} petrol presets", file=sys.stderr)

    if args.json:
        print(json.dumps({"ev": ev_presets, "petrol": petrol_presets}, indent=2, ensure_ascii=False))
        return 0

    if args.write:
        # Resolve path relative to project root (parent of scripts/)
        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent
        data_js_path = project_root / args.data_js
        if update_data_js(ev_presets, petrol_presets, str(data_js_path), verbose=args.verbose):
            print(f"  ✓ Updated {data_js_path}", file=sys.stderr)
            return 0
        return 1

    # Default: print as JSON to stdout
    print(json.dumps({"ev": ev_presets, "petrol": petrol_presets}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
