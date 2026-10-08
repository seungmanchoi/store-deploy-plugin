#!/usr/bin/env python3
"""
Shared browser utilities for Store Deploy Plugin.
- Persistent browser profile (login sessions survive between runs)
- Step-by-step logging
- Screenshot on error
- Graceful fallback when selectors break
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from playwright.async_api import (
        Browser,
        BrowserContext,
        Page,
        Playwright,
        async_playwright,
    )
except ImportError:
    print("Error: playwright not installed.")
    print("Run: pip3 install playwright && python3 -m playwright install chromium")
    sys.exit(1)

BROWSER_DATA_DIR = Path.home() / ".store-deploy" / "browser-data"
ERROR_SCREENSHOTS_DIR = Path.home() / ".store-deploy" / "error-screenshots"

# Generous timeouts for slow store consoles
DEFAULT_TIMEOUT = 30_000  # 30s
NAV_TIMEOUT = 60_000  # 60s


class StepLogger:
    """Logs automation steps with clear formatting."""

    def __init__(self, section: str):
        self.section = section
        self.step_num = 0
        print(f"\n{'='*60}")
        print(f"  {section}")
        print(f"{'='*60}")

    def step(self, msg: str):
        self.step_num += 1
        print(f"\n  [{self.step_num}] {msg}")

    def info(self, msg: str):
        print(f"      → {msg}")

    def success(self, msg: str):
        print(f"      ✓ {msg}")

    def warn(self, msg: str):
        print(f"      ⚠ {msg}")

    def error(self, msg: str):
        print(f"      ✗ {msg}")

    def done(self):
        print(f"\n  {'─'*40}")
        print(f"  ✓ {self.section} — Complete")
        print()


class BrowserSession:
    """
    Manages a persistent Playwright browser session.
    Login sessions are preserved via user-data-dir.
    """

    def __init__(
        self,
        headless: bool = False,
        slow_mo: int = 100,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.headless = headless
        self.slow_mo = slow_mo
        self.timeout = timeout
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def start(self):
        BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA_DIR),
            headless=self.headless,
            slow_mo=self.slow_mo,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="Asia/Seoul",
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )
        self._context.set_default_timeout(self.timeout)
        self._context.set_default_navigation_timeout(NAV_TIMEOUT)

        # Use existing page or create new one
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        return self

    @property
    def page(self) -> Page:
        assert self._page, "Browser not started"
        return self._page

    @property
    def context(self) -> BrowserContext:
        assert self._context, "Browser not started"
        return self._context

    async def new_page(self) -> Page:
        assert self._context, "Browser not started"
        return await self._context.new_page()

    async def close(self):
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

    async def navigate(self, url: str, wait_until: str = "domcontentloaded"):
        """Navigate to URL with retry."""
        try:
            await self.page.goto(url, wait_until=wait_until)
        except Exception as e:
            print(f"      ⚠ Navigation slow, retrying: {e}")
            await self.page.goto(url, wait_until="commit")

    async def wait_and_click(self, selector: str, description: str = "") -> bool:
        """Wait for element and click it. Returns False if not found."""
        try:
            el = self.page.locator(selector).first
            await el.wait_for(state="visible", timeout=self.timeout)
            await el.click()
            if description:
                print(f"      ✓ Clicked: {description}")
            return True
        except Exception:
            if description:
                print(f"      ⚠ Not found: {description} ({selector})")
            return False

    async def wait_and_fill(self, selector: str, value: str, description: str = "") -> bool:
        """Wait for input and fill it. Returns False if not found."""
        try:
            el = self.page.locator(selector).first
            await el.wait_for(state="visible", timeout=self.timeout)
            await el.fill(value)
            if description:
                print(f"      ✓ Filled: {description}")
            return True
        except Exception:
            if description:
                print(f"      ⚠ Not found: {description} ({selector})")
            return False

    async def click_text(self, text: str, exact: bool = False, tag: str = "") -> bool:
        """Click element by visible text."""
        try:
            if tag:
                el = self.page.locator(tag, has_text=text).first
            else:
                el = self.page.get_by_text(text, exact=exact).first
            await el.wait_for(state="visible", timeout=10_000)
            await el.click()
            print(f"      ✓ Clicked text: '{text}'")
            return True
        except Exception:
            print(f"      ⚠ Text not found: '{text}'")
            return False

    async def click_role(self, role: str, name: str) -> bool:
        """Click element by ARIA role and name."""
        try:
            el = self.page.get_by_role(role, name=name).first
            await el.wait_for(state="visible", timeout=10_000)
            await el.click()
            print(f"      ✓ Clicked {role}: '{name}'")
            return True
        except Exception:
            print(f"      ⚠ {role} not found: '{name}'")
            return False

    async def select_radio(self, label_text: str) -> bool:
        """Select a radio button by its label text."""
        try:
            label = self.page.get_by_text(label_text, exact=False).first
            await label.click()
            print(f"      ✓ Selected: '{label_text}'")
            return True
        except Exception:
            print(f"      ⚠ Radio not found: '{label_text}'")
            return False

    async def save_error_screenshot(self, name: str):
        """Save screenshot for debugging when something goes wrong."""
        ERROR_SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = ERROR_SCREENSHOTS_DIR / f"{name}_{ts}.png"
        try:
            await self.page.screenshot(path=str(path))
            print(f"      📸 Error screenshot: {path}")
        except Exception:
            pass

    async def wait_for_login(self, check_url_contains: str, service_name: str):
        """
        Check if user is logged in by checking URL.
        If not logged in, pause and wait for manual login.
        """
        current = self.page.url
        if check_url_contains in current:
            print(f"      ✓ Already on {service_name}")
            return

        print(f"\n      ⏳ Please log into {service_name} in the browser window.")
        print(f"      Waiting for URL to contain: {check_url_contains}")
        print(f"      Press Ctrl+C to cancel.\n")

        try:
            while True:
                await asyncio.sleep(2)
                if check_url_contains in self.page.url:
                    print(f"      ✓ Logged into {service_name}")
                    return
        except KeyboardInterrupt:
            print(f"\n      Cancelled.")
            raise

    async def pause_for_manual(self, message: str, fallback_wait_sec: int = 60):
        """Pause and let user do something manually, press Enter to continue.

        When stdin is unavailable (run as a background task), fall back to a
        fixed wait so the user can act in the visible browser window instead
        of crashing with EOFError.
        """
        print(f"\n      ⏸  {message}")
        print(f"         Press Enter when done...")
        try:
            await asyncio.get_event_loop().run_in_executor(None, input)
        except EOFError:
            print(f"      ⚠ stdin unavailable — waiting {fallback_wait_sec}s, "
                  f"complete the step in the browser window")
            await self.save_error_screenshot("pause_for_manual")
            await asyncio.sleep(fallback_wait_sec)

    async def safe_step(self, description: str, coro):
        """
        Execute a step with error handling.
        On failure: save screenshot, offer manual fallback.
        """
        try:
            result = await coro
            return result
        except Exception as e:
            print(f"      ✗ Failed: {description} — {e}")
            await self.save_error_screenshot(description.replace(" ", "_"))
            print(f"      → Please complete this step manually in the browser.")
            await self.pause_for_manual(f"Complete '{description}' manually")
            return None


async def check_playwright_installed() -> bool:
    """Check if Playwright and Chromium are installed."""
    try:
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=True)
        await browser.close()
        await p.stop()
        return True
    except Exception as e:
        print(f"[!] Playwright check failed: {e}")
        print("    Run: python3 -m playwright install chromium")
        return False
