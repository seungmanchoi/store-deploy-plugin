# Store Deploy Plugin

This plugin automates the entire Expo/React Native app store deployment pipeline.

## When to Use

Always use this plugin's skills when the user requests any of the following for an Expo or React Native app:
- Building for production (App Store / Google Play)
- Generating or processing store screenshots
- Creating or uploading store metadata
- Filling store forms (age rating, privacy, data safety, etc.)
- Submitting binaries to stores
- Setting up AdMob
- Any combination of the above ("deploy to store", "publish app", etc.)

## Preflight Checklist

Before ANY deployment action, verify:
1. Current directory has `app.json` or `app.config.ts`
2. `eas.json` exists with a `production` build profile
3. Required credentials exist:
   - iOS: `~/works/common/AuthKey_6FD6879KFW.p8`
   - Android: `~/works/common/works-488915-4f58ab8044c4.json`
4. Tools are installed: `eas`, `fastlane`, `python3` (with Pillow), `agent-browser`
5. If any tool is missing, run `/store-setup` first

## Credential Reference

| Key | Value |
|-----|-------|
| iOS API Key Path | `./fastlane/keys/AuthKey_6FD6879KFW.p8` |
| iOS Key ID | `6FD6879KFW` |
| iOS Issuer ID | `69a6de87-13e2-47e3-e053-5b8c7c11a4d1` |
| iOS Apple ID | `blue_eng@hanmail.net` |
| iOS Team ID | `6Y6T9LPHH3` |
| iOS ITC Team ID | `117885592` |
| Android Service Account JSON | `./fastlane/keys/play-store-service-account.json` |
| Android Service Account Email | `play-store-deploy@works-488915.iam.gserviceaccount.com` |
| App Review Contact | Seungman Choi / blueng.choi@gmail.com |

## Important Rules

- **Never** log or display credential file contents. Reference by path only.
- **Always** use `production` build profile unless explicitly told otherwise.
- **Always** check `git status` before building — warn about uncommitted changes.
- **Google Play ordering**: First AAB must be uploaded before metadata. Run submit before metadata for new apps.
- **Browser login required**: For `store-forms` and `store-admob`, user must be logged into the console first.
- **Screenshot dimensions**: iOS requires EXACT sizes: 1320×2868 (6.9"), iPhone Duo 1398×2034 outer / 2007×2853 inner (required from April 2027). Use `scripts/process_screenshots.py` for resizing.
- **CLI first, browser fallback**: Always try CLI/API approaches first. Use agent-browser only for tasks that cannot be done via CLI (store forms, AdMob setup, content rating, etc.).
- **Parallel when possible**: Use `deploy-ios` and `deploy-android` subagents to run platform-specific tasks in parallel.

## Fastlane Auth Pattern

Always use the inline `app_store_connect_api_key` block (not file path in deliver):
```ruby
app_store_connect_api_key(
  key_id: "6FD6879KFW",
  issuer_id: "69a6de87-13e2-47e3-e053-5b8c7c11a4d1",
  key_filepath: "./fastlane/keys/AuthKey_6FD6879KFW.p8"
)
```
