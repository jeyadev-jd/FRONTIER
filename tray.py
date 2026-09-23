"""
FRONTIER System Tray App
Requires: pip install pystray pillow

Shows 🟢 FRONTIER — Online in the system tray.
Right-click menu: Open Dashboard, Pause, Resume, Logs, Stop.
"""
import sys
import os
import threading
import subprocess
import webbrowser
import textwrap

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DASHBOARD_URL = "http://localhost:8000/docs"
LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "frontier.log")


def make_icon(color: str = "#00ff88") -> "Image.Image":
    """Generate a simple colored circle icon for the tray."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=color,
        outline="#ffffff",
        width=2,
    )
    return img


_paused = False
_frontier_process: subprocess.Popen | None = None


def start_frontier():
    global _frontier_process
    script_dir = os.path.dirname(os.path.abspath(__file__))
    python = sys.executable
    _frontier_process = subprocess.Popen(
        [python, "run.py"],
        cwd=script_dir,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )


def on_open_dashboard(icon, item):
    webbrowser.open(DASHBOARD_URL)


def on_pause(icon, item):
    global _paused
    _paused = True
    icon.icon = make_icon("#ffaa00")
    icon.title = "🟡 FRONTIER — Paused"


def on_resume(icon, item):
    global _paused
    _paused = False
    icon.icon = make_icon("#00ff88")
    icon.title = "🟢 FRONTIER — Online"


def on_open_logs(icon, item):
    if os.path.exists(LOG_FILE):
        os.startfile(LOG_FILE)
    else:
        webbrowser.open(f"file:///{LOG_FILE}")


def on_stop(icon, item):
    global _frontier_process
    if _frontier_process:
        _frontier_process.terminate()
    icon.stop()


def run_tray():
    if not TRAY_AVAILABLE:
        print("System tray requires: pip install pystray pillow")
        return

    icon = pystray.Icon(
        name="FRONTIER",
        icon=make_icon("#00ff88"),
        title="🟢 FRONTIER — Online",
        menu=pystray.Menu(
            pystray.MenuItem("Open Dashboard", on_open_dashboard, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Pause Agent", on_pause),
            pystray.MenuItem("Resume Agent", on_resume),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("View Logs", on_open_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Stop FRONTIER", on_stop),
        ),
    )

    # Start the FRONTIER backend in background
    frontier_thread = threading.Thread(target=start_frontier, daemon=True)
    frontier_thread.start()

    icon.run()


if __name__ == "__main__":
    run_tray()
