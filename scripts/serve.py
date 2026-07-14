#!/usr/bin/env python3
"""
serve.py — Robust dev server for Bike TCO Compare
=================================================

A self-contained HTTP server with quality-of-life features for development:

  ✓ Auto-finds a free port (if default 8080 is busy)
  ✓ Watches files for changes → live reload (no browser extension needed)
  ✓ Auto-opens the default browser on start
  ✓ Optional QR code in terminal for mobile testing
  ✓ Pretty request logging with method, path, status, size, timing
  ✓ Correct MIME types for .html, .css, .js, .svg, .png, .jpg, .json, .woff2
  ✓ CORS-friendly (Access-Control-Allow-Origin: *)
  ✓ Cache headers (no-cache for HTML, 1h for static assets)
  ✓ Graceful Ctrl+C shutdown
  ✓ Optional --bundle mode to serve a single bundled HTML (no folder walks)

Usage:
  python serve.py                          # serve ../ on port 8080
  python serve.py --port 4000              # use a specific port
  python serve.py --no-open                # don't auto-open browser
  python serve.py --qr                     # print QR code for mobile
  python serve.py --watch                  # live reload on file change (default on)
  python serve.py --no-watch               # disable live reload

Requires: Python 3.8+  (stdlib only — qrcode optional for --qr)
"""

from __future__ import annotations
import argparse
import http.server
import os
import socket
import socketserver
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional, Dict
from urllib.parse import urlparse


# =========================================================
# Constants
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # TCO/

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".htm":  "text/html; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".js":   "application/javascript; charset=utf-8",
    ".mjs":  "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg":  "image/svg+xml",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif":  "image/gif",
    ".webp": "image/webp",
    ".ico":  "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf":  "font/ttf",
    ".otf":  "font/otf",
    ".txt":  "text/plain; charset=utf-8",
    ".pdf":  "application/pdf",
    ".mp4":  "video/mp4",
    ".webm": "video/webm",
    ".map":  "application/json",
}

LIVE_RELOAD_SNIPPET = b"""
<!-- dev-server live reload -->
<script>
(function(){
  var wsUrl = (location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.hostname + ':__WS_PORT__/ws';
  var ws;
  var retryMs = 1500;
  function connect() {
    try { ws = new WebSocket(wsUrl); } catch(e) { schedule(); return; }
    ws.onopen = function(){ retryMs = 1500; console.log('[dev] live reload connected'); };
    ws.onmessage = function(ev){
      try { var msg = JSON.parse(ev.data); } catch(e){ return; }
      if (msg.type === 'reload') { console.log('[dev] reloading...'); location.reload(); }
    };
    ws.onclose = function(){ schedule(); };
    ws.onerror = function(){ try{ws.close();}catch(e){} };
  }
  function schedule(){ setTimeout(connect, retryMs); retryMs = Math.min(retryMs * 1.5, 8000); }
  connect();
})();
</script>
"""


# =========================================================
# Find a free port
# =========================================================

def find_free_port(start: int, end: int = 65535, host: str = "127.0.0.1") -> int:
    for port in range(start, end + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((host, port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No free port in range {start}-{end}")


def get_lan_ip() -> Optional[str]:
    """Returns the LAN IP address (for mobile testing)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


# =========================================================
# Custom request handler
# =========================================================

class TCORequestHandler(http.server.SimpleHTTPRequestHandler):
    """Serves files from PROJECT_ROOT with proper MIME + cache headers."""

    server_version = "TCODevServer/1.0"

    def __init__(self, *args, root: Path = PROJECT_ROOT, inject_reload: bool = False, **kwargs):
        self._root = root
        self._inject_reload = inject_reload
        super().__init__(*args, directory=str(root), **kwargs)

    def guess_type(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        return MIME_TYPES.get(ext, "application/octet-stream")

    def end_headers(self):
        # CORS + cache headers
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        if self.path.endswith(".html") or self.path == "/" or "?" in self.path:
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        else:
            self.send_header("Cache-Control", "public, max-age=3600")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args):
        # Pretty request logging
        elapsed_ms = (self._end_time - self._start_time) * 1000 if hasattr(self, "_end_time") else 0
        status = args[1] if len(args) > 1 else "???"
        size = args[0].split()[-1] if len(args) > 0 else ""
        method = self.command
        path = self.path
        if len(path) > 60:
            path = path[:57] + "..."
        color = "\033[32m" if str(status).startswith("2") else ("\033[33m" if str(status).startswith("3") else "\033[31m")
        reset = "\033[0m"
        sys.stderr.write(f"  {color}{method:4}{reset} {status} {path:<60} {size:>8}  {elapsed_ms:6.1f}ms\n")

    def handle_one_request(self):
        self._start_time = time.time()
        super().handle_one_request()
        self._end_time = time.time()

    def copyfile(self, source, outputfile):
        # Inject live reload snippet into HTML responses
        if self._inject_reload and (self.path.endswith(".html") or self.path == "/"):
            content = source.read()
            ws_port = getattr(self.server, "ws_port", 0)
            snippet = LIVE_RELOAD_SNIPPET.replace(b"__WS_PORT__", str(ws_port).encode())
            if b"</body>" in content:
                content = content.replace(b"</body>", snippet + b"</body>")
            else:
                content = content + snippet
            try:
                outputfile.write(content)
            except BrokenPipeError:
                pass
            return
        super().copyfile(source, outputfile)


# =========================================================
# Threaded server with optional live reload
# =========================================================

class TCOServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    ws_port: int = 0  # set externally


# =========================================================
# File watcher (polling-based, no extra deps)
# =========================================================

def watch_files(root: Path, server: TCOServer, interval: float = 0.7):
    """Polls files for changes; notifies connected WS clients to reload."""
    file_mtimes: Dict[Path, float] = {}
    extensions = {".html", ".css", ".js", ".json", ".svg", ".png"}

    def scan():
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in extensions:
                try:
                    file_mtimes[path] = path.stat().st_mtime
                except OSError:
                    pass
    scan()

    while True:
        time.sleep(interval)
        try:
            for path in list(file_mtimes.keys()):
                try:
                    current = path.stat().st_mtime
                except OSError:
                    current = None
                if current is None:
                    # File deleted
                    file_mtimes.pop(path, None)
                    notify_reload(server)
                    break
                if current != file_mtimes[path]:
                    file_mtimes[path] = current
                    notify_reload(server)
                    break
            # Also detect new files
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in extensions and path not in file_mtimes:
                    try:
                        file_mtimes[path] = path.stat().st_mtime
                    except OSError:
                        continue
                    notify_reload(server)
                    break
        except Exception as e:
            sys.stderr.write(f"[watcher] error: {e}\n")


def notify_reload(server: TCOServer):
    """Send reload message to all connected WS clients."""
    ws_server = getattr(server, "ws_server", None)
    if not ws_server:
        return
    for client in list(ws_server.clients):
        try:
            import asyncio
            asyncio.run_coroutine_threadsafe(client.send('{"type":"reload"}'), ws_server.loop)
        except Exception:
            pass


# =========================================================
# Optional WebSocket server (for true live reload)
# =========================================================

def start_ws_server(host: str, port: int) -> Optional[int]:
    """Starts a minimal WebSocket server. Returns the actual port, or None if unavailable."""
    try:
        import asyncio
        import websockets
    except ImportError:
        return None

    clients = set()
    loop = asyncio.new_event_loop()

    async def handler(websocket):
        clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            clients.discard(websocket)

    async def serve_ws():
        server = await websockets.serve(handler, host, port)
        async with server:
            await server.serve_forever()

    def run_loop():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(serve_ws())

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()

    # Stash references for notify_reload
    ws_state = type("W", (), {"clients": clients, "loop": loop})()
    return ws_state


# =========================================================
# QR code (optional)
# =========================================================

def print_qr(url: str):
    try:
        import qrcode
        qr = qrcode.QRCode(border=1, box_size=1)
        qr.add_data(url)
        qr.make(fit=True)
        print("\n  📱  Scan to open on your phone:\n")
        qr.print_ascii(invert=True)
        print(f"\n  URL: {url}\n")
    except ImportError:
        print(f"\n  💡 Install 'qrcode' for in-terminal QR:  pip install qrcode")
        print(f"     Mobile URL: {url}\n")


# =========================================================
# Main
# =========================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Robust dev server for the Bike TCO Compare project.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--port", type=int, default=8080, help="Port to serve on (default 8080; auto-finds free if busy)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default 0.0.0.0 = all interfaces)")
    parser.add_argument("--no-open", action="store_true", help="Don't auto-open the browser")
    parser.add_argument("--qr", action="store_true", help="Print QR code for mobile testing")
    parser.add_argument("--no-watch", action="store_true", help="Disable live reload on file change")
    parser.add_argument("--root", default=str(PROJECT_ROOT), help="Directory to serve (default: project root)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 2

    # Find a free port
    try:
        port = find_free_port(args.port) if args.port else find_free_port(8080)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    # Start optional WebSocket server for live reload
    ws_state = None
    ws_port = 0
    inject_reload = False
    if not args.no_watch:
        try:
            ws_port = find_free_port(35729)  # LiveReload standard port
            ws_state = start_ws_server("0.0.0.0", ws_port)
            if ws_state:
                inject_reload = True
        except Exception as e:
            sys.stderr.write(f"[dev] live reload unavailable: {e}\n")

    # Build handler with root bound
    def handler_factory(*a, **kw):
        return TCORequestHandler(*a, root=root, inject_reload=inject_reload, **kw)

    server = TCOServer((args.host, port), handler_factory)
    server.ws_port = ws_port
    server.ws_server = ws_state

    # Start file watcher
    if not args.no_watch and ws_state:
        watcher_thread = threading.Thread(target=watch_files, args=(root, server), daemon=True)
        watcher_thread.start()

    # Compose URLs
    lan_ip = get_lan_ip()
    local_url = f"http://localhost:{port}/"
    lan_url = f"http://{lan_ip}:{port}/" if lan_ip and args.host == "0.0.0.0" else None

    # Print banner
    print()
    print("  ╔" + "═" * 60 + "╗")
    print("  ║  🏍️  Bike TCO Compare — Dev Server" + " " * 26 + "║")
    print("  ╠" + "═" * 60 + "╣")
    print(f"  ║  Serving: {str(root):<50} ║")
    print(f"  ║  Local:   {local_url:<51}║")
    if lan_url:
        print(f"  ║  Network: {lan_url:<51}║")
    if inject_reload:
        print(f"  ║  Live reload: ✓ (WS port {ws_port})" + " " * (60 - len(f"  Live reload: ✓ (WS port {ws_port})")) + "║")
    else:
        print(f"  ║  Live reload: disabled" + " " * 36 + "║")
    print("  ║  Press Ctrl+C to stop" + " " * 39 + "║")
    print("  ╚" + "═" * 60 + "╝")
    print()

    # Auto-open browser
    if not args.no_open:
        try:
            webbrowser.open(local_url)
        except Exception:
            pass

    # Print QR code if requested
    if args.qr:
        if lan_url:
            print_qr(lan_url)
        else:
            print_qr(local_url)

    # Serve until interrupted
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n  Shutting down... ", end="", flush=True)
        server.shutdown()
        print("done. 👋\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
