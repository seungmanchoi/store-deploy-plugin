---
name: store-build
description: "Build Expo app for production using EAS Build. Local build is the default; cloud only when the user asks or a local build is impossible."
argument-hint: "[ios|android|both] [--cloud]"
---

## Step 1: Pre-build Checks

1. Run `git status` — warn if uncommitted changes
2. Read `eas.json` — confirm `production` profile exists
3. Check version: read `app.json` for `version`, `buildNumber`, `versionCode`
4. If `eas.json` has `"autoIncrement": true`, inform it's automatic. Otherwise ask:
   > "Current: v{version} (iOS build {buildNumber}, Android code {versionCode}). Bump version? (y/n)"

## Step 2: Choose Build Type

Default is **local** (`eas build --local`). Use cloud only when the user asks (`--cloud` in `$ARGUMENTS`) or a local build is impossible on this machine (no Xcode / Android SDK).

Apps without an EAS project (beyond the account's 25-project limit) cannot use `eas build` at all, local or cloud. Build those with the app's fastlane lane (see `~/works/AGENTS.md`).

## Step 3: Execute Build

**iOS:**
```bash
eas build --local --platform ios --profile production --non-interactive --output build-output/<app>-<ver>.ipa
# cloud, only when chosen in Step 2:
eas build --platform ios --profile production
```

**Android:**
```bash
EAS_LOCAL_BUILD_WORKINGDIR="$HOME/tmp/eas-build" eas build --local --platform android --profile production --non-interactive --output build-output/<app>-<ver>.aab
# cloud, only when chosen in Step 2:
eas build --platform android --profile production
```

For "both", launch two builds. Cloud builds can run in parallel.

## Step 4: Report

Note the local artifact path (pass it to `/store-submit`), or the build ID and dashboard URL for a cloud build.

```
Build Complete
==============
iOS:    {build_id or file path}
Android: {build_id or file path}
Dashboard: https://expo.dev/accounts/{account}/builds
```
