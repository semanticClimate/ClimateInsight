"""
inject-tunnel.py
----------------
1. Launches cloudflared quick tunnels for both ports (5000=backend, 3000=frontend).
2. Reads the generated URLs from cloudflared's stderr output.
3. Patches frontend/js/api.js with the backend tunnel URL.
4. Prints both URLs — click the frontend link to open your app.
5. Ctrl+C shuts down tunnels and reverts api.js to localhost.

Usage:
    python scripts/inject-tunnel.py          # start tunnels
    python scripts/inject-tunnel.py --reset  # revert api.js to localhost only
"""

import sys
import re
import subprocess
import threading
import time
import signal
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT   = Path(__file__).parent.parent
API_JS = ROOT / "frontend" / "js" / "api.js"
LOCALHOST_API = "http://localhost:5000/api"

# Matches any trycloudflare.com URL in cloudflared output
URL_RE = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")


def say(msg=""):
    """print() with immediate flush — works reliably on Windows."""
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# api.js patching
# ---------------------------------------------------------------------------
def patch_api_js(target_url: str):
    text = API_JS.read_text(encoding="utf-8")
    patched = re.sub(
        r'(const API_BASE\s*=\s*")[^"]+(\")',
        rf'\g<1>{target_url}\g<2>',
        text,
    )
    if patched == text:
        say("WARNING: 'const API_BASE' not found in api.js — nothing changed.")
        return
    API_JS.write_text(patched, encoding="utf-8")
    say(f"  api.js patched  ->  {target_url}")


# ---------------------------------------------------------------------------
# --reset mode
# ---------------------------------------------------------------------------
if "--reset" in sys.argv:
    say()
    say("Reverting api.js to localhost ...")
    patch_api_js(LOCALHOST_API)
    say("Done.")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Tunnel URL reader (runs in a daemon thread)
# ---------------------------------------------------------------------------
def read_url_from_stderr(proc: subprocess.Popen, bucket: list, label: str):
    """
    Reads cloudflared stderr line by line until a trycloudflare.com URL
    is found, then stores it in bucket[0].
    """
    for raw in proc.stderr:                            # type: ignore[union-attr]
        line = raw.decode("utf-8", errors="replace").strip()
        match = URL_RE.search(line)
        if match:
            bucket.append(match.group(0))
            say(f"  [{label}] URL captured.")
            return
    bucket.append(None)   # process ended without URL


def launch_tunnel(port: int, label: str):
    """Start cloudflared for port; return (proc, url_bucket, reader_thread)."""
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    bucket: list = []
    t = threading.Thread(
        target=read_url_from_stderr,
        args=(proc, bucket, label),
        daemon=True,
    )
    t.start()
    return proc, bucket, t


def wait_for_url(bucket: list, label: str, timeout: int = 60):
    deadline = time.time() + timeout
    dots = 0
    while time.time() < deadline:
        if bucket:
            return bucket[0]
        # print a progress dot every 3 seconds
        dots += 1
        if dots % 10 == 0:
            say(f"  ... still waiting for {label} tunnel URL ...")
        time.sleep(0.3)
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
say()
say("=" * 60)
say("  Cloudflare Quick Tunnel Launcher")
say("  backend  -> http://localhost:5000")
say("  frontend -> http://localhost:3000")
say("=" * 60)
say()
say("Starting cloudflared for backend  (port 5000) ...")
proc_back,  bucket_back,  _ = launch_tunnel(5000, "backend :5000")
say("Starting cloudflared for frontend (port 3000) ...")
proc_front, bucket_front, _ = launch_tunnel(3000, "frontend :3000")
say()
say("Waiting for Cloudflare to assign URLs (up to 60 s) ...")
say()

backend_url  = wait_for_url(bucket_back,  "backend")
frontend_url = wait_for_url(bucket_front, "frontend")

if not backend_url or not frontend_url:
    say()
    say("ERROR: Could not get both tunnel URLs.")
    say("Make sure both servers are running:")
    say("  backend  -> python app.py        (port 5000)")
    say("  frontend -> python -m http.server 3000")
    proc_back.terminate()
    proc_front.terminate()
    sys.exit(1)

# Patch api.js
say()
patch_api_js(backend_url + "/api")

# Print summary
say()
say("=" * 60)
say("  TUNNELS ARE LIVE")
say("-" * 60)
say(f"  backend  API  ->  {backend_url}/api")
say(f"  frontend app  ->  {frontend_url}")
say("-" * 60)
say("  Click the FRONTEND URL above to open your app.")
say("  api.js is already patched to the backend tunnel.")
say()
say("  Press Ctrl+C to stop tunnels and revert api.js.")
say("=" * 60)
say()


# ---------------------------------------------------------------------------
# Keep alive + graceful shutdown
# ---------------------------------------------------------------------------
def shutdown(signum=None, frame=None):
    say()
    say("Shutting down tunnels ...")
    try:
        proc_back.terminate()
    except Exception:
        pass
    try:
        proc_front.terminate()
    except Exception:
        pass
    say("Reverting api.js to localhost ...")
    patch_api_js(LOCALHOST_API)
    say("Done. Goodbye.")
    sys.exit(0)


signal.signal(signal.SIGINT,  shutdown)
signal.signal(signal.SIGTERM, shutdown)

try:
    while True:
        # Auto-restart a dead tunnel
        if proc_back.poll() is not None:
            say("WARNING: backend tunnel crashed -- restarting ...")
            proc_back, bucket_back, _ = launch_tunnel(5000, "backend :5000")
            new_url = wait_for_url(bucket_back, "backend", timeout=30)
            if new_url:
                patch_api_js(new_url + "/api")
                say(f"backend tunnel restarted -> {new_url}/api")

        if proc_front.poll() is not None:
            say("WARNING: frontend tunnel crashed -- restarting ...")
            proc_front, bucket_front, _ = launch_tunnel(3000, "frontend :3000")
            new_url = wait_for_url(bucket_front, "frontend", timeout=30)
            if new_url:
                say(f"frontend tunnel restarted -> {new_url}")

        time.sleep(5)
except KeyboardInterrupt:
    shutdown()