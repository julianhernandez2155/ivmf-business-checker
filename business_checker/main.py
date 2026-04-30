"""
Business Checker — Desktop App Entry Point

Starts the Flask server in a background thread and opens a native pywebview
window. This is the PyInstaller entry point.

For development without pywebview, run business_checker_app.py directly.
"""

import socket
import sys
import threading

import webview

from business_checker_app import app, ensure_dirs


# ── Port selection ───────────────────────────────────────────────────────────

DEFAULT_PORT = 5001


def find_available_port(preferred: int = DEFAULT_PORT) -> int:
    """Try the preferred port first; fall back to a random available one."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", preferred))
        sock.close()
        return preferred
    except OSError:
        sock.close()
        # Let the OS pick a free port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        return port


# ── Flask server thread ──────────────────────────────────────────────────────

def start_flask(port: int) -> None:
    """Run the Flask dev server in a background thread (no reloader)."""
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False, use_reloader=False)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ensure_dirs()

    port = find_available_port()

    server = threading.Thread(target=start_flask, args=(port,), daemon=True)
    server.start()

    webview.create_window(
        "IVMF Business Checker",
        f"http://127.0.0.1:{port}",
        width=1280,
        height=860,
        min_size=(900, 600),
    )
    webview.start()  # blocks until the window is closed


if __name__ == "__main__":
    main()
