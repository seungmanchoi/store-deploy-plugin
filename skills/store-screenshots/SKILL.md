---
name: store-screenshots
description: "Generate and process store screenshots for App Store and Google Play, one set per app language. Captures simulator/emulator screens with sim-use, supports AI generation (nano-banana-mcp), Pillow post-processing with text overlays, and iPhone Duo (required from April 2027)."
argument-hint: "[ios|android|both] [--simulator|--ai|--process] [--duo]"
---

## Step 0: Languages the App Ships

Screenshots are made **per language the app actually supports**, not per store listing guess. Find them in this order:

1. App i18n resources: `src/shared/i18n/locales/*`, `locales/*`, `app.config.ts` `locales`, `plugins/withLocalizedAppName.js` table
2. Store metadata folders: `fastlane/metadata/ios/*`, `fastlane/metadata/android/*`

Use App Store Connect locale codes as folder names: `en-US`, `ko`, `ja`, `zh-Hans`, `zh-Hant`, … (`en` → `en-US`). The processor maps them to Play codes (`ko` → `ko-KR`, `zh-Hans` → `zh-CN`) for Android.

Every language gets the **same screens in the same order** (`01_home`, `02_…`), so the store gallery lines up across locales.

## Step 1: Choose Approach

```
Screenshot approach?
  a) simulator  — Capture real app screens per language with sim-use
  b) ai         — Generate marketing screenshots with nano-banana-mcp (Gemini)
  c) process    — Post-process only (resize/overlay existing screenshots)
```

Parse from `$ARGUMENTS` if `--simulator`, `--ai`, or `--process` flag present.

## Step 2a: Simulator Capture (sim-use)

Drive screens **only with `sim-use`** (load the `sim-use` skill first). Never tap with `simctl`/`adb` coordinates or Playwright. `simctl`/`adb` are used only to boot, set the language, and launch.

Missing CLI: `brew tap lycorp-jp/tap && brew install lycorp-jp/tap/sim-use`. Missing skill: `sim-use init --client claude`.

### Output layout

```
screenshots/
├── ios/{lang}/NN_name.png                 # iPhone 6.9" (iPhone 17 Pro Max: 1320×2868)
├── ios-duo/outer/{lang}/NN_name.png       # iPhone Duo outer display (optional, see Step 2d)
├── ios-duo/inner/{lang}/NN_name.png       # iPhone Duo inner display (optional)
└── android/{lang}/NN_name.png
```

### iOS

1. Build and install once (the same build serves every language):
```bash
npx expo run:ios --device "iPhone 17 Pro Max"
sim-use devices                                   # note the UDID
xcrun simctl status_bar <UDID> override --time 9:41 --batteryState charged --batteryLevel 100 --cellularBars 4
```

2. For each language, relaunch the app in that language, then capture:
```bash
LANG_CODE=ko; APPLE_LANG=ko; APPLE_LOCALE=ko_KR    # en-US → en / en_US, zh-Hans → zh-Hans / zh_CN
mkdir -p screenshots/ios/$LANG_CODE
xcrun simctl terminate <UDID> <bundleId> 2>/dev/null || true
xcrun simctl launch <UDID> <bundleId> -AppleLanguages "($APPLE_LANG)" -AppleLocale $APPLE_LOCALE

sim-use ui --device <UDID>                         # observe
sim-use tap '#tab-games' --device <UDID>           # act: prefer #id (testID) — labels change per language
sim-use ui --device <UDID>                         # verify the screen before capturing
sim-use screenshot --device <UDID> --output screenshots/ios/$LANG_CODE/02_games.png
```

3. Check each language really switched (read `sim-use ui` text). If the app keeps an in-app language setting that overrides the device language, change it in the app's settings screen with `sim-use` instead.

4. Capture 4–6 screens per language. Fill demo data first so screens are not empty; no personal data.

### Android

```bash
sim-use android init --device <serial>             # once per emulator
adb -s <serial> shell cmd locale set-app-locales <package> --locales ko-KR   # Android 13+
adb -s <serial> shell monkey -p <package> -c android.intent.category.LAUNCHER 1
sim-use ui --device <serial>
sim-use tap '#tab-games' --device <serial>
sim-use screenshot --device <serial> --output screenshots/android/ko/02_games.png
```

Folder name stays the ASC code (`ko`); the processor writes Play codes. To skip Android capture, reuse iOS shots with `--android-crop` in Step 3.

## Step 2b: AI Generation (nano-banana-mcp)

1. Read app description from `app.json` or metadata files.
2. For each screen and language, use `generate_image` tool:

Prompt template:
```
iPhone 17 Pro Max screenshot of a {app_category} app showing {screen_description}.
UI text in {language}. Modern iOS UI, clean minimal design, {color_scheme} theme.
Full screen app UI, no device frame, 1320x2868 resolution.
```

3. Save to `screenshots/ios/{lang}/` and `screenshots/android/{lang}/`.

## Step 2c: Process Only

Skip generation, go directly to Step 3.

## Step 2d: iPhone Duo (Apple policy — required from April 2027)

Apple: from **April 2027**, every app submitted to App Store Connect must include **iPhone Duo screenshots**. How the app looks on the Duo inner display depends on the SDK it was built with:

| Built with | Inner display |
|------------|---------------|
| iOS 26 SDK or earlier | Centered window, empty space around it |
| iOS 27 SDK | Fills most of the display, avoids the right-edge status bar |
| iOS 27.1 SDK (Xcode 27.1) or later | Full display, toolbars/tab bars run vertically below the status bar |

Specs:

| Display | Portrait | Landscape |
|---------|----------|-----------|
| Outer | 1398 × 2034 | 2034 × 1398 |
| Inner | 2007 × 2853 | 2853 × 2007 |

- **Native capture (preferred)**: with Xcode 27.1+ and an iPhone Duo simulator, capture each language twice — folded (outer) to `screenshots/ios-duo/outer/{lang}/`, unfolded (inner) to `screenshots/ios-duo/inner/{lang}/` — with the same file names as `screenshots/ios/{lang}/`. Check the app in every pose before capturing.
- **Fallback (prep only)**: without a Duo simulator, `--duo` letterboxes the 6.9" captures into the Duo frames (`duoBackground` in config) for any screen that has no native capture (matched by file name). Apple does not say these pass review — they only keep the pipeline unblocked. Before submitting, replace them with native captures that match what the shipped build really shows on iPhone Duo.
- Landscape sources (wider than tall) are kept landscape (2034×1398 / 2853×2007).
- **Upload**: as of 2026-10, App Store Connect has no Duo upload slot and the API has no Duo `ScreenshotDisplayType` ("available later this year" — Apple DTS), so `fastlane deliver` cannot upload them. Output goes to `fastlane/screenshots_duo/` (kept out of `fastlane/screenshots/`, which deliver would reject). Upload in App Store Connect once the slot appears; re-check the [spec page](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications) and fastlane release notes, and move them into the deliver path when supported.

## Step 3: Post-Processing

### 3-1. Create config if missing

If `screenshots/config.json` doesn't exist, generate it from app metadata. One text array per language from Step 0, in screen order:

```json
{
  "texts": {
    "en-US": ["Track Your Calories", "Easy Food Log", "Beautiful Charts", "Set Goals"],
    "ko": ["칼로리 추적", "간편한 음식 기록", "아름다운 차트", "목표 설정"]
  },
  "fontSize": 56,
  "fontColor": "#FFFFFF",
  "overlayHeight": 200,
  "duoBackground": "#111111",
  "font": null
}
```

Write marketing-oriented text based on actual app features. Without `texts`, languages come from the `screenshots/ios/{lang}/` folders and no caption is drawn.

### 3-2. Run processor

```bash
python3 ${CLAUDE_SKILL_DIR}/../../scripts/process_screenshots.py --project . --platform both --duo
# --android-crop : build Android shots from the iOS captures (2:1 center crop)
```

Per-language source folders are used per language; a flat `screenshots/ios/` is reused for all languages. Output:

| Target | Size | Folder |
|--------|------|--------|
| iPhone 6.9" | 1320×2868 | `fastlane/screenshots/{lang}/` |
| iPhone Duo outer / inner | 1398×2034 / 2007×2853 | `fastlane/screenshots_duo/{lang}/{outer,inner}/` |
| Android phone | 1080×1920 (or 1320×2640 with `--android-crop`) | `fastlane/metadata/android/{play-lang}/images/phoneScreenshots/` |

Open one image per language and check that the captions render (no tofu boxes) and the app UI is in that language.

## Step 4: Upload

**iOS:**
```bash
fastlane ios upload_screenshots
```

**iPhone Duo:** App Store Connect web, manually, once the Duo slot exists (Step 2d). From April 2027 an iOS submission without them is blocked — do not submit iOS without them.

**Android:**
```bash
fastlane android upload_screenshots
```

## Step 5: Report

```
Screenshots Complete
====================
Languages: {langs}
Processed: {count} images
iOS:     fastlane/screenshots/{langs}/
Duo:     fastlane/screenshots_duo/{langs}/{outer,inner}/  (native | letterboxed, uploaded: yes/no)
Android: fastlane/metadata/android/{langs}/images/phoneScreenshots/
Uploaded: {yes/no}
```
