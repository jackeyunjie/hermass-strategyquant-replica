#!/usr/bin/env python3
"""
Hermass StrategyQuant Replica - Browser Acceptance Test

Logs in with the demo account and navigates through every main page,
taking screenshots and checking for blank/white screens.

Usage:
    cd backend && source .venv/bin/activate
    python ../scripts/browser_acceptance.py
"""
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:3000"
EMAIL = "demo@hermass.com"
PASSWORD = "demo1234"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "tmp" / "browser_acceptance"

PAGES = [
    ("/", "Dashboard"),
    ("/strategy-builder", "Strategy Builder"),
    ("/backtest", "Backtest"),
    ("/results-ai", "Results AI"),
    ("/fuzzy-builder", "Fuzzy Builder"),
    ("/indicator-marketplace", "Indicator Marketplace"),
    ("/data", "Data"),
]


async def check_not_blank(page, name: str) -> tuple[bool, str]:
    """Return (ok, reason) after inspecting the rendered DOM."""
    body_text = (await page.locator("body").inner_text()).strip()
    if not body_text:
        return False, "body has no text"
    if len(body_text) < 20:
        return False, f"body text too short: {body_text[:50]!r}"
    lower = body_text.lower()
    if "loading" in lower and len(body_text) < 100:
        return False, "page stuck in loading state"
    if name == "Login" and ("欢迎登录" not in body_text and "login" not in lower):
        return False, "login page missing expected text"
    return True, "OK"


async def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        # 1. Login page screenshot
        print(f"[INFO] Visiting /login")
        await page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=15000)
        await page.screenshot(path=str(OUTPUT_DIR / "01-login.png"), full_page=True)
        ok, reason = await check_not_blank(page, "Login")
        results.append(("/login", ok, reason))
        print(f"  {'PASS' if ok else 'FAIL'} /login - {reason}")

        # 2. Log in
        print(f"[INFO] Logging in as {EMAIL}")
        await page.get_by_placeholder("邮箱地址").fill(EMAIL)
        await page.get_by_placeholder("密码").fill(PASSWORD)
        await page.locator('button[type="submit"]').click()

        # Wait for dashboard to load
        await page.wait_for_url(f"{BASE_URL}/", timeout=15000)
        await page.wait_for_load_state("networkidle")

        # 3. Navigate through each protected page
        for idx, (route, name) in enumerate(PAGES, start=2):
            print(f"[INFO] Visiting {route} ({name})")
            await page.goto(f"{BASE_URL}{route}", wait_until="networkidle", timeout=20000)
            await asyncio.sleep(1)  # give JS a moment to render

            filename = f"{idx:02d}-{name.lower().replace(' ', '_')}.png"
            await page.screenshot(path=str(OUTPUT_DIR / filename), full_page=True)

            ok, reason = await check_not_blank(page, name)
            results.append((route, ok, reason))
            print(f"  {'PASS' if ok else 'FAIL'} {route} - {reason}")

        await browser.close()

    # Summary
    print("\n=== Browser Acceptance Summary ===")
    failed = [r for r in results if not r[1]]
    passed = [r for r in results if r[1]]
    print(f"Passed: {len(passed)}")
    print(f"Failed: {len(failed)}")
    for route, ok, reason in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {route}: {reason}")

    print(f"\nScreenshots saved to: {OUTPUT_DIR}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
