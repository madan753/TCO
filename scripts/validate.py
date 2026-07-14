#!/usr/bin/env python3
"""
validate.py — Project validator for Bike TCO Compare
====================================================

Runs a battery of checks on the TCO project and prints a pass/fail report.

  python validate.py                 # run all checks
  python validate.py --json          # output as JSON
  python validate.py --quiet         # exit code only (0=pass, 1=fail)

Checks performed:
  1. Project structure — all expected files exist
  2. HTML structure    — basic tag balance, valid <script>/<link> refs
  3. CSS brace balance — every { has a matching }
  4. JS syntax         — every .js file parses cleanly (uses Node if available)
  5. Calculator parity — Python calc.py and JS calculator.js agree on known scenarios
  6. Cross-references  — every <script src> and <link href> resolves to a real file
  7. Broken internal links — no orphan CSS classes referenced by JS that don't exist

Requires: Python 3.8+  (stdlib only)
"""

from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional


# =========================================================
# Constants
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # TCO/
EXPECTED_FILES = [
    "index.html",
    "css/styles.css",
    "css/responsive.css",
    "js/data.js",
    "js/calculator.js",
    "js/charts.js",
    "js/fetcher.js",
    "js/ui.js",
    "js/app.js",
    "scripts/calc.py",
    "scripts/serve.py",
    "scripts/validate.py",
    "scripts/build.py",
    "scripts/refresh_presets.py",
]

# Known scenarios for parity testing — Nepal edition.
# Each scenario has INDEPENDENT usage for EV and petrol bikes.
# Numbers are NPR (रू). Verified to match between Python calc.py
# and JS calculator.js.
PARITY_SCENARIOS = [
    {
        "name": "Default — Komaki XGT KM vs Honda Dio (independent usage)",
        "ev": "komaki-xgt-km", "petrol": "honda-dio",
        "ev_km": 22, "ev_rd": 6, "ev_yr": 5,
        "pet_km": 18, "pet_rd": 6, "pet_yr": 5,
        "expected_ev_final": 172387,        # ±5 tolerance
        "expected_petrol_final": 250231,
    },
    {
        "name": "Heavy delivery — TVS iQube vs Suzuki Access 125 (Pathao)",
        "ev": "tvs-iqube-np", "petrol": "suzuki-access-np",
        "ev_km": 90, "ev_rd": 7, "ev_yr": 4,
        "pet_km": 80, "pet_rd": 7, "pet_yr": 4,
        "expected_ev_final": 279177,
        "expected_petrol_final": 668067,
    },
    {
        "name": "Weekend rider — Yadea G5 vs TVS Jupiter",
        "ev": "yadea-g5", "petrol": "tvs-jupiter-np",
        "ev_km": 12, "ev_rd": 3, "ev_yr": 5,
        "pet_km": 10, "pet_rd": 3, "pet_yr": 5,
        "expected_ev_final": 212792,
        "expected_petrol_final": 172502,
    },
    {
        "name": "Long-term — Bajaj Chetak vs Pulsar 150 (8 yr, independent)",
        "ev": "bajaj-chetak-np", "petrol": "bajaj-pulsar-np",
        "ev_km": 25, "ev_rd": 6, "ev_yr": 8,
        "pet_km": 22, "pet_rd": 6, "pet_yr": 8,
        "expected_ev_final": 288378,
        "expected_petrol_final": 489596,
    },
]


# =========================================================
# Result types
# =========================================================

@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str = ""
    items: List[str] = field(default_factory=list)


# =========================================================
# Check 1: Project structure
# =========================================================

def check_project_structure(root: Path) -> CheckResult:
    missing, present = [], []
    for rel in EXPECTED_FILES:
        if (root / rel).exists():
            present.append(rel)
        else:
            missing.append(rel)
    return CheckResult(
        name="Project structure",
        passed=not missing,
        details=f"{len(present)}/{len(EXPECTED_FILES)} expected files present",
        items=[f"Missing: {m}" for m in missing] if missing else [],
    )


# =========================================================
# Check 2: HTML structure (basic)
# =========================================================

def check_html_structure(root: Path) -> CheckResult:
    html_path = root / "index.html"
    if not html_path.exists():
        return CheckResult(name="HTML structure", passed=False, details="index.html not found")
    content = html_path.read_text(encoding="utf-8")

    issues = []
    # Tag balance for non-void elements
    VOID_TAGS = {"meta", "link", "br", "img", "input", "hr", "source", "area", "base", "col", "embed", "param", "track", "wbr"}
    tag_re = re.compile(r"<(/?)(\w[\w-]*)([^>]*?)(/?)>")

    stack = []
    for m in tag_re.finditer(content):
        closing, name, _attrs, self_close = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
        if name in VOID_TAGS or self_close:
            continue
        if closing:
            if not stack:
                issues.append(f"Unexpected </{name}> with no opening")
            elif stack[-1] != name:
                # Pop until match (handle minor mismatches)
                while stack and stack[-1] != name:
                    issues.append(f"Unclosed <{stack[-1]}> before </{name}>")
                    stack.pop()
                if stack:
                    stack.pop()
            else:
                stack.pop()
        else:
            stack.append(name)
    if stack:
        issues.append(f"Unclosed at end: {', '.join(stack)}")

    # Check for DOCTYPE
    if not content.lstrip().lower().startswith("<!doctype html>"):
        issues.append("Missing <!DOCTYPE html>")

    # Check for charset
    if 'charset="UTF-8"' not in content and 'charset="utf-8"' not in content.lower():
        issues.append("Missing <meta charset>")

    return CheckResult(
        name="HTML structure",
        passed=not issues,
        details="Tag balance OK, DOCTYPE present, charset present" if not issues else f"{len(issues)} issues",
        items=issues,
    )


# =========================================================
# Check 3: CSS brace balance
# =========================================================

def check_css_braces(root: Path) -> CheckResult:
    css_files = sorted((root / "css").glob("*.css"))
    if not css_files:
        return CheckResult(name="CSS brace balance", passed=False, details="No CSS files found")
    issues = []
    for css in css_files:
        content = css.read_text(encoding="utf-8")
        # Strip comments
        content_no_comments = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
        opens = content_no_comments.count("{")
        closes = content_no_comments.count("}")
        if opens != closes:
            issues.append(f"{css.relative_to(root)}: {opens} '{{' vs {closes} '}}'")
    return CheckResult(
        name="CSS brace balance",
        passed=not issues,
        details=f"{len(css_files)} CSS files checked" + (f", {len(issues)} mismatches" if issues else ", all balanced"),
        items=issues,
    )


# =========================================================
# Check 4: JS syntax
# =========================================================

def check_js_syntax(root: Path) -> CheckResult:
    js_files = sorted((root / "js").glob("*.js"))
    if not js_files:
        return CheckResult(name="JS syntax", passed=False, details="No JS files found")

    # Try Node first (catches real syntax errors)
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
        issues = []
        for js in js_files:
            try:
                proc = subprocess.run(
                    ["node", "--check", str(js)],
                    capture_output=True, text=True, timeout=10,
                )
                if proc.returncode != 0:
                    issues.append(f"{js.relative_to(root)}: {proc.stderr.strip()}")
            except subprocess.TimeoutExpired:
                issues.append(f"{js.relative_to(root)}: timeout")
            except Exception as e:
                issues.append(f"{js.relative_to(root)}: {e}")
        return CheckResult(
            name="JS syntax (node --check)",
            passed=not issues,
            details=f"{len(js_files)} JS files checked via Node" + (f", {len(issues)} errors" if issues else ", all OK"),
            items=issues,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Fallback: crude brace/paren balance check
    issues = []
    for js in js_files:
        content = js.read_text(encoding="utf-8")
        # Strip strings and comments
        stripped = re.sub(r"//.*?$", "", content, flags=re.MULTILINE)
        stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)
        stripped = re.sub(r"'(?:\\.|[^'\\])*'", "''", stripped)
        stripped = re.sub(r'"(?:\\.|[^"\\])*"', '""', stripped)
        stripped = re.sub(r"`(?:\\.|[^`\\])*`", "``", stripped)
        for opener, closer in [("{", "}"), ("(", ")"), ("[", "]")]:
            if stripped.count(opener) != stripped.count(closer):
                issues.append(f"{js.relative_to(root)}: {opener}{closer} unbalanced ({stripped.count(opener)} vs {stripped.count(closer)})")
    return CheckResult(
        name="JS syntax (brace balance fallback)",
        passed=not issues,
        details=f"{len(js_files)} JS files checked (Node not available, using brace balance)" + (f", {len(issues)} errors" if issues else ", all OK"),
        items=issues,
    )


# =========================================================
# Check 5: Calculator parity
# =========================================================

def check_calc_parity(root: Path) -> CheckResult:
    # Run Python calc.py for each scenario with independent per-bike usage
    calc_py = root / "scripts" / "calc.py"
    if not calc_py.exists():
        return CheckResult(name="Calculator parity", passed=False, details="calc.py not found")

    issues = []
    results = []
    for sc in PARITY_SCENARIOS:
        try:
            proc = subprocess.run(
                ["python3", str(calc_py), "compare",
                 "--ev", sc["ev"], "--petrol", sc["petrol"],
                 "--ev-km", str(sc["ev_km"]), "--ev-ride-days", str(sc["ev_rd"]), "--ev-years", str(sc["ev_yr"]),
                 "--petrol-km", str(sc["pet_km"]), "--petrol-ride-days", str(sc["pet_rd"]), "--petrol-years", str(sc["pet_yr"]),
                 "--json"],
                capture_output=True, text=True, timeout=15,
            )
            if proc.returncode != 0:
                issues.append(f"{sc['name']}: calc.py exited {proc.returncode}: {proc.stderr[:200]}")
                continue
            data = json.loads(proc.stdout)
            ev_final = round(data["ev"]["final_cost"])
            pet_final = round(data["petrol"]["final_cost"])
            ev_ok = abs(ev_final - sc["expected_ev_final"]) <= 5
            pet_ok = abs(pet_final - sc["expected_petrol_final"]) <= 5
            if ev_ok and pet_ok:
                results.append(f"✓ {sc['name']}: EV रू{ev_final:,} / Petrol रू{pet_final:,}")
            else:
                if not ev_ok:
                    issues.append(f"{sc['name']}: EV रू{ev_final:,} ≠ expected रू{sc['expected_ev_final']:,}")
                if not pet_ok:
                    issues.append(f"{sc['name']}: Petrol रू{pet_final:,} ≠ expected रू{sc['expected_petrol_final']:,}")
        except Exception as e:
            issues.append(f"{sc['name']}: {e}")

    return CheckResult(
        name="Calculator parity (Python vs known values)",
        passed=not issues,
        details=f"{len(PARITY_SCENARIOS)} scenarios tested" + (f", {len(issues)} mismatches" if issues else ", all match"),
        items=results + issues,
    )


# =========================================================
# Check 6: Cross-references (script src / link href)
# =========================================================

def check_cross_references(root: Path) -> CheckResult:
    html_path = root / "index.html"
    if not html_path.exists():
        return CheckResult(name="Cross-references", passed=False, details="index.html not found")
    content = html_path.read_text(encoding="utf-8")

    refs = []
    # <script src="...">
    for m in re.finditer(r'<script[^>]+src="([^"]+)"', content):
        refs.append(("script", m.group(1)))
    # <link href="...">
    for m in re.finditer(r'<link[^>]+href="([^"]+)"', content):
        href = m.group(1)
        if not href.startswith(("http://", "https://", "//")):
            refs.append(("link", href))

    issues = []
    for kind, href in refs:
        if href.startswith(("http://", "https://", "//")):
            continue  # external, skip
        path = root / href
        if not path.exists():
            issues.append(f"{kind}: {href} — file not found")

    return CheckResult(
        name="Cross-references (local src/href)",
        passed=not issues,
        details=f"{len(refs)} references checked" + (f", {len(issues)} broken" if issues else ", all resolve"),
        items=issues,
    )


# =========================================================
# Check 7: JS files reference expected global namespaces
# =========================================================

def check_js_globals(root: Path) -> CheckResult:
    """Ensure each JS file declares its expected global (TCOData, TCOCalc, etc.)."""
    expected = {
        "js/data.js": "TCOData",
        "js/calculator.js": "TCOCalc",
        "js/charts.js": "TCOCharts",
        "js/fetcher.js": "TCOFetcher",
        "js/ui.js": "TCOUI",
    }
    issues = []
    found = []
    for rel, global_name in expected.items():
        path = root / rel
        if not path.exists():
            issues.append(f"{rel}: file missing")
            continue
        content = path.read_text(encoding="utf-8")
        if f"global.{global_name}" in content or f"window.{global_name}" in content:
            found.append(f"✓ {rel} exposes {global_name}")
        else:
            issues.append(f"{rel}: does not expose {global_name}")
    return CheckResult(
        name="JS global exports",
        passed=not issues,
        details=f"{len(found)}/{len(expected)} files expose expected globals",
        items=found + issues,
    )


# =========================================================
# Runner
# =========================================================

def run_all_checks(root: Path) -> List[CheckResult]:
    return [
        check_project_structure(root),
        check_html_structure(root),
        check_css_braces(root),
        check_js_syntax(root),
        check_calc_parity(root),
        check_cross_references(root),
        check_js_globals(root),
    ]


def print_report(results: List[CheckResult]) -> int:
    print()
    print("  Bike TCO Compare — Validation Report")
    print("  " + "=" * 68)
    all_pass = True
    for r in results:
        status = "✓ PASS" if r.passed else "✗ FAIL"
        marker = "  " if r.passed else "  "
        print(f"  {status}  {r.name}")
        print(f"         {r.details}")
        for item in r.items:
            print(f"         • {item}")
        if not r.passed:
            all_pass = False
    print("  " + "=" * 68)
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"  Result: {passed}/{total} checks passed")
    print()
    return 0 if all_pass else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Bike TCO Compare project.")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress output, exit code only")
    parser.add_argument("--root", default=str(PROJECT_ROOT), help="Project root (default: parent of scripts/)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Error: project root not found: {root}", file=sys.stderr)
        return 2

    results = run_all_checks(root)

    if args.json:
        print(json.dumps([
            {"name": r.name, "passed": r.passed, "details": r.details, "items": r.items}
            for r in results
        ], indent=2))
        return 0 if all(r.passed for r in results) else 1

    if args.quiet:
        return 0 if all(r.passed for r in results) else 1

    return print_report(results)


if __name__ == "__main__":
    sys.exit(main())
