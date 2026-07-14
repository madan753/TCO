# Bike TCO Compare — Python Scripts

A small toolkit of robust Python utility scripts for the Bike TCO Compare project.
All scripts are **stdlib-only** (Python 3.8+) — no `pip install` needed.

## Files

```
scripts/
├── calc.py        ← Python mirror of the TCO calculator (CLI + library)
├── serve.py       ← Dev server with hot reload + QR code + browser auto-open
├── validate.py    ← Project validator (HTML/CSS/JS syntax + calc parity)
├── build.py       ← Bundler + minifier + checksums + zip
└── README.md      ← this file
```

---

## 1. `calc.py` — Python TCO calculator

Pure-Python implementation of the same TCO logic that powers the web app.
Numbers match the JavaScript version to within rounding.

### Run as CLI

```bash
# List all built-in bike presets
python scripts/calc.py presets

# Compare two bikes (default usage: 20 km/day, 5 years, 6 days/week)
python scripts/calc.py compare --ev "TVS iQube ST" --petrol "Honda Activa 6G"

# Custom usage
python scripts/calc.py compare --ev tvs-iqube --petrol honda-activa-6g \
                               --km 70 --years 4 --ride-days 7

# Different currency
python scripts/calc.py compare --ev "Ather 450X (3.7 kWh)" --petrol "Suzuki Access 125" \
                               --currency NPR

# Output as JSON (pipe into other tools)
python scripts/calc.py compare --ev "TVS iQube ST" --petrol "Honda Activa 6G" --json

# Interactive mode (step-by-step prompts)
python scripts/calc.py interactive
```

### Use as a library

```python
from scripts.calc import TCOCalculator, PRESETS, CURRENCIES

calc = TCOCalculator(currency_code="INR")
result = calc.compare(
    ev="TVS iQube ST",          # preset name or id, or a Bike object
    petrol="Honda Activa 6G",
    daily_km=20, years=5, ride_days=6,
)

print(result["verdict"]["headline"])   # "Electric saves you ₹13,329 over 5 years."
print(result["savings"])               # 13329.0
print(result["breakeven_year"])        # 4.12
```

### Why a Python mirror?

- **Scripting** — batch-compare many bike pairs and dump to CSV/JSON
- **Testing** — verify the JS calculator matches expected values (see `validate.py`)
- **Server-side rendering** — generate comparison reports in a backend
- **Notebook analysis** — pull TCO numbers into pandas / Jupyter

---

## 2. `serve.py` — Robust dev server

A self-contained HTTP server for local development. Better than `python -m http.server`
because it:

- Watches files for changes and **live-reloads** the browser (no extension needed)
- **Auto-opens** your default browser on start
- **Finds a free port** automatically if 8080 is busy
- Prints a **QR code** in the terminal for testing on your phone
- Logs requests with method, status, size, and timing
- Sends correct MIME types and CORS headers
- Handles Ctrl+C gracefully

### Usage

```bash
# Default: serve ../ on port 8080, open browser, watch files
python scripts/serve.py

# Custom port
python scripts/serve.py --port 4000

# Don't auto-open the browser
python scripts/serve.py --no-open

# Print a QR code for mobile testing (requires: pip install qrcode)
python scripts/serve.py --qr

# Disable live reload
python scripts/serve.py --no-watch
```

### Live reload

The server injects a small WebSocket snippet into HTML responses. When a file
in the project changes, the server pushes a `reload` message to all connected
browsers, which then refresh automatically.

If the `websockets` package isn't installed, the server falls back to no live
reload (you'll need to refresh manually). Install with:

```bash
pip install websockets
```

---

## 3. `validate.py` — Project validator

Runs a battery of checks on the project and prints a pass/fail report.
Use it before deploying or after making big changes.

### Usage

```bash
# Run all checks (human-readable report)
python scripts/validate.py

# Output as JSON (for CI pipelines)
python scripts/validate.py --json

# Exit code only (0 = pass, 1 = fail) — quiet mode
python scripts/validate.py --quiet
```

### Checks performed

1. **Project structure** — all expected files exist
2. **HTML structure** — basic tag balance, DOCTYPE, charset
3. **CSS brace balance** — every `{` has a matching `}`
4. **JS syntax** — every `.js` file parses cleanly (uses Node if available)
5. **Calculator parity** — Python `calc.py` matches known expected values
6. **Cross-references** — every `<script src>` and `<link href>` resolves
7. **JS global exports** — each JS file exposes its expected global namespace

### Example output

```
  Bike TCO Compare — Validation Report
  ====================================================================
  ✓ PASS  Project structure
         12/12 expected files present
  ✓ PASS  HTML structure
         Tag balance OK, DOCTYPE present, charset present
  ✓ PASS  CSS brace balance
         2 CSS files checked, all balanced
  ✓ PASS  JS syntax (node --check)
         5 JS files checked via Node, all OK
  ✓ PASS  Calculator parity (Python vs known values)
         3 scenarios tested, all match
  ✓ PASS  Cross-references (local src/href)
         6 references checked, all resolve
  ✓ PASS  JS global exports
         4/4 files expose expected globals
  ====================================================================
  Result: 7/7 checks passed
```

---

## 4. `build.py` — Build / bundler

Three useful build modes plus a "do everything" command.

### Usage

```bash
# Single-file bundle (great for sharing via email, USB, etc.)
python scripts/build.py bundle
# → ../tco-bundle.html (everything inline, minified)

# Minify individual CSS/JS files (writes to ./dist/)
python scripts/build.py minify
# → ./dist/css/*.css, ./dist/js/*.js (minified copies)

# Generate SHA-256 checksums for all project files
python scripts/build.py checksums
# → ./CHECKSUMS.sha256

# Full build: minify + bundle + checksums + zip archive
python scripts/build.py all
# → ./dist/, ../tco-bundle.html, ./CHECKSUMS.sha256, ../tco-bundle.zip
```

### Why bundle?

- **Share via email / chat** — one HTML file, no folder structure to maintain
- **Embed in a Word doc or PDF** — single file is easier to attach
- **Host on a static CDN** — one file = one URL, no relative-path issues
- **Archive for the future** — zip preserves the original structure

### Minification

The minifier is conservative (regex-based, no AST rewriting) so it never breaks
your code. Typical savings:

| File             | Original | Minified | Savings |
| ---------------- | -------- | -------- | ------- |
| `css/styles.css` | ~20 KB   | ~15 KB   | ~25%    |
| `js/app.js`      | ~11 KB   | ~8 KB    | ~27%    |
| `index.html`     | ~18 KB   | ~14 KB   | ~22%    |

For production-grade minification, run the output through `esbuild` or `terser`
afterwards — but for a small project like this, the regex minifier is fine.

---

## Quick start

If you just want to **preview the app**:

```bash
cd /path/to/TCO
python scripts/serve.py
```

If you want to **verify everything works**:

```bash
python scripts/validate.py
```

If you want to **share the app as a single file**:

```bash
python scripts/build.py bundle
# email ../tco-bundle.html to your friend
```

If you want to **compare bikes from the terminal**:

```bash
python scripts/calc.py compare --ev "TVS iQube ST" --petrol "Honda Activa 6G"
```

---

## Requirements

- **Python 3.8+** (all scripts work with stdlib only)
- **Node.js** (optional — `validate.py` uses it for stricter JS syntax checking)
- **`websockets`** (optional — enables live reload in `serve.py`)
- **`qrcode`** (optional — enables `--qr` in `serve.py`)

Install all optional deps with:

```bash
pip install websockets qrcode
```
