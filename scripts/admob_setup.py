#!/usr/bin/env python3
"""
AdMob App & Ad Unit Setup Automation
1. Create AdMob app (iOS / Android)
2. Create ad units (banner, interstitial, rewarded)
3. Save ad unit IDs to project config

Usage:
  python3 admob_setup.py --app-name "My App" --bundle-id com.example.app --package-name com.example.app
  python3 admob_setup.py --app-name "My App" --platform ios --bundle-id com.example.app
  python3 admob_setup.py --app-name "My App" --platform android --package-name com.example.app
  python3 admob_setup.py --dry-run --app-name "My App"
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from browser_base import BrowserSession, StepLogger
from credentials_manager import ensure_credentials

ADMOB_BASE = "https://apps.admob.com"

AD_UNIT_TYPES = ["banner", "interstitial", "rewarded"]


async def create_admob_app(
    browser: BrowserSession,
    platform: str,
    app_name: str,
    app_id: str,
    is_published: bool,
    log: StepLogger,
) -> str:
    """
    Create an AdMob app. Returns the AdMob App ID (ca-app-pub-XXXX~XXXX).
    """
    log.step(f"Create AdMob App ({platform.upper()})")

    # hl=en: AdMob console language follows the Google account setting (often ko),
    # but all selectors in this script are English — force the English UI.
    await browser.navigate(f"{ADMOB_BASE}/v2/home?hl=en")
    await asyncio.sleep(3)

    # Check login
    if "accounts.google.com" in browser.page.url:
        log.warn("Not logged in to AdMob")
        await browser.wait_for_login("apps.admob.com", "AdMob")
        await asyncio.sleep(3)

    # Check if app already exists
    await browser.click_text("Apps", exact=True)
    await asyncio.sleep(2)

    # Search for existing app
    existing = await browser.page.get_by_text(app_name, exact=False).count()
    if existing > 0:
        log.info(f"App '{app_name}' may already exist in AdMob")
        # Try to find app ID from the page
        app_id_match = await _extract_admob_app_id(browser, app_name)
        if app_id_match:
            log.success(f"Found existing app: {app_id_match}")
            return app_id_match
        log.warn("Could not extract App ID from existing app")

    # Click "Add app"
    clicked = await browser.click_role("button", "Add app")
    if not clicked:
        clicked = await browser.click_text("Add app", exact=False)
    if not clicked:
        log.warn("Could not find 'Add app' button")
        await browser.pause_for_manual("Click 'Add app' button")

    await asyncio.sleep(2)

    # Select platform
    platform_text = "iOS" if platform == "ios" else "Android"
    await browser.click_text(platform_text, exact=True)
    log.info(f"Platform: {platform_text}")
    await asyncio.sleep(1)

    if is_published:
        # Search for published app
        log.info(f"Searching for published app: {app_id}")
        await browser.click_text("Yes", exact=True)
        await asyncio.sleep(1)

        # Fill search field
        search_filled = await browser.wait_and_fill(
            'input[type="text"], input[placeholder*="Search"], input[aria-label*="Search"]',
            app_id,
            f"Search for {app_id}"
        )
        if search_filled:
            await asyncio.sleep(3)
            # Click on the search result
            await browser.click_text(app_name, exact=False)
        else:
            await browser.pause_for_manual(f"Search for app: {app_id}")
    else:
        # Not published yet
        log.info("App not yet published, entering manually")
        await browser.click_text("No", exact=True)
        await asyncio.sleep(1)

        # Enter app name
        await browser.wait_and_fill(
            'input[aria-label*="App name"], input[placeholder*="App name"], input[type="text"]',
            app_name,
            f"App name: {app_name}"
        )

    await asyncio.sleep(1)

    # Click Add / Continue
    added = await browser.click_role("button", "Add")
    if not added:
        added = await browser.click_role("button", "Continue")
    if not added:
        added = await browser.click_role("button", "Add app")

    await asyncio.sleep(3)

    if added:
        log.success(f"AdMob app created: {app_name} ({platform_text})")
    else:
        await browser.pause_for_manual("Complete app creation")

    # Extract the App ID from the confirmation page or redirect
    admob_app_id = await _extract_admob_app_id_from_page(browser)
    if admob_app_id:
        log.success(f"AdMob App ID: {admob_app_id}")
    else:
        log.warn("Could not auto-extract App ID")
        await browser.pause_for_manual("Note the AdMob App ID (ca-app-pub-XXXX~XXXX)")
        admob_app_id = await _extract_admob_app_id_from_page(browser)

    return admob_app_id or ""


async def _extract_admob_app_id(browser: BrowserSession, app_name: str) -> str:
    """Try to extract AdMob app ID from app list."""
    try:
        await browser.click_text(app_name, exact=False)
        await asyncio.sleep(2)
        return await _extract_admob_app_id_from_page(browser)
    except Exception:
        return ""


async def _extract_admob_app_id_from_page(browser: BrowserSession) -> str:
    """Extract ca-app-pub-XXXX~XXXX from current page content."""
    try:
        content = await browser.page.content()
        match = re.search(r"ca-app-pub-\d+~\d+", content)
        if match:
            return match.group(0)
    except Exception:
        pass
    return ""


async def create_ad_unit(
    browser: BrowserSession,
    unit_type: str,
    app_name: str,
    log: StepLogger,
) -> str:
    """
    Create an ad unit. Returns the ad unit ID (ca-app-pub-XXXX/XXXX).
    """
    unit_name = f"{app_name}_{unit_type}"
    log.info(f"Creating ad unit: {unit_name} ({unit_type})")

    # Navigate to Ad Units
    clicked = await browser.click_text("Ad units", exact=False)
    if not clicked:
        # Try sidebar navigation
        await browser.click_text("Apps", exact=True)
        await asyncio.sleep(1)
        await browser.click_text(app_name, exact=False)
        await asyncio.sleep(1)
        await browser.click_text("Ad units", exact=False)

    await asyncio.sleep(2)

    # Click "Add ad unit"
    clicked = await browser.click_role("button", "Add ad unit")
    if not clicked:
        clicked = await browser.click_text("Add ad unit", exact=False)
    if not clicked:
        await browser.pause_for_manual("Click 'Add ad unit'")

    await asyncio.sleep(2)

    # Select ad type
    type_map = {
        "banner": "Banner",
        "interstitial": "Interstitial",
        "rewarded": "Rewarded",
        "rewarded_interstitial": "Rewarded interstitial",
        "native": "Native advanced",
        "app_open": "App open",
    }

    type_text = type_map.get(unit_type, "Banner")
    clicked = await browser.click_text(type_text, exact=False)
    if clicked:
        log.info(f"Selected type: {type_text}")
    else:
        await browser.pause_for_manual(f"Select ad type: {type_text}")

    await asyncio.sleep(1)

    # Enter ad unit name
    await browser.wait_and_fill(
        'input[aria-label*="Ad unit name"], input[placeholder*="Ad unit name"], input[type="text"]',
        unit_name,
        f"Ad unit name: {unit_name}"
    )

    await asyncio.sleep(1)

    # Create
    created = await browser.click_role("button", "Create ad unit")
    if not created:
        created = await browser.click_role("button", "Create")
    if not created:
        created = await browser.click_role("button", "Done")

    await asyncio.sleep(3)

    # Extract ad unit ID
    ad_unit_id = await _extract_ad_unit_id(browser)
    if ad_unit_id:
        log.success(f"Ad unit created: {unit_name} = {ad_unit_id}")
    else:
        log.warn(f"Could not extract ad unit ID for {unit_name}")
        await browser.pause_for_manual(f"Note the ad unit ID for {unit_name}")
        ad_unit_id = await _extract_ad_unit_id(browser)

    # Close the confirmation dialog if present
    await browser.click_role("button", "Done")
    await asyncio.sleep(1)

    return ad_unit_id or ""


async def _extract_ad_unit_id(browser: BrowserSession) -> str:
    """Extract ca-app-pub-XXXX/XXXX from current page."""
    try:
        content = await browser.page.content()
        match = re.search(r"ca-app-pub-\d+/\d+", content)
        if match:
            return match.group(0)
    except Exception:
        pass
    return ""


def save_admob_config(results: dict, project_root: str, output_format: str):
    """Save AdMob IDs to project config file."""
    project = Path(project_root)

    # Save to store-deploy.json
    deploy_file = project / "store-deploy.json"
    if deploy_file.exists():
        with open(deploy_file) as f:
            existing = json.load(f)
    else:
        existing = {}

    existing["admob"] = results

    with open(deploy_file, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
    print(f"\n[✓] AdMob config saved to {deploy_file}")

    # Also generate TypeScript config if requested
    if output_format == "typescript":
        ts_content = generate_ts_config(results)
        ts_path = project / "src" / "shared" / "config" / "admob.ts"
        ts_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ts_path, "w") as f:
            f.write(ts_content)
        print(f"[✓] TypeScript config saved to {ts_path}")


def generate_ts_config(results: dict) -> str:
    """Generate TypeScript AdMob config."""
    lines = ["export const ADMOB_CONFIG = {"]

    for platform in ["ios", "android"]:
        if platform in results:
            lines.append(f"  {platform}: {{")
            lines.append(f'    appId: "{results[platform].get("app_id", "")}",')
            units = results[platform].get("ad_units", {})
            for unit_type, unit_id in units.items():
                lines.append(f'    {unit_type}: "{unit_id}",')
            lines.append("  },")

    lines.append("} as const;")
    return "\n".join(lines) + "\n"


async def run(args):
    creds = ensure_credentials(args.project)
    config = creds.get("defaults", {})
    ad_types = args.ad_types.split(",") if args.ad_types else config.get("ad_types", AD_UNIT_TYPES)

    if args.dry_run:
        print("\n[DRY RUN] Would create:")
        print(f"  App name: {args.app_name}")
        if args.platform in ("ios", "both"):
            print(f"  iOS bundle ID: {args.bundle_id}")
        if args.platform in ("android", "both"):
            print(f"  Android package: {args.package_name}")
        print(f"  Ad types: {ad_types}")
        print(f"  Published: {args.published}")
        return

    log = StepLogger("AdMob Setup")
    results = {}

    async with BrowserSession(headless=False, slow_mo=200) as browser:
        platforms = []
        if args.platform in ("ios", "both") and args.bundle_id:
            platforms.append(("ios", args.bundle_id))
        if args.platform in ("android", "both") and args.package_name:
            platforms.append(("android", args.package_name))

        for platform, app_id in platforms:
            # Create app
            admob_app_id = await create_admob_app(
                browser, platform, args.app_name, app_id, args.published, log
            )

            # Create ad units
            ad_units = {}
            log.step(f"Ad Units ({platform.upper()})")

            for unit_type in ad_types:
                unit_id = await create_ad_unit(browser, unit_type, args.app_name, log)
                ad_units[unit_type] = unit_id

            results[platform] = {
                "app_id": admob_app_id,
                "ad_units": ad_units,
            }

        log.done()

    # Save results
    save_admob_config(results, args.project, args.output)

    # Print summary
    print("\nAdMob Setup — Complete")
    print("=" * 50)
    for platform, data in results.items():
        print(f"\n  {platform.upper()}:")
        print(f"    App ID: {data['app_id']}")
        for unit_type, unit_id in data.get("ad_units", {}).items():
            print(f"    {unit_type}: {unit_id}")
    print()


def main():
    parser = argparse.ArgumentParser(description="AdMob App & Ad Unit Setup")
    parser.add_argument("--app-name", required=True, help="App display name")
    parser.add_argument("--platform", choices=["ios", "android", "both"], default="both")
    parser.add_argument("--bundle-id", help="iOS bundle identifier")
    parser.add_argument("--package-name", help="Android package name")
    parser.add_argument("--ad-types", help=f"Comma-separated ad types (default: {','.join(AD_UNIT_TYPES)})")
    parser.add_argument("--published", action="store_true", help="App is already published on store")
    parser.add_argument("--project", default=".", help="Project root directory")
    parser.add_argument("--output", choices=["json", "typescript"], default="json", help="Output format")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done")
    args = parser.parse_args()

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
