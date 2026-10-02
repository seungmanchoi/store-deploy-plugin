---
name: store-admob
description: "Set up AdMob app and create ad units (banner, interstitial, rewarded) via Python+Playwright automation. Saves ad unit IDs to project config."
argument-hint: "[ios|android|both]"
---

This skill sets up AdMob using **Python scripts with Playwright** (NOT Playwright MCP).
Zero LLM token cost for browser automation.

## Step 1: Ensure Credentials

```bash
python3 ${PLUGIN_DIR}/scripts/credentials_manager.py --show
```

If not configured:
```bash
python3 ${PLUGIN_DIR}/scripts/credentials_manager.py --setup
```

## Step 2: Determine Setup Parameters

Read `app.json` to extract:
- App name (expo.name)
- Bundle ID (expo.ios.bundleIdentifier)
- Package name (expo.android.package)

Ask the developer:
- Which ad types? Default: the formats the app code calls. With the template that is `banner,interstitial,rewarded,app_open` (`useAppOpenAd` calls `APP_OPEN`). Add `native` only if the app shows `NATIVE_FEED`.
- Is the app already published? (affects AdMob app linking)
- Output format? (json or typescript)

## Step 3: Run AdMob Setup Script

**IMPORTANT**: Tell the user:
> "Browser will open. Please log into AdMob (https://apps.admob.com) if prompted."

Always pass `--ad-types` with the list from Step 2. Without it the script creates only `banner,interstitial,rewarded`, and the template's `APP_OPEN` gets no production ID.

### Both platforms:
```bash
python3 ${PLUGIN_DIR}/scripts/admob_setup.py \
  --app-name "{APP_NAME}" \
  --platform both \
  --bundle-id {BUNDLE_ID} \
  --package-name {PACKAGE_NAME} \
  --ad-types {AD_TYPES} \
  --project .
```

### iOS only:
```bash
python3 ${PLUGIN_DIR}/scripts/admob_setup.py \
  --app-name "{APP_NAME}" \
  --platform ios \
  --bundle-id {BUNDLE_ID} \
  --ad-types {AD_TYPES} \
  --project .
```

### Android only:
```bash
python3 ${PLUGIN_DIR}/scripts/admob_setup.py \
  --app-name "{APP_NAME}" \
  --platform android \
  --package-name {PACKAGE_NAME} \
  --ad-types {AD_TYPES} \
  --project .
```

### Custom ad types:
```bash
python3 ${PLUGIN_DIR}/scripts/admob_setup.py \
  --app-name "{APP_NAME}" \
  --platform both \
  --bundle-id {BUNDLE_ID} \
  --package-name {PACKAGE_NAME} \
  --ad-types banner,interstitial \
  --project .
```

### With TypeScript output:
```bash
python3 ${PLUGIN_DIR}/scripts/admob_setup.py \
  --app-name "{APP_NAME}" \
  --platform both \
  --bundle-id {BUNDLE_ID} \
  --package-name {PACKAGE_NAME} \
  --ad-types {AD_TYPES} \
  --output typescript \
  --project .
```

### Dry run:
```bash
python3 ${PLUGIN_DIR}/scripts/admob_setup.py --app-name "My App" --dry-run
```

## Step 4: Verify Output

The script saves AdMob IDs to `store-deploy.json`:
```json
{
  "admob": {
    "ios": {
      "app_id": "ca-app-pub-XXXXX~XXXXX",
      "ad_units": {
        "banner": "ca-app-pub-XXXXX/XXXXX",
        "interstitial": "ca-app-pub-XXXXX/XXXXX",
        "rewarded": "ca-app-pub-XXXXX/XXXXX"
      }
    },
    "android": {
      "app_id": "ca-app-pub-XXXXX~XXXXX",
      "ad_units": {
        "banner": "ca-app-pub-XXXXX/XXXXX",
        "interstitial": "ca-app-pub-XXXXX/XXXXX",
        "rewarded": "ca-app-pub-XXXXX/XXXXX"
      }
    }
  }
}
```

If `--output typescript` was used, also check `src/shared/config/admob.ts`.

Read the output file and confirm the IDs are populated. If any are empty, the script encountered issues — check `~/.store-deploy/error-screenshots/`.

## Step 5: Integrate into App

`~/works/react-native-fsd-template` 의 광고 구현을 그대로 가져다 쓴다. 코드를 새로 짜지 않는다.

- `src/shared/config/ads.ts`: 광고 단위 ID. dev 는 Google 테스트 ID, prod 는 Step 4 의 실제 ID (`env.IS_PROD` 분기)
- `src/features/ads/`: `lib/consent.ts` (초기화 순서), `hooks/` (인터스티셜·리워드), `store/` (빈도 제한), `ui/AdBanner.tsx`
- `plugins/withLocalizedAttDescription.js`: 언어별 ATT 문구

1. 패키지: `npm install react-native-google-mobile-ads`, `npx expo install expo-tracking-transparency`
2. `app.config.ts` plugins: `react-native-google-mobile-ads` 에 `androidAppId`, `iosAppId`, `userTrackingUsageDescription` 을, `expo-tracking-transparency` 에 `userTrackingPermission` 을 넣는다. iOS `infoPlist` 의 `NSUserTrackingUsageDescription` 도 같은 문구로 둔다.
3. **ATT 목적 문자열 (CRITICAL, 위반 시 자동 반려)**: Apple 자동 심사가 상투 문구를 Guideline 5.1.1 로 반려한다 (실제 사례: poly-dash 1.0.10, 2026-08-06).
   - 금지: `This identifier will be used to deliver personalized ads to you.` 처럼 용도만 말하는 문장. `App would like to access your Contacts`, `App needs microphone access` 도 같다.
   - 필수 4요소: 무엇을 쓰는지 (기기의 광고 식별자), 왜 쓰는지 (광고 관련성 향상, 설치 측정), 구체적 예시 ("관련 없는 상품 대신 이 앱과 비슷한 앱·게임 광고를 보여준다"), 거부했을 때의 결과 ("광고는 계속 표시되며 맞춤 광고가 아닐 뿐")
   - 문구는 앱마다 새로 쓴다. 형식 예시 (그대로 복사하지 않는다):
     "{앱이름} uses your device's advertising identifier to make the ads shown in this app more relevant — for example, showing ads for apps and games similar to {앱이름} instead of unrelated products — and to measure how many people install an app after seeing its ad. Ads still appear if you decline; they just won't be personalized."
   - `withLocalizedAttDescription.js` 로케일 테이블도 언어별로 같은 구성으로 채운다. 기본 placeholder 테이블을 그대로 두면 `.lproj` 에 상투 문구가 실려 같은 반려를 받는다. `app.config.ts` 만 고치는 것으로는 부족하다.
4. **초기화 순서**: UMP 동의 → iOS ATT → `mobileAds().setRequestConfiguration()` → `mobileAds().initialize()`. 순서가 어긋나면 첫 광고 요청이 동의 정보를 반영하지 못한다. `_layout.tsx` 는 `initializeAdsWithConsent()` 만 `void` 로 부른다 (await 하지 않는다. 첫 렌더를 막지 않는다).
   - AdMob Console → Privacy & messaging 에서 GDPR 메시지와 IDFA 메시지를 만들어 게시해야 동의 폼이 뜬다. 게시하지 않으면 `requestInfoUpdate()` 가 항상 not required 를 돌려준다.
   - Android 는 ATT 가 없고 `AD_ID` 권한이 자동으로 들어가므로 추가 작업이 없다.
5. **인터스티셜 빈도 제한**: 앱 시작 후 최소 3분, N회 액션마다 1회 (기본 3회), 최소 60초 간격, 하루 최대 10회
6. **광고 금지 구역**: 카메라·핵심 기능 화면에는 배너를 넣지 않는다. 핵심 액션 직전·진행 중에는 인터스티셜을 띄우지 않는다.
7. **`ads.ts` 키와 광고 단위 대응**: 앱 코드가 부르는 키는 모두 운영 ID 를 채운다. 부르지 않는 키는 placeholder 로 두고, 그 키를 쓰는 훅·컴포넌트를 앱에 넣지 않는다.

   | `ads.ts` 키 | `--ad-types` | `store-deploy.json` |
   |---|---|---|
   | `BANNER_GALLERY`, `BANNER_SETTINGS` | `banner` | `ad_units.banner` (두 키에 같은 ID 를 써도 된다) |
   | `INTERSTITIAL_AFTER_ACTION` | `interstitial` | `ad_units.interstitial` |
   | `REWARDED_PREMIUM` | `rewarded` | `ad_units.rewarded` |
   | `NATIVE_FEED` | `native` | `ad_units.native` |
   | `APP_OPEN` | `app_open` | `ad_units.app_open` (템플릿 `useAppOpenAd` 가 부른다) |

   콘솔에서 직접 만들 때도 스크립트와 같은 이름 `{앱이름}_{형식}` 을 쓴다.
8. **제출 전 확인**: 앱이 부르는 키마다 `ads.ts` 의 iOS·Android 운영 값이 `ca-app-pub-XXXXX` placeholder 가 아닌지 본다.

## Step 6: Report

```
AdMob Setup Complete
====================
iOS App ID:     ca-app-pub-XXXXX~XXXXX
Android App ID: ca-app-pub-XXXXX~XXXXX

Ad Units:
  banner:       ca-app-pub-XXXXX/XXXXX (iOS) / ca-app-pub-XXXXX/XXXXX (Android)
  interstitial: ca-app-pub-XXXXX/XXXXX (iOS) / ca-app-pub-XXXXX/XXXXX (Android)
  rewarded:     ca-app-pub-XXXXX/XXXXX (iOS) / ca-app-pub-XXXXX/XXXXX (Android)

Config saved to: store-deploy.json
```

## Step 7: Policy Compliance Checklist (계정 정지 방어)

After setup, walk the user through this checklist. These are account-level items that code alone cannot fix:

1. **app-ads.txt 게시**: 개발자 웹사이트 루트에 `app-ads.txt`를 게시한다
   (`~/works/seungmanchoi.github.io/app-ads.txt` → `https://seungmanchoi.github.io/app-ads.txt`).
   내용은 AdMob Console → 앱 → 모든 앱 보기 → app-ads.txt 탭에서 확인. 형식:
   ```
   google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0
   ```
   스토어 리스팅의 "개발자 웹사이트"가 같은 도메인을 가리켜야 크롤링된다.
   미게시 시 광고 게재 제한(ad serving limit)으로 직행한다.

2. **스토어 리스팅 연결**: 앱 출시 후 AdMob 앱을 스토어 리스팅에 연결한다
   (AdMob Console → 앱 설정 → 앱 스토어 세부정보). 미연결/미검증 상태가
   길어지면 광고 게재가 제한된다.

3. **테스트 기기 등록**: 실제 광고 단위 ID가 들어간 internal/TestFlight 빌드를
   배포하기 전, 개발자/테스터 실기기를 `setRequestConfiguration({ testDeviceIdentifiers })`에
   등록한다 (템플릿의 `TEST_DEVICE_IDS` 상수). 미등록 기기의 클릭은 무효 트래픽으로
   집계되어 계정 정지 사유가 된다.

4. **본인 광고 클릭 절대 금지**: 프로덕션 빌드에서 본인 광고를 클릭하지 않는다.
   스토어 스크린샷 촬영도 테스트 기기/TestIds 상태에서만 진행한다 (실광고 화면 캡처 금지).
