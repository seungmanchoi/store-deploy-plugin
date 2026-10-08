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

**macOS local-build guards** (run once before any `--local` build; safe no-ops when not needed):

```bash
# iOS — drop stale eas-build-*.keychain entries from the search list. Interrupted local
# builds leave them behind, and a leftover one can hold a duplicate-named distribution
# cert that xcodebuild picks during exportArchive (see Troubleshooting). Nothing is deleted.
security list-keychains -d user -s "$HOME/Library/Keychains/login.keychain-db"

# Android (reanimated/worklets) — build in a symlink-free dir (/tmp -> /private/tmp breaks
# ninja with `libworklets.so missing`). Android only; never pass it to the iOS build.
mkdir -p "$HOME/tmp/eas-build"
```

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

## Troubleshooting: local builds (macOS)

These apply to ANY Expo project doing `eas build --local` on macOS.

### iOS export fails: "Provisioning profile doesn't include signing certificate"

Symptom — ARCHIVE succeeds but the **exportArchive** step fails:
```
error: exportArchive Provisioning profile "*[expo] <bundleId> AppStore ..."
  doesn't include signing certificate "iPhone Distribution: <Name> (<TeamID>)".
** EXPORT FAILED **
```

Root cause is almost never a bad certificate. It is **stale `eas-build-*.keychain`
entries accumulated in the macOS keychain search list** from prior interrupted/failed
local builds. When two distribution certs share the same common name — the correct one
(in the build's fresh temp keychain, included in the profile) and an old one (in a
leftover keychain, NOT in the profile) — xcodebuild's export searches the whole list
and can pick the wrong one. ARCHIVE passes because it signs with the build's own temp
keychain; only export re-resolves across all keychains and trips.

Diagnose:
```bash
security list-keychains -d user                 # many eas-build-*.keychain → this case
security find-identity -v -p codesigning        # duplicate same-named distribution certs?
```
The login keychain itself is usually clean (only an "Apple Development" cert), so this
is NOT a user-credential problem.

Fix (non-destructive — DO NOT delete keychain certs):
```bash
security list-keychains -d user -s "$HOME/Library/Keychains/login.keychain-db"
# then rebuild; EAS re-imports the correct cert into a fresh temp keychain
```

If export still fails at ARCHIVE (not export) with a similar message, it is instead an
eas-cli version issue with legacy "iPhone Distribution" certs — build with a known-good
CLI: `npx -y eas-cli@20.1.0 build --local --platform ios --profile production ...`
(set `FASTLANE_XCODEBUILD_SETTINGS_TIMEOUT=180` to avoid showBuildSettings timeouts).

### Android: `libworklets.so missing` ninja error

reanimated/worklets fail to link because the EAS local build dir is under
`/tmp` (a symlink to `/private/tmp`) and CMake/Ninja confuse the logical vs physical
path. Fix: build in a symlink-free dir via `EAS_LOCAL_BUILD_WORKINGDIR` (Step 3 Android command).

### Project archive fails to compress (`Cannot copy a socket file`)

A unix socket in the project tree (e.g. `.codegraph/daemon.sock`) breaks EAS project
compression. Add the offending dir to `.easignore` (e.g. `.codegraph/`).

### Cloud build credits exhausted

`eas build` (cloud) errors with "used 100% of included build credits this month".
Free credits reset on the 1st. Fall back to `--local` builds and submit the local
artifact with `eas submit --path <artifact>`.
