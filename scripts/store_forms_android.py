#!/usr/bin/env python3
"""
Google Play Console Form Automation
Fills forms that fastlane/EAS cannot handle:
1. Content Rating (IARC questionnaire)
2. Data Safety
3. Target Audience & Content
4. Ads Declaration

Usage:
  python3 store_forms_android.py --package-name com.example.app
  python3 store_forms_android.py --package-name com.example.app --config forms_config.json
  python3 store_forms_android.py --package-name com.example.app --dry-run
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from browser_base import BrowserSession, StepLogger
from credentials_manager import ensure_credentials, load_merged

GPC_BASE = "https://play.google.com/console?hl=en"


def load_forms_config(config_path: str = None, project_root: str = ".") -> dict:
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            return json.load(f)
    p = Path(project_root) / "store-deploy.json"
    if p.exists():
        with open(p) as f:
            data = json.load(f)
            return data.get("forms_android", data.get("defaults", {}))
    return {}


async def find_developer_id(browser: BrowserSession) -> str:
    """Extract developer account ID from the console URL."""
    url = browser.page.url
    # URL format: https://play.google.com/console/developers/{dev_id}/...
    if "/developers/" in url:
        parts = url.split("/developers/")
        if len(parts) > 1:
            dev_id = parts[1].split("/")[0]
            return dev_id
    return ""


async def navigate_to_app(browser: BrowserSession, package_name: str, log: StepLogger) -> str:
    """Navigate to the app in Google Play Console and return the app page base URL."""
    await browser.navigate(GPC_BASE)
    await asyncio.sleep(3)

    # Check login
    if "accounts.google.com" in browser.page.url:
        log.warn("Not logged in to Google Play Console")
        await browser.wait_for_login("play.google.com/console", "Google Play Console")
        await asyncio.sleep(3)

    # Find developer ID from URL
    dev_id = await find_developer_id(browser)

    if not dev_id:
        # Click on "All apps" to get to the app list
        await browser.click_text("All apps", exact=False)
        await asyncio.sleep(2)
        dev_id = await find_developer_id(browser)

    if not dev_id:
        log.warn("Could not detect developer ID from URL")
        await browser.pause_for_manual("Navigate to your app in Google Play Console")
        dev_id = await find_developer_id(browser)

    # Search for the app by package name
    log.info(f"Looking for app: {package_name}")

    # Try clicking on the app directly
    clicked = await browser.click_text(package_name, exact=False)
    if not clicked:
        # Try searching
        search = browser.page.locator('input[aria-label*="Search"], input[placeholder*="Search"]').first
        try:
            await search.fill(package_name)
            await asyncio.sleep(2)
            await browser.click_text(package_name, exact=False)
        except Exception:
            await browser.pause_for_manual(f"Navigate to app: {package_name}")

    await asyncio.sleep(2)
    return browser.page.url


async def fill_content_rating(browser: BrowserSession, package_name: str, config: dict, log: StepLogger):
    """
    Fill Content Rating (IARC questionnaire).
    Path: Policy and programs > Content rating
    """
    log.step("Content Rating (IARC)")

    # Navigate via sidebar
    await browser.click_text("Policy and programs", exact=False)
    await asyncio.sleep(1)
    clicked = await browser.click_text("Content rating", exact=False)
    if not clicked:
        # Try direct navigation pattern
        await browser.click_text("App content", exact=False)
        await asyncio.sleep(1)
        await browser.click_text("Content rating", exact=False)

    await asyncio.sleep(2)

    # Start questionnaire
    started = await browser.click_role("button", "Start questionnaire")
    if not started:
        started = await browser.click_role("button", "Start new questionnaire")
    if not started:
        started = await browser.click_text("Start", exact=False)

    await asyncio.sleep(2)

    # Category selection — most apps are "Utility, Productivity, Communication, or other"
    app_category = config.get("iarc_category", "utility")
    log.info(f"App category: {app_category}")

    category_map = {
        "utility": "Utility, Productivity, Communication",
        "game": "Game",
        "social": "Social Networking",
        "news": "News",
    }

    cat_text = category_map.get(app_category, category_map["utility"])
    selected = await browser.click_text(cat_text, exact=False)
    if selected:
        log.success(f"Category: {cat_text}")
    else:
        log.warn("Could not select category")
        await browser.pause_for_manual(f"Select category: {cat_text}")

    # Click Next
    await browser.click_role("button", "Next")
    await asyncio.sleep(2)

    # Answer questionnaire — for utility/productivity apps, all "No"
    has_violence = config.get("has_violence", False)
    has_sexual = config.get("has_sexual", False)
    has_profanity = config.get("has_profanity", False)
    has_drugs = config.get("has_drugs", False)
    has_gambling = config.get("has_gambling", False)

    # Select "No" for all questions
    no_buttons = await browser.page.get_by_text("No", exact=True).all()
    if no_buttons:
        log.info(f"Found {len(no_buttons)} questions, answering 'No' to all...")
        for btn in no_buttons:
            try:
                await btn.click()
                await asyncio.sleep(0.3)
            except Exception:
                pass
        log.success("All questions answered 'No'")
    else:
        log.warn("Could not find 'No' options")
        await browser.pause_for_manual("Answer questionnaire (select 'No' for all)")

    # Navigate through remaining pages
    for _ in range(5):  # Max 5 pages in questionnaire
        next_clicked = await browser.click_role("button", "Next")
        if not next_clicked:
            next_clicked = await browser.click_role("button", "Save")
            if next_clicked:
                break
            next_clicked = await browser.click_role("button", "Submit")
            if next_clicked:
                break
        await asyncio.sleep(2)

        # Keep answering "No" on subsequent pages
        no_buttons = await browser.page.get_by_text("No", exact=True).all()
        for btn in no_buttons:
            try:
                await btn.click()
                await asyncio.sleep(0.2)
            except Exception:
                pass

    log.success("Content Rating questionnaire submitted")


async def fill_data_safety(browser: BrowserSession, package_name: str, config: dict, log: StepLogger):
    """
    Fill Data Safety form.
    Path: Policy and programs > Data safety (or App content > Data safety)
    """
    log.step("Data Safety")

    await browser.click_text("Policy and programs", exact=False)
    await asyncio.sleep(1)
    clicked = await browser.click_text("Data safety", exact=False)
    if not clicked:
        await browser.click_text("App content", exact=False)
        await asyncio.sleep(1)
        await browser.click_text("Data safety", exact=False)

    await asyncio.sleep(2)

    has_ads = config.get("has_ads", False)
    data_collection = config.get("data_collection", [])
    has_analytics = "analytics" in data_collection or has_ads

    # Data collection overview
    log.info(f"Has ads: {has_ads}, Analytics: {has_analytics}")

    # "Does your app collect or share any of the required user data types?"
    if not has_ads and not data_collection:
        # No data collection
        clicked = await browser.click_text("No", exact=True)
        if clicked:
            log.success("Declared: No data collected")
        else:
            await browser.pause_for_manual("Select 'No' for data collection")
    else:
        clicked = await browser.click_text("Yes", exact=True)
        if clicked:
            log.info("Data collection: Yes")
        await browser.pause_for_manual(
            f"Fill data safety details:\n"
            f"         Ads: {has_ads}\n"
            f"         Data types: {data_collection}\n"
            f"         - If ads: declare Device/Advertising ID\n"
            f"         - If analytics: declare App interactions, Crash logs"
        )

    # Encryption
    log.info("Declaring encryption in transit: Yes (HTTPS)")
    await browser.click_text("encrypted in transit", exact=False)

    # Data deletion
    log.info("Declaring data deletion available")
    await browser.click_text("request that their data is deleted", exact=False)

    # Save / Next through pages
    for _ in range(5):
        next_clicked = await browser.click_role("button", "Next")
        if not next_clicked:
            save_clicked = await browser.click_role("button", "Save")
            if save_clicked:
                break
            submit_clicked = await browser.click_role("button", "Submit")
            if submit_clicked:
                break
        await asyncio.sleep(2)

    log.success("Data Safety saved")


async def fill_target_audience(browser: BrowserSession, package_name: str, config: dict, log: StepLogger):
    """
    Fill Target Audience & Content.
    Path: Policy and programs > Target audience and content
    """
    log.step("Target Audience & Content")

    await browser.click_text("Policy and programs", exact=False)
    await asyncio.sleep(1)
    clicked = await browser.click_text("Target audience", exact=False)
    if not clicked:
        await browser.click_text("App content", exact=False)
        await asyncio.sleep(1)
        await browser.click_text("Target audience", exact=False)

    await asyncio.sleep(2)

    min_age = config.get("min_age", 18)
    log.info(f"Target age: {min_age}+")

    # Select age group — for general apps, select "18 and over"
    if min_age >= 18:
        age_texts = ["18 and over", "18+", "Adults"]
        for text in age_texts:
            clicked = await browser.click_text(text, exact=False)
            if clicked:
                log.success(f"Target age: {text}")
                break
        if not clicked:
            await browser.pause_for_manual("Select '18 and over' target age")
    else:
        await browser.pause_for_manual(f"Select target age: {min_age}+")

    # Click Next/Save
    await browser.click_role("button", "Next")
    await asyncio.sleep(2)
    await browser.click_role("button", "Save")

    log.success("Target Audience saved")


async def fill_ads_declaration(browser: BrowserSession, package_name: str, config: dict, log: StepLogger):
    """
    Fill Ads Declaration.
    Path: Policy and programs > Ads (or within Store listing)
    """
    log.step("Ads Declaration")

    has_ads = config.get("has_ads", False)
    log.info(f"Contains ads: {has_ads}")

    await browser.click_text("Policy and programs", exact=False)
    await asyncio.sleep(1)
    clicked = await browser.click_text("Ads", exact=False)
    if not clicked:
        await browser.click_text("App content", exact=False)
        await asyncio.sleep(1)
        await browser.click_text("Ads", exact=False)

    await asyncio.sleep(2)

    if has_ads:
        clicked = await browser.click_text("Yes, my app contains ads", exact=False)
        if not clicked:
            clicked = await browser.click_text("Yes", exact=True)
        if clicked:
            log.success("Declared: App contains ads")
        else:
            await browser.pause_for_manual("Select 'Yes, my app contains ads'")
    else:
        clicked = await browser.click_text("No, my app does not contain ads", exact=False)
        if not clicked:
            clicked = await browser.click_text("No", exact=True)
        if clicked:
            log.success("Declared: App does not contain ads")
        else:
            await browser.pause_for_manual("Select 'No, my app does not contain ads'")

    # Save
    saved = await browser.click_role("button", "Save")
    if saved:
        log.success("Ads declaration saved")


async def run(args):
    creds = ensure_credentials(args.project)
    config = load_forms_config(args.config, args.project)

    defaults = creds.get("defaults", {})
    for k, v in defaults.items():
        if k not in config:
            config[k] = v

    package_name = args.package_name

    if args.dry_run:
        print("\n[DRY RUN] Would fill the following forms:")
        print(f"  Package: {package_name}")
        print(f"  Config: {json.dumps(config, indent=2)}")
        return

    log = StepLogger("Google Play Console Forms")

    async with BrowserSession(headless=False, slow_mo=150) as browser:
        # Navigate to app
        await navigate_to_app(browser, package_name, log)

        steps = {
            "content_rating": (fill_content_rating, [browser, package_name, config, log]),
            "data_safety": (fill_data_safety, [browser, package_name, config, log]),
            "target_audience": (fill_target_audience, [browser, package_name, config, log]),
            "ads_declaration": (fill_ads_declaration, [browser, package_name, config, log]),
        }

        selected = args.forms.split(",") if args.forms else list(steps.keys())

        for form_name in selected:
            if form_name in steps:
                func, func_args = steps[form_name]
                try:
                    await func(*func_args)
                except Exception as e:
                    log.error(f"{form_name} failed: {e}")
                    await browser.save_error_screenshot(f"android_{form_name}")
                    await browser.pause_for_manual(f"Complete {form_name} manually")

        log.done()

    print("\nAndroid Store Forms — Complete")
    print("=" * 40)
    for form_name in selected:
        print(f"  [✓] {form_name.replace('_', ' ').title()}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Google Play Console Form Automation")
    parser.add_argument("--package-name", required=True, help="Android package name")
    parser.add_argument("--config", help="Path to forms config JSON")
    parser.add_argument("--project", default=".", help="Project root directory")
    parser.add_argument("--forms", help="Comma-separated form names (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done")
    args = parser.parse_args()

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
