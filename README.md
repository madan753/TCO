# Bike TCO Compare — Nepal Edition

A clean, user-friendly **Total Cost of Ownership** comparison tool for electric vs petrol bikes, built specifically for **Nepal** riders. Every cost is in your hands — set independent usage patterns for each bike, see the breakeven point, and get a clear verdict in plain language.

![Bike TCO Compare](https://img.shields.io/badge/Nepal-Edition-DC143C) ![No build step](https://img.shields.io/badge/build-zero--dependency-success) ![License](https://img.shields.io/badge/license-MIT-blue)

---

## Why this exists

Sticker price is just the start. This tool adds **fuel, electricity, service, insurance, bluebook renewal, and resale** to show what you'll *actually* spend over the years — and tells you in plain English which one saves you money.

Most comparison tools assume you ride an EV and a petrol bike the same way. **You don't.** EV is so cheap per km that owners ride more; petrol owners often cut back when fuel is expensive. This tool gives each bike its own usage profile so the comparison reflects *your* real life.

---

## Features

### For the rider
- **Independent usage per bike** — different daily km, ride days, and ownership years for EV vs petrol
- **Plain-English verdict** — "Electric saves you रू77,843 over 5 years. EV breaks even at year 4.1…"
- **6 KPI cards** — total cost, per-km cost (for fair comparison), savings, breakeven
- **Sensitivity analysis** — see how your verdict changes if fuel or electricity prices move ±10% to ±50%
- **Year-by-year table** — cumulative cost at end of each year, with resale drop clearly marked in the final row
- **Cumulative cost chart** — lines RISE during ownership, then show a sharp DASHED DROP at the end when resale is applied (matches reality). Hover for exact values.
- **Cost breakdown bars** — purchase, running, service, insurance, bluebook, resale per bike
- **Currency switch** — NPR (default), INR, USD with live conversion of EVERY field (including unit labels and the defaults banner)
- **Refresh prices from web** — fetch latest bike models & prices from Wikipedia + CORS-proxied scrape, with graceful fallback to embedded presets
- **Quick-start templates** — City Commuter (KTM), Pathao/Delivery, Weekend Rider, Long-Term Owner
- **Print/PDF** — save your comparison as a single PDF
- **Mobile-responsive** — works on your phone

### For Nepal
- Default currency: **NPR (रू)**
- Electricity: **रू9.8/kWh** (Nepal Electricity Authority domestic tier)
- Petrol: **रू175/litre** (2024 average)
- Bluebook renewal: **रू2,500/yr**
- Insurance: **रू2,800/yr** (third-party + basic own-damage)
- **Real Nepal bike presets** with on-road prices from Nepali dealers:
  - **EVs**: Komaki XGT KM, Yadea G5, TVS iQube Electric, Bajaj Chetak Electric, NIU NQi Sport, Yatri Project Zero
  - **Petrol**: Honda Dio, TVS Jupiter, Honda Activa 6G, Suzuki Access 125, Honda CB Shine 125, Bajaj Pulsar 150, Yamaha FZ-S V3

### For developers
- **No build step** — pure HTML, CSS, vanilla JavaScript. Open `index.html` in any browser.
- **No external dependencies** — only Google Fonts loaded from CDN. Works offline if you self-host fonts.
- **Clean separation** — HTML / CSS / JS in separate folders, each file < 400 lines.
- **Python toolkit** included for CLI use, validation, and bundling.

---

## Quick start

### Option A — Just open it
```bash
# Clone or download, then:
cd TCO
open index.html        # macOS
xdg-open index.html    # Linux
start index.html       # Windows
```

### Option B — Use the dev server (recommended)
```bash
cd TCO
python3 scripts/serve.py
# → opens http://localhost:8080 with live reload
```

### Option C — Use the CLI to compare from terminal
```bash
cd TCO
python3 scripts/calc.py presets                                              # list bikes
python3 scripts/calc.py compare --ev "Komaki XGT KM" --petrol "Honda Dio"   # default usage
python3 scripts/calc.py compare --ev komaki-xgt-km --petrol honda-dio \
                                --ev-km 30 --ev-years 6 \
                                --petrol-km 18 --petrol-years 5              # independent usage
```

### Option D — Refresh bike presets with latest web data
```bash
# In the browser: click "Refresh prices" button (top-right) — fetches live data
# Or from the terminal:
python3 scripts/refresh_presets.py --write   # updates js/data.js with latest models & prices
```

---

## File structure

```
TCO/
├── index.html              ← main page (semantic HTML)
├── css/
│   ├── styles.css          ← main styles (light, friendly theme)
│   └── responsive.css      ← breakpoints + print styles
├── js/
│   ├── data.js             ← Nepal bike presets, currencies, templates
│   ├── calculator.js       ← TCO math (per-bike usage, sensitivity, breakeven, resale-at-end)
│   ├── charts.js           ← canvas line chart with tooltip + resale-drop segments
│   ├── fetcher.js          ← live bike data fetcher (Wikipedia + CORS proxy + fallback)
│   ├── ui.js               ← verdict, KPIs, breakdown bars, tables
│   └── app.js              ← state, event binding, currency symbols, init
├── scripts/
│   ├── calc.py             ← Python CLI mirror of the calculator
│   ├── serve.py            ← dev server with live reload + QR
│   ├── validate.py         ← project validator (7 checks)
│   ├── build.py            ← bundler + minifier + checksums
│   ├── refresh_presets.py  ← scraper: fetch latest bike models & prices → update data.js
│   └── README.md           ← scripts documentation
├── README.md               ← this file
├── LICENSE                 ← MIT
└── .gitignore
```

---

## How the math works

### Total Cost of Ownership (TCO)

```
Net cost = purchase price
         + running cost (fuel or electricity)
         + service cost
         + insurance
         + bluebook renewal
         − resale (if included)
```

### Resale timing — important

Resale is applied as a **single sharp drop at the END of ownership**, not as a gradual cumulative credit. This matches reality: you keep paying fuel/service/insurance while you own the bike, and only recover the resale value on the day you sell it.

- **During years 1 to N−1**: cumulative cost keeps RISING (no resale credit)
- **At end of year N**: cost drops by the resale amount
- **Chart**: lines rise monotonically, then a dashed vertical segment shows the resale drop
- **Year table**: only the final-year row shows a "−रूXX,XXX resale" badge

### Realistic degradation

- **EV battery**: range drops ~5% per 10,000 km → electricity use slowly rises
- **Petrol engine**: mileage drops ~5% per 15,000 km → fuel use slowly rises
- **Service cost**: drifts up ~2% per 10,000 km as parts age

### Per-km cost

When EV and petrol have different usage patterns (different km, different years), total cost isn't a fair comparison. The **per-km cost** KPI divides total cost by total distance, so you can compare apples to apples.

### Breakeven point

The day when EV cumulative cost crosses below petrol cumulative cost. Found via numerical sampling (240 samples + linear interpolation), so it correctly handles non-linear degradation and different ownership periods.

### Sensitivity analysis

The verdict can flip when fuel or electricity prices change. The sensitivity table runs 8 scenarios:
- Fuel +10%, +25%, +50%
- Electricity +10%, +25%, +50%
- Both +25%
- Both −10%

For each scenario, you see the new EV cost, petrol cost, savings, and winner.

---

## Nepal default assumptions

All defaults are editable in step 5 of the UI.

| Item                  | Default (NPR)        | Source                                  |
| --------------------- | -------------------- | --------------------------------------- |
| Electricity rate      | रू9.8 / kWh          | Nepal Electricity Authority domestic    |
| Petrol price          | रू175 / litre        | 2024 Nepal average                      |
| Bluebook renewal      | रू2,500 / year       | Standard for sub-250cc bikes            |
| Insurance (3rd party) | रू2,800 / year       | Mandatory + basic own-damage            |
| EV resale (5 yr)      | ~40% of price        | Typical battery-scooter depreciation    |
| Petrol resale (5 yr)  | ~55% of price        | Typical scooter depreciation            |

---

## Python toolkit

All scripts are **stdlib-only** (Python 3.8+) — no `pip install` needed.

### `calc.py` — CLI calculator

```bash
# List presets
python3 scripts/calc.py presets

# Compare with defaults
python3 scripts/calc.py compare --ev "TVS iQube Electric" --petrol "Honda Activa 6G"

# Independent usage per bike
python3 scripts/calc.py compare --ev tvs-iqube-np --petrol honda-activa-np \
                                --ev-km 30 --ev-years 6 \
                                --petrol-km 18 --petrol-years 5

# JSON output (pipe into other tools)
python3 scripts/calc.py compare --ev "Komaki XGT KM" --petrol "Honda Dio" --json

# Interactive mode
python3 scripts/calc.py interactive
```

### `serve.py` — Dev server

```bash
python3 scripts/serve.py                    # serve on port 8080 with live reload
python3 scripts/serve.py --port 4000        # custom port
python3 scripts/serve.py --qr               # print QR code for mobile testing
python3 scripts/serve.py --no-watch         # disable live reload
```

### `validate.py` — Project validator

```bash
python3 scripts/validate.py                 # run 7 checks (HTML, CSS, JS, calc parity, etc.)
python3 scripts/validate.py --json          # JSON output for CI
python3 scripts/validate.py --quiet         # exit code only (0=pass, 1=fail)
```

### `build.py` — Bundler

```bash
python3 scripts/build.py bundle             # single-file HTML (share via email)
python3 scripts/build.py minify             # minified copies to dist/
python3 scripts/build.py checksums          # SHA-256 checksums
python3 scripts/build.py all                # everything + zip
```

### `refresh_presets.py` — Live data scraper

Fetches the latest bike models & prices from the web and updates `js/data.js`:

```bash
python3 scripts/refresh_presets.py          # print fetched presets as JSON
python3 scripts/refresh_presets.py --write  # update js/data.js in place
python3 scripts/refresh_presets.py --verbose # show source-by-source progress
```

**Multi-source fallback strategy:**
1. Wikipedia REST API → fetches list of motorcycle models (CORS-enabled, no key)
2. CORS-proxied scrape of Nepali listing pages → tries to find current NPR prices
3. Embedded fallback presets → always available if the above fail

The script MERGES results: new Wikipedia models are prepended to the dropdown, but the fallback presets are always kept.

See [`scripts/README.md`](scripts/README.md) for full documentation.

---

## Use as a library

The Python calculator is importable:

```python
import sys
sys.path.insert(0, 'scripts')
from calc import TCOCalculator

calc = TCOCalculator(currency_code="NPR")
result = calc.compare(
    ev="Komaki XGT KM",
    petrol="Honda Dio",
    ev_daily_km=30, ev_years=6,
    petrol_daily_km=18, petrol_years=5,
)

print(result["verdict"]["headline"])   # "Electric saves you रू..."
print(result["savings"])               # 16427.0
print(result["ev_per_km"])             # 1.61
print(result["sensitivity"]["baseline"])
```

---

## Browser support

- Modern browsers (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)
- Mobile Safari iOS 14+
- Chrome Android 90+
- No IE support (uses ES6+, `??`, optional chaining)

---

## Contributing

1. Fork the repo
2. Make your changes
3. Run `python3 scripts/validate.py` — all 7 checks must pass
4. Submit a pull request

### Adding a new bike preset

Edit `js/data.js` and `scripts/calc.py` (keep them in sync — the validator checks parity). Add an entry to `EV_PRESETS` or `PETROL_PRESETS`:

```javascript
// js/data.js
{
  id: 'my-new-bike',
  name: 'My New Bike',
  price: 250000,           // NPR on-road
  range: 90,               // EV only: km per charge
  battery: 2.5,            // EV only: kWh
  mileage: 50,             // Petrol only: km/litre
  service: 2000,           // annual service cost
  insurance: 3000,         // annual insurance
  tax: 2500,               // annual bluebook
  resalePct: 0.40          // % of price recovered at end
}
```

Then add the same entry to `EV_PRESETS` or `PETROL_PRESETS` in `scripts/calc.py`.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgements

- Bike preset prices sourced from Nepali dealer listings, 2024
- Nepal Electricity Authority tariff for electricity rate baseline
- Built with [Inter](https://rsms.me/inter/) and [JetBrains Mono](https://www.jetbrains.com/lp/mono/) fonts
- Inspired by the lack of a honest, Nepal-specific EV vs petrol comparison tool

---

## Disclaimer

All numbers are **estimates** based on typical 2024 Nepal prices. Always cross-check with your dealer quote before making a purchase decision. Battery replacement, accidents, theft, and major repairs are not included — add them to the annual service cost if you want to model those scenarios.
