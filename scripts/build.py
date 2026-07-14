#!/usr/bin/env python3
"""
build.py — Build / bundler for Bike TCO Compare
================================================

Three useful build modes:

  1. Bundle to single portable HTML file:
       python build.py bundle
       → writes ../tco-bundle.html (everything inline, share-friendly)

  2. Minify individual CSS / JS files in place (writes to ../dist/):
       python build.py minify
       → writes ../dist/css/*.css and ../dist/js/*.js (minified copies)

  3. Generate checksums for all project files:
       python build.py checksums
       → writes ../CHECKSUMS.sha256

  4. Full build (bundle + minify + checksums + zip):
       python build.py all
       → ../dist/, ../tco-bundle.html, ../tco-bundle.zip

Requires: Python 3.8+  (stdlib only — uses zipfile, hashlib, re, html.parser)
"""

from __future__ import annotations
import argparse
import hashlib
import re
import sys
import zipfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Tuple, Optional


# =========================================================
# Constants
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # TCO/


# =========================================================
# HTML parser to extract <script> and <link> references
# =========================================================

class HTMLAssetExtractor(HTMLParser):
    """Extracts local <script src> and <link href> references from HTML."""

    def __init__(self):
        super().__init__()
        self.scripts: List[str] = []   # src paths
        self.styles: List[str] = []    # href paths
        self.head_scripts: List[str] = []
        self._in_head = False

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        if tag == "head":
            self._in_head = True
        elif tag == "script" and "src" in attrs_d:
            src = attrs_d["src"]
            if not src.startswith(("http://", "https://", "//")):
                self.scripts.append(src)
                if self._in_head:
                    self.head_scripts.append(src)
        elif tag == "link" and "href" in attrs_d:
            href = attrs_d["href"]
            if not href.startswith(("http://", "https://", "//")):
                self.styles.append(href)

    def handle_endtag(self, tag):
        if tag == "head":
            self._in_head = False


# =========================================================
# Minifiers (regex-based — no external deps)
# =========================================================

def minify_css(css: str) -> str:
    """Aggressive but safe CSS minifier."""
    # Remove comments
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    # Remove leading/trailing whitespace per line
    css = "\n".join(line.strip() for line in css.splitlines())
    # Collapse multiple whitespace
    css = re.sub(r"\s+", " ", css)
    # Remove spaces around { } : ; ,
    css = re.sub(r"\s*([{}:;,>])\s*", r"\1", css)
    # Remove trailing semicolon before }
    css = re.sub(r";}", "}", css)
    # Remove last semicolon
    css = css.rstrip(";")
    return css.strip()


def minify_js(js: str) -> str:
    """Conservative JS minifier — strips comments + leading whitespace per line.
    Does NOT rename variables or refactor (preserves correctness)."""
    # Remove /* */ block comments
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.DOTALL)
    # Remove // line comments (careful not to break URLs like http://)
    # Match // only when not preceded by : (so we don't break http://)
    out_lines = []
    for line in js.splitlines():
        # Find // that isn't part of a URL
        i = 0
        result = []
        while i < len(line):
            if line[i:i+2] == "//" and (i == 0 or line[i-1] != ":"):
                # Comment — skip rest of line
                break
            result.append(line[i])
            i += 1
        stripped = "".join(result).rstrip()
        out_lines.append(stripped)
    js = "\n".join(out_lines)
    # Collapse multiple blank lines
    js = re.sub(r"\n{3,}", "\n\n", js)
    # Strip leading whitespace per line (careful with template literals — leave those alone)
    # Conservative: don't strip inside backtick strings
    return js.strip()


def minify_html(html: str) -> str:
    """Conservative HTML minifier — collapses whitespace between tags."""
    # Remove HTML comments (but keep IE conditionals)
    html = re.sub(r"<!--(?!\[if).*?-->", "", html, flags=re.DOTALL)
    # Collapse whitespace between tags
    html = re.sub(r">\s+<", ">\n<", html)
    # Collapse runs of whitespace
    html = re.sub(r"[ \t]+", " ", html)
    return html.strip()


# =========================================================
# Bundle to single HTML
# =========================================================

def build_bundle(root: Path, output: Path, minify: bool = True) -> Path:
    """Inline all <script src> and <link href> into a single HTML file."""
    html_path = root / "index.html"
    if not html_path.exists():
        raise FileNotFoundError(f"index.html not found in {root}")

    html = html_path.read_text(encoding="utf-8")
    extractor = HTMLAssetExtractor()
    extractor.feed(html)

    # Inline CSS
    for href in extractor.styles:
        css_path = root / href
        if not css_path.exists():
            sys.stderr.write(f"[bundle] warning: CSS not found: {href}\n")
            continue
        css = css_path.read_text(encoding="utf-8")
        if minify:
            css = minify_css(css)
        inline_tag = f'<style>\n/* Inlined from {href} */\n{css}\n</style>'
        # Replace the <link> tag with inline <style>
        # Match the exact href to avoid replacing wrong links
        link_pattern = re.compile(
            r'<link[^>]*href="' + re.escape(href) + r'"[^>]*/?>',
            re.IGNORECASE,
        )
        html = link_pattern.sub(inline_tag, html, count=1)

    # Inline JS (preserve order)
    for src in extractor.scripts:
        js_path = root / src
        if not js_path.exists():
            sys.stderr.write(f"[bundle] warning: JS not found: {src}\n")
            continue
        js = js_path.read_text(encoding="utf-8")
        if minify:
            js = minify_js(js)
        inline_tag = f'<script>\n// Inlined from {src}\n{js}\n</script>'
        # Replace the <script src="..."> tag
        script_pattern = re.compile(
            r'<script[^>]*src="' + re.escape(src) + r'"[^>]*>\s*</script>',
            re.IGNORECASE,
        )
        html = script_pattern.sub(inline_tag, html, count=1)

    if minify:
        html = minify_html(html)

    # Add a build banner comment
    banner = f"<!-- Built: {datetime.now().isoformat(timespec='seconds')} | Single-file bundle of Bike TCO Compare -->\n"
    html = banner + html

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output


# =========================================================
# Minify to dist/
# =========================================================

def build_minify(root: Path, dist: Path) -> Path:
    """Write minified copies of CSS and JS to dist/."""
    dist.mkdir(parents=True, exist_ok=True)

    # CSS
    css_src = root / "css"
    css_dst = dist / "css"
    css_dst.mkdir(exist_ok=True)
    for css in css_src.glob("*.css"):
        content = css.read_text(encoding="utf-8")
        (css_dst / css.name).write_text(minify_css(content), encoding="utf-8")

    # JS
    js_src = root / "js"
    js_dst = dist / "js"
    js_dst.mkdir(exist_ok=True)
    for js in js_src.glob("*.js"):
        content = js.read_text(encoding="utf-8")
        (js_dst / js.name).write_text(minify_js(content), encoding="utf-8")

    # Copy index.html (minified)
    html_path = root / "index.html"
    if html_path.exists():
        (dist / "index.html").write_text(minify_html(html_path.read_text(encoding="utf-8")), encoding="utf-8")

    return dist


# =========================================================
# Checksums
# =========================================================

def write_checksums(root: Path, output: Path) -> Path:
    """Generate SHA-256 checksums for all project files."""
    lines = []
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file()
        and ".git" not in p.parts
        and "node_modules" not in p.parts
        and "dist" not in p.parts
    )
    for path in files:
        rel = path.relative_to(root)
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{h}  {rel}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


# =========================================================
# Zip archive
# =========================================================

def create_zip(root: Path, output: Path, exclude_dirs: Tuple[str, ...] = ("dist", "__pycache__")) -> Path:
    """Create a zip archive of the project."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if any(excluded in path.parts for excluded in exclude_dirs):
                continue
            if path.name.endswith((".pyc", ".pyo", ".DS_Store")):
                continue
            arcname = path.relative_to(root.parent)  # include TCO/ prefix
            zf.write(path, arcname)
    return output


# =========================================================
# Size helpers
# =========================================================

def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


# =========================================================
# Commands
# =========================================================

def cmd_bundle(args) -> int:
    root = Path(args.root).resolve()
    out = Path(args.output).resolve() if args.output else root.parent / "tco-bundle.html"
    print(f"\n  📦 Bundling {root} → {out}")
    build_bundle(root, out, minify=not args.no_minify)
    size = out.stat().st_size
    print(f"  ✓ Bundle written: {out} ({human_size(size)})\n")
    return 0


def cmd_minify(args) -> int:
    root = Path(args.root).resolve()
    dist = Path(args.output).resolve() if args.output else root / "dist"
    print(f"\n  ✂️  Minifying to {dist}")
    build_minify(root, dist)
    # Report sizes
    print(f"  ✓ Minified files written to {dist}")
    for path in sorted(dist.rglob("*")):
        if path.is_file():
            orig = root / path.relative_to(dist)
            if orig.exists():
                orig_size = orig.stat().st_size
                new_size = path.stat().st_size
                pct = (1 - new_size / orig_size) * 100 if orig_size else 0
                print(f"    {path.relative_to(dist)}: {human_size(orig_size)} → {human_size(new_size)} ({pct:.0f}% smaller)")
    print()
    return 0


def cmd_checksums(args) -> int:
    root = Path(args.root).resolve()
    out = Path(args.output).resolve() if args.output else root / "CHECKSUMS.sha256"
    print(f"\n  🔐 Generating checksums → {out}")
    write_checksums(root, out)
    count = sum(1 for line in out.read_text(encoding="utf-8").splitlines() if line.strip())
    print(f"  ✓ {count} files hashed\n")
    return 0


def cmd_all(args) -> int:
    root = Path(args.root).resolve()
    dist = root / "dist"
    bundle = root.parent / "tco-bundle.html"
    checksums = root / "CHECKSUMS.sha256"
    archive = root.parent / "tco-bundle.zip"

    print(f"\n  🚀 Full build — {root}")
    print("  " + "=" * 60)

    # 1. Minify to dist/
    print("\n  [1/4] Minifying CSS/JS/HTML → dist/ ...")
    build_minify(root, dist)
    print("  ✓ done")

    # 2. Bundle to single HTML
    print("\n  [2/4] Bundling to single HTML ...")
    build_bundle(root, bundle, minify=True)
    print(f"  ✓ {bundle.name} ({human_size(bundle.stat().st_size)})")

    # 3. Checksums
    print("\n  [3/4] Generating checksums ...")
    write_checksums(root, checksums)
    print(f"  ✓ {checksums.name}")

    # 4. Zip archive
    print("\n  [4/4] Creating zip archive ...")
    create_zip(root, archive)
    print(f"  ✓ {archive.name} ({human_size(archive.stat().st_size)})")

    print("\n  " + "=" * 60)
    print(f"  ✓ Build complete. Artifacts:")
    print(f"     {dist}/                 (minified source)")
    print(f"     {bundle}        (single-file bundle)")
    print(f"     {checksums}     (SHA-256 checksums)")
    print(f"     {archive}        (zip archive)\n")
    return 0


# =========================================================
# Main
# =========================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="build.py",
        description="Build / bundler for Bike TCO Compare.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python build.py bundle                 # single-file HTML
  python build.py minify                 # minify to dist/
  python build.py checksums              # SHA-256 file
  python build.py all                    # everything + zip
""",
    )
    parser.add_argument("--root", default=str(PROJECT_ROOT), help="Project root (default: parent of scripts/)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_b = sub.add_parser("bundle", help="Inline all CSS/JS into a single HTML file")
    p_b.add_argument("--output", help="Output path (default: ../tco-bundle.html)")
    p_b.add_argument("--no-minify", action="store_true", help="Skip minification")
    p_b.set_defaults(func=cmd_bundle)

    p_m = sub.add_parser("minify", help="Write minified copies to dist/")
    p_m.add_argument("--output", help="Output dir (default: ./dist)")
    p_m.set_defaults(func=cmd_minify)

    p_c = sub.add_parser("checksums", help="Generate SHA-256 checksums")
    p_c.add_argument("--output", help="Output file (default: ./CHECKSUMS.sha256)")
    p_c.set_defaults(func=cmd_checksums)

    p_a = sub.add_parser("all", help="Full build: minify + bundle + checksums + zip")
    p_a.set_defaults(func=cmd_all)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
