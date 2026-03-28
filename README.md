# Store Deploy Plugin

[![Claude Code](https://img.shields.io/badge/Claude_Code-Plugin-blueviolet)](https://code.claude.com)
[![Expo](https://img.shields.io/badge/Expo-SDK_54-000020)](https://expo.dev)
[![Fastlane](https://img.shields.io/badge/Fastlane-2.x-00b0ff)](https://fastlane.tools)
[![EAS](https://img.shields.io/badge/EAS_Build-CLI-4630eb)](https://docs.expo.dev/eas/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A Claude Code plugin that automates the **entire** Expo/React Native app store deployment pipeline — from build to live store listing.

## What It Does

One command (`/store-deploy full`) handles everything:

```
Build → Screenshots → Metadata → Submit → Store Forms → Done
```

| Skill | Description |
|-------|-------------|
| `/store-deploy` | Main orchestrator — routes to sub-skills or runs full pipeline |
| `/store-setup` | Install prerequisites, create fastlane structure, configure credentials |
| `/store-build` | EAS production build (local or cloud, iOS/Android) |
| `/store-screenshots` | Generate screenshots (simulator, AI, or existing) + resize & text overlay |
| `/store-metadata` | Generate multilingual metadata + upload via fastlane |
| `/store-forms` | Browser automation for store forms (age rating, privacy, data safety, etc.) |
| `/store-submit` | Submit binary via EAS Submit + post-submission metadata upload |
| `/store-admob` | Create AdMob app + ad units via browser automation |

### Parallel Platform Processing

When deploying to both platforms, the plugin uses `deploy-ios` and `deploy-android` subagents to run platform tasks **in parallel**.

## Installation

### As a Claude Code Plugin

```bash
# Clone the repo
git clone https://github.com/seungmanchoi/store-deploy-plugin.git ~/works/store-deploy-plugin
```

Then add to your Claude Code settings (`~/.claude/settings.json`).
**Important**: Use an absolute path (not `~/`):

```json
{
  "extraKnownMarketplaces": {
    "store-deploy": {
      "source": {
        "source": "directory",
        "path": "/Users/yourname/works/store-deploy-plugin"
      }
    }
  },
  "enabledPlugins": {
    "store-deploy@store-deploy": true
  }
}
```

Restart Claude Code to load the plugin. Skills will be available as `/store-deploy:skill-name`.

### Via `--plugin-dir` flag (development)

Alternatively, load the plugin directly when launching Claude Code:

```bash
claude --plugin-dir ~/works/store-deploy-plugin
```

### Prerequisites

| Tool | Install | Purpose |
|------|---------|---------|
| [EAS CLI](https://docs.expo.dev/eas/) | `npm install -g eas-cli` | Expo builds & submissions |
| [Fastlane](https://fastlane.tools/) | `brew install fastlane` | Metadata & screenshot upload |
| [Python 3 + Pillow](https://python-pillow.org/) | `pip3 install Pillow` | Screenshot resize & text overlay |
| [agent-browser](https://github.com/nicepkg/agent-browser) | `brew install agent-browser && agent-browser install` | Store form & AdMob browser automation |

Optional:
| Tool | Purpose |
|------|---------|
| Xcode + iOS Simulator | Simulator-based screenshot capture |
| nano-banana-mcp | AI-generated screenshots (Gemini) |
| Playwright MCP | In-Claude browser automation |

Run `/store-setup` to auto-check and install missing tools.

## Credentials

### iOS (App Store Connect)

| Key | Value |
|-----|-------|
| API Key File | `~/works/common/AuthKey_6FD6879KFW.p8` |
| Key ID | `6FD6879KFW` |
| Issuer ID | `69a6de87-13e2-47e3-e053-5b8c7c11a4d1` |
| Apple ID | `blue_eng@hanmail.net` |
| Team ID | `6Y6T9LPHH3` |
| ITC Team ID | `117885592` |

### Android (Google Play)

| Key | Value |
|-----|-------|
| Service Account JSON | `~/works/common/works-488915-4f58ab8044c4.json` |
| Service Account Email | `play-store-deploy@works-488915.iam.gserviceaccount.com` |

### AdMob (Optional)

For REST API access (instead of browser automation):
1. Enable AdMob API at [Google API Console](https://console.cloud.google.com/apis)
2. Create OAuth 2.0 client (Desktop app type)
3. Save credentials to `~/works/common/admob_credentials.json`

## Screenshot Configuration

### Screenshot Generation Methods

Configure your preferred method in `screenshots/config.json`:

```json
{
  "method": "simulator",
  "texts": {
    "en-US": ["Track Calories", "Log Food", "View Charts", "Set Goals"],
    "ko": ["칼로리 추적", "음식 기록", "차트 보기", "목표 설정"]
  },
  "fontSize": 56,
  "fontColor": "#FFFFFF",
  "overlayHeight": 200,
  "font": null
}
```

**`method` options:**

| Method | Description | When to Use |
|--------|-------------|-------------|
| `simulator` | Capture from iOS Simulator / Android Emulator | Real app screenshots, most accurate |
| `ai` | Generate via nano-banana-mcp (Gemini) | No simulator available, marketing-style images |
| `pillow` | Post-process existing images only | Already have raw screenshots |

If `method` is not set, the skill will ask which approach to use.

### Screenshot Sizes

| Platform | Device | Dimensions |
|----------|--------|------------|
| iOS (required) | iPhone 6.7" | 1290 × 2796 px |
| iOS (optional) | iPhone 6.5" | 1242 × 2688 px |
| Android (recommended) | Phone | 1080 × 1920 px |

### Custom Fonts

Set `"font"` to an absolute path for custom font overlay:
```json
{
  "font": "/Users/you/fonts/NotoSansKR-Bold.ttf"
}
```

Default: macOS system fonts (Arial Bold, Apple SD Gothic Neo).

## Directory Structure

After `/store-setup`, your project will have:

```
your-expo-app/
├── fastlane/
│   ├── Appfile
│   ├── Fastfile
│   ├── Deliverfile
│   ├── keys/                              # Symlinks to ~/works/common/
│   │   ├── AuthKey_6FD6879KFW.p8
│   │   └── play-store-service-account.json
│   ├── metadata/
│   │   ├── en-US/                         # iOS metadata
│   │   ├── ko/
│   │   └── android/
│   │       ├── en-US/                     # Android metadata
│   │       └── ko-KR/
│   └── screenshots/
│       ├── en-US/                         # Processed iOS screenshots
│       └── ko/
├── screenshots/
│   ├── config.json                        # Screenshot settings
│   ├── ios/                               # Raw iOS screenshots
│   └── android/                           # Raw Android screenshots
└── eas.json                               # Updated with submit profiles
```

## Plugin Structure

```
store-deploy-plugin/
├── CLAUDE.md                              # Plugin rules & credential refs
├── README.md                              # This file
├── skills/
│   ├── store-deploy/SKILL.md              # Main orchestrator
│   ├── store-setup/SKILL.md               # Prerequisites & fastlane setup
│   ├── store-build/SKILL.md               # EAS build
│   ├── store-screenshots/SKILL.md         # Screenshot generation & processing
│   ├── store-metadata/SKILL.md            # Metadata generation & upload
│   ├── store-forms/SKILL.md               # Browser automation for store forms
│   ├── store-submit/SKILL.md              # Binary submission
│   └── store-admob/SKILL.md               # AdMob setup
├── agents/
│   ├── deploy-ios.md                      # iOS parallel deployment agent
│   └── deploy-android.md                  # Android parallel deployment agent
└── scripts/
    └── process_screenshots.py             # Pillow screenshot processor
```

## Usage

### Quick Start

```
/store-deploy:store-deploy full both
```

This runs the entire pipeline for both platforms.

### Individual Actions

```
/store-deploy:store-deploy setup          # First-time project setup
/store-deploy:store-deploy build ios      # Build iOS only
/store-deploy:store-deploy screenshots    # Generate & process screenshots
/store-deploy:store-deploy metadata       # Generate & upload metadata
/store-deploy:store-deploy store-forms    # Fill store forms via browser
/store-deploy:store-deploy submit android # Submit Android binary
/store-deploy:store-deploy admob          # Set up AdMob
/store-deploy:store-deploy status         # Check deployment status
```

### Or Use Sub-Skills Directly

```
/store-deploy:store-setup
/store-deploy:store-build ios --local
/store-deploy:store-screenshots --ai
/store-deploy:store-metadata both
/store-deploy:store-forms ios
/store-deploy:store-submit both
/store-deploy:store-admob ios
```

## CLI vs Browser Automation

The plugin follows a **CLI-first** approach:

| Task | Method | Tool |
|------|--------|------|
| Build | CLI | `eas build` |
| Submit binary | CLI | `eas submit` |
| Upload metadata | CLI | `fastlane deliver` / `supply` |
| Upload screenshots | CLI | `fastlane deliver` / `supply` |
| Age rating | **Browser** | Playwright MCP / agent-browser |
| Privacy details | **Browser** | Playwright MCP / agent-browser |
| Data safety form | **Browser** | Playwright MCP / agent-browser |
| Content rating | **Browser** | Playwright MCP / agent-browser |
| Export compliance | **Browser** | Playwright MCP / agent-browser |
| IDFA declaration | **Browser** | Playwright MCP / agent-browser |
| AdMob setup | **Browser** | Playwright MCP / agent-browser |

## Troubleshooting

### EAS authentication error
```bash
eas login
```

### Fastlane Apple ID auth failure
The plugin uses API Key authentication (not password). Verify the symlink:
```bash
ls -la fastlane/keys/AuthKey_6FD6879KFW.p8
```

### Google Play metadata upload fails
First AAB must be uploaded before metadata. Run `/store-deploy:store-submit android` first.

### Simulator screenshots fail
```bash
xcrun simctl list devices available | grep "Pro Max"
```

### Pillow font error
macOS system fonts are auto-detected. For custom fonts, set the `font` field in `screenshots/config.json` to an absolute path.

## Links

- [App Store Connect](https://appstoreconnect.apple.com)
- [Google Play Console](https://play.google.com/console)
- [AdMob Console](https://apps.admob.com)
- [EAS Build Docs](https://docs.expo.dev/build/introduction/)
- [EAS Submit Docs](https://docs.expo.dev/submit/introduction/)
- [Fastlane deliver](https://docs.fastlane.tools/actions/deliver/)
- [Fastlane supply](https://docs.fastlane.tools/actions/supply/)
- [Claude Code Skills](https://code.claude.com/docs/skills)
- [Claude Code Plugins](https://code.claude.com/docs/plugins)

## License

MIT
