"""
UI smoke tests for the Almanac app.

Launches index.html in headless Chromium via Playwright and verifies:
- The Today, Exercise, and Meals tabs each render their circular tracker
- The Exercise tab shows the workout title instead of a duplicate date
- The exercise info modal opens cleanly
- No JS console errors fire on any tab, at both mobile and desktop widths

Setup:
    pip install -r requirements-dev.txt
    playwright install chromium

Usage:
    python tests/test_ui.py
"""

import functools
import http.server
import socket
import sys
import threading
from contextlib import closing
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent.parent

VIEWPORTS = [
    ("mobile", {"width": 390, "height": 844}),
    ("desktop", {"width": 1400, "height": 900}),
]


def free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def serve(port):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("localhost", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def run():
    port = free_port()
    server = serve(port)
    url = f"http://localhost:{port}/index.html"
    failures = []

    def check(cond, msg):
        if cond:
            print(f"  ok: {msg}")
        else:
            failures.append(msg)
            print(f"  FAIL: {msg}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()

            for label, viewport in VIEWPORTS:
                print(f"--- {label} ({viewport['width']}x{viewport['height']}) ---")
                page = browser.new_page(viewport=viewport)
                errors = []
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.goto(url)
                page.wait_for_selector("#todayView.active")

                check(page.is_visible("#arcSvg"), "today tab shows tracker")

                page.click("#tabExercise")
                page.wait_for_timeout(200)
                check(page.is_visible(".exercise-head"), "exercise tab renders")
                check(page.is_visible("#arcSvg"), "exercise tab shows tracker")
                heading = page.text_content(".exercise-head h3") or ""
                check(
                    heading != "" and "," not in heading and not any(c.isdigit() for c in heading),
                    f"exercise heading is a workout title, not a date (got {heading!r})",
                )

                page.click("#tabMeals")
                page.wait_for_timeout(200)
                check(page.is_visible("#arcSvg"), "meals tab shows tracker")

                page.click("#tabExercise")
                page.wait_for_timeout(200)
                info_btn = page.query_selector(".info-btn")
                check(info_btn is not None, "exercise info button exists")
                if info_btn:
                    info_btn.click()
                    page.wait_for_timeout(200)
                    check(page.is_visible("#infoModalOverlay.open"), "info modal opens")
                    page.click("#modalCloseBtn")

                check(errors == [], f"no console errors (got {errors})")
                page.close()

            browser.close()
    finally:
        server.shutdown()

    print()
    if failures:
        print(f"{len(failures)} check(s) failed.")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    run()
