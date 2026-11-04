"""
inject-tunnel.py
----------------
Shares a running ClimateInsight app through a Cloudflare Quick Tunnel.

The Flask backend serves both the frontend and the /api routes from one
origin (http://localhost:5001 by default), and the frontend resolves its
API base from window.location — so a single tunnel exposes the whole app
and no files need to be patched.

1. Launches a cloudflared quick tunnel for the backend port.
2. Reads the generated URL from cloudflared's stderr output.
3. Prints the URL — open it to use the app.
4. Restarts the tunnel if it crashes; Ctrl+C shuts it down.

Usage:
    python scripts/inject-tunnel.py           # tunnel port 5001
    PORT=8080 python scripts/inject-tunnel.py # tunnel another port

Requires cloudflared (Apache-2.0, https://github.com/cloudflare/cloudflared).
"""

import os
import re
import signal
import subprocess
import sys
import threading
import time

PORT = int(os.getenv("PORT", "5001"))

# Matches any trycloudflare.com URL in cloudflared output
URL_RE = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")


def say(msg=""):
    """print() with immediate flush — works reliably on Windows."""
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Tunnel URL reader (runs in a daemon thread)
# ---------------------------------------------------------------------------
def read_url_from_stderr(proc: subprocess.Popen, bucket: list):
    """
    Reads cloudflared stderr line by line until a trycloudflare.com URL
    is found, then stores it in bucket[0].
    """
    for raw in proc.stderr:                            # type: ignore[union-attr]
        line = raw.decode("utf-8", errors="replace").strip()
        match = URL_RE.search(line)
        if match:
            bucket.append(match.group(0))
            return
    bucket.append(None)   # process ended without URL


def launch_tunnel(port: int):
    """Start cloudflared for port; return (proc, url_bucket)."""
    try:
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        say("ERROR: cloudflared is not installed or not on PATH.")
        sys.exit(1)
    bucket: list = []
    threading.Thread(target=read_url_from_stderr, args=(proc, bucket), daemon=True).start()
    return proc, bucket


def wait_for_url(bucket: list, timeout: int = 60):
    deadline = time.time() + timeout
    ticks = 0
    while time.time() < deadline:
        if bucket:
            return bucket[0]
        ticks += 1
        if ticks % 10 == 0:
            say("  ... still waiting for tunnel URL ...")
        time.sleep(0.3)
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
say()
say("=" * 60)
say("  Cloudflare Quick Tunnel Launcher")
say(f"  app -> http://localhost:{PORT}")
say("=" * 60)
say()
say(f"Starting cloudflared for port {PORT} ...")
proc, bucket = launch_tunnel(PORT)
say("Waiting for Cloudflare to assign a URL (up to 60 s) ...")

url = wait_for_url(bucket)
if not url:
    say()
    say("ERROR: Could not get a tunnel URL.")
    say(f"Make sure the app is running:  cd backend && python app.py  (port {PORT})")
    proc.terminate()
    sys.exit(1)

say()
say("=" * 60)
say("  TUNNEL IS LIVE")
say("-" * 60)
say(f"  ClimateInsight  ->  {url}")
say("-" * 60)
say("  Anyone with this link can use the app while this runs.")
say("  Press Ctrl+C to stop the tunnel.")
say("=" * 60)
say()


# ---------------------------------------------------------------------------
# Keep alive + graceful shutdown
# ---------------------------------------------------------------------------
def shutdown(signum=None, frame=None):
    say()
    say("Shutting down tunnel ...")
    try:
        proc.terminate()
    except Exception:
        pass
    say("Done. Goodbye.")
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

try:
    while True:
        # Auto-restart a dead tunnel (Quick Tunnels get a new URL each time)
        if proc.poll() is not None:
            say("WARNING: tunnel crashed -- restarting ...")
            proc, bucket = launch_tunnel(PORT)
            new_url = wait_for_url(bucket, timeout=30)
            if new_url:
                say(f"Tunnel restarted -> {new_url}")
        time.sleep(5)
except KeyboardInterrupt:
    shutdown()
