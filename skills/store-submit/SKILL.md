---
name: store-submit
description: "Submit app binary to App Store and Google Play via EAS Submit. Handles submission configuration and post-submission metadata upload."
argument-hint: "[ios|android|both]"
---

## Step 1: Check Build

Run `eas build:list --limit 3 --platform {platform}` to find the latest successful build.

If no build found, suggest running `/store-build` first.

## Step 2: Check eas.json Submit Config

Verify `eas.json` has submit profiles with iOS credentials (`ascApiKeyPath`, `ascApiKeyIssuerId`, `ascApiKeyId`).

If `ascApiKeyPath`가 없거나 파일이 존재하지 않으면:

```bash
# .p8 키 파일 자동 탐색
ASC_KEY=$(find ~/works/common fastlane/keys -name "AuthKey_*.p8" -maxdepth 1 2>/dev/null | head -1)

# 절대 경로로 변환 (EAS CLI는 ~를 resolve하지 못함)
if [ -n "$ASC_KEY" ]; then
  RESOLVED=$(cd "$(dirname "$ASC_KEY")" && pwd)/$(basename "$ASC_KEY")
  echo "Found: $RESOLVED"
fi
```

찾은 절대 경로를 `eas.json`의 `submit.production.ios.ascApiKeyPath`에 설정한다.
파일을 찾을 수 없으면 사용자에게 경로를 질문한다.

## Step 3: Submit Binary

**iOS:**
```bash
eas submit --platform ios --profile production
```

**Android:**
```bash
eas submit --platform android --profile production
```

If submitting a specific build:
```bash
eas submit --platform {platform} --profile production --id {BUILD_ID}
```

## Step 4: Post-Submission

After binary upload, also upload metadata and screenshots if they exist:

```bash
# iOS
fastlane ios upload_all

# Android
fastlane android upload_metadata
fastlane android upload_screenshots
```

## Step 5: Report

```
Submission Complete
===================
iOS:     Binary submitted to App Store Connect
Android: AAB submitted to Google Play Console

Next:
- iOS: Review at https://appstoreconnect.apple.com
- Android: Review at https://play.google.com/console
```
