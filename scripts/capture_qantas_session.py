"""Capture an authenticated Qantas session for reuse by the scraper.

Run this once, log in to your Qantas Frequent Flyer account in the
browser window that opens, then return to the terminal and press Enter.
The cookies/local storage are saved to a ``storage_state`` JSON that the
provider reuses (env ``QANTAS_STORAGE_STATE``), so Classic Reward pricing
is visible without logging in on every run.

Usage:
    python scripts/capture_qantas_session.py [output_path]
"""

from __future__ import annotations

import asyncio
import sys

from playwright.async_api import async_playwright

LOGIN_URL = "https://www.qantas.com/au/en/frequent-flyer/login.html"


async def capture(output_path: str) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context(locale="en-AU")
        page = await context.new_page()
        await page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print("\nA browser window has opened.")
        print("1) Log in to your Qantas Frequent Flyer account.")
        print("2) Once you see your account dashboard, come back here.")
        # Run blocking input() off the event loop.
        await asyncio.get_event_loop().run_in_executor(
            None, input, "Press Enter to save the session... "
        )

        await context.storage_state(path=output_path)
        print(f"Saved session to: {output_path}")
        await browser.close()


def main() -> None:
    output_path = sys.argv[1] if len(sys.argv) > 1 else "qantas_session.json"
    asyncio.run(capture(output_path))


if __name__ == "__main__":
    main()
