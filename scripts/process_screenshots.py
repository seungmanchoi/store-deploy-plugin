#!/usr/bin/env python3
"""
Store Screenshot Processor
- Resizes screenshots to exact App Store / Google Play dimensions
- Adds localized text overlay at the top
- Reads config from screenshots/config.json
- Outputs to fastlane-compatible directory structure

Usage:
  python3 process_screenshots.py [--platform ios|android|both] [--source DIR] [--config PATH]
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Error: Pillow not installed. Run: pip3 install Pillow")
    sys.exit(1)

# Store screenshot dimensions
SIZES = {
    "ios_67": {"name": "iPhone 6.7\"", "width": 1290, "height": 2796},
    "ios_65": {"name": "iPhone 6.5\"", "width": 1242, "height": 2688},
    "ios_55": {"name": "iPhone 5.5\"", "width": 1242, "height": 2208},
    "android_phone": {"name": "Android Phone", "width": 1080, "height": 1920},
    # Reuses iOS screenshots, center-cropped top/bottom to a 2:1 ratio
    # (Google Play rejects screenshots taller than 2:1).
    "android_cropped": {"name": "Android (cropped from iOS 6.7\")", "width": 1290, "height": 2580},
}

# Google Play requires full locale codes; config.json commonly uses short
# codes shared with fastlane deliver (iOS). Map short -> Play Store code.
ANDROID_LOCALE_ALIASES = {
    "ko": "ko-KR",
    "ja": "ja-JP",
    "zh": "zh-CN",
    "zh-Hans": "zh-CN",
    "zh-Hant": "zh-TW",
}

DEFAULT_CONFIG = {
    "texts": {
        "en-US": [],
        "ko": []
    },
    "fontSize": 56,
    "fontColor": "#FFFFFF",
    "overlayHeight": 200,
    "overlayColor": "rgba(0,0,0,0.6)",
    "font": None
}

LATIN_FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# Broad CJK + Latin + Hangul coverage, needed for any ja/zh/ko text overlay
# (plain Arial/Helvetica render CJK glyphs as tofu boxes).
CJK_FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

FONT_PATHS = LATIN_FONT_PATHS  # backwards-compat alias


def find_font(config_font=None, size=56, text=""):
    """Find a usable font. Picks a CJK-capable font when `text` has non-ASCII chars."""
    if config_font and os.path.exists(config_font):
        return ImageFont.truetype(config_font, size)

    needs_cjk = any(ord(ch) > 0x2FF for ch in text)
    search_paths = CJK_FONT_PATHS if needs_cjk else LATIN_FONT_PATHS

    for fp in search_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue

    return ImageFont.load_default()


def resize_for_platform(img, platform_key, w, h):
    """Resize (and center-crop, for android_cropped) an image to the target size."""
    if platform_key == "android_cropped":
        src_w, src_h = SIZES["ios_67"]["width"], SIZES["ios_67"]["height"]
        img = img.resize((src_w, src_h), Image.LANCZOS)
        top = (src_h - h) // 2
        return img.crop((0, top, w, top + h))
    return img.resize((w, h), Image.LANCZOS)


def add_text_overlay(img, text, config):
    """Add text overlay at the top of the image."""
    if not text:
        return img

    draw = ImageDraw.Draw(img)
    w, h = img.size
    font_size = config.get("fontSize", 56)
    font = find_font(config.get("font"), font_size, text=text)
    overlay_h = config.get("overlayHeight", 200)

    # Semi-transparent overlay background
    overlay = Image.new("RGBA", (w, overlay_h), (0, 0, 0, 160))
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    img.paste(overlay, (0, 0), overlay)

    # Draw text centered
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (w - tw) // 2
    y = (overlay_h - th) // 2
    draw.text((x, y), text, fill=config.get("fontColor", "#FFFFFF"), font=font)

    return img.convert("RGB")


def process_platform(platform_key, source_dir, config, project_root):
    """Process screenshots for a specific platform and size."""
    size_info = SIZES[platform_key]
    w, h = size_info["width"], size_info["height"]
    is_ios = platform_key.startswith("ios")

    source = Path(source_dir)
    if not source.exists():
        print(f"  [!] Source directory not found: {source}")
        return 0

    images = sorted([
        f for f in source.iterdir()
        if f.suffix.lower() in (".png", ".jpg", ".jpeg")
    ])

    if not images:
        print(f"  [!] No images found in {source}")
        return 0

    processed = 0
    texts = config.get("texts", {})

    for lang, lang_texts in texts.items():
        if is_ios:
            # fastlane deliver format: fastlane/screenshots/{lang}/
            out_lang = lang
            out_dir = project_root / "fastlane" / "screenshots" / out_lang
        else:
            # fastlane supply format (needs full Play Store locale codes)
            out_lang = ANDROID_LOCALE_ALIASES.get(lang, lang)
            out_dir = project_root / "fastlane" / "metadata" / "android" / out_lang / "images" / "phoneScreenshots"

        out_dir.mkdir(parents=True, exist_ok=True)

        for i, img_path in enumerate(images):
            img = Image.open(img_path)

            # Resize to exact dimensions
            img = resize_for_platform(img, platform_key, w, h)

            # Add text overlay
            text = lang_texts[i] if i < len(lang_texts) else ""
            if text:
                img = add_text_overlay(img, text, config)

            # Save with sequential naming
            out_name = f"{i + 1:02d}_{img_path.stem}.png"
            out_path = out_dir / out_name

            if img.mode == "RGBA":
                img = img.convert("RGB")
            img.save(out_path, "PNG")
            processed += 1
            print(f"  [{out_lang}] {out_name} → {w}x{h}")

    # If no texts/langs configured, process without overlay
    if not texts:
        if is_ios:
            out_dir = project_root / "fastlane" / "screenshots" / "en-US"
        else:
            out_dir = project_root / "fastlane" / "metadata" / "android" / "en-US" / "images" / "phoneScreenshots"

        out_dir.mkdir(parents=True, exist_ok=True)

        for i, img_path in enumerate(images):
            img = Image.open(img_path)
            img = img.resize((w, h), Image.LANCZOS)
            out_name = f"{i + 1:02d}_{img_path.stem}.png"
            out_path = out_dir / out_name
            if img.mode == "RGBA":
                img = img.convert("RGB")
            img.save(out_path, "PNG")
            processed += 1
            print(f"  [en-US] {out_name} → {w}x{h}")

    return processed


def main():
    parser = argparse.ArgumentParser(description="Process store screenshots")
    parser.add_argument("--platform", choices=["ios", "android", "both"], default="both")
    parser.add_argument("--source-ios", default="screenshots/ios", help="iOS source directory")
    parser.add_argument("--source-android", default="screenshots/android", help="Android source directory")
    parser.add_argument("--config", default="screenshots/config.json", help="Config file path")
    parser.add_argument("--project", default=".", help="Project root directory")
    parser.add_argument(
        "--android-crop",
        action="store_true",
        help="Derive Android screenshots from screenshots/ios instead of screenshots/android, "
             "center-cropping the 6.7\" iOS frame to a 2:1 ratio",
    )
    args = parser.parse_args()

    project_root = Path(args.project).resolve()

    # Load config
    config_path = project_root / args.config
    if config_path.exists():
        with open(config_path) as f:
            config = {**DEFAULT_CONFIG, **json.load(f)}
        print(f"[✓] Loaded config from {config_path}")
    else:
        config = DEFAULT_CONFIG.copy()
        print(f"[!] No config found at {config_path}, using defaults (no text overlay)")

    total = 0

    if args.platform in ("ios", "both"):
        print(f"\n=== iOS Screenshots (1290×2796 - iPhone 6.7\") ===")
        source = project_root / args.source_ios
        total += process_platform("ios_67", source, config, project_root)

    if args.platform in ("android", "both"):
        if args.android_crop:
            print(f"\n=== Android Screenshots (1290×2580, cropped from iOS) ===")
            source = project_root / args.source_ios
            total += process_platform("android_cropped", source, config, project_root)
        else:
            print(f"\n=== Android Screenshots (1080×1920) ===")
            source = project_root / args.source_android
            total += process_platform("android_phone", source, config, project_root)

    print(f"\n[✓] Processed {total} screenshots total")

    if total > 0:
        print(f"\nOutput directories:")
        if args.platform in ("ios", "both"):
            print(f"  iOS:     {project_root}/fastlane/screenshots/")
        if args.platform in ("android", "both"):
            print(f"  Android: {project_root}/fastlane/metadata/android/*/images/phoneScreenshots/")


if __name__ == "__main__":
    main()
