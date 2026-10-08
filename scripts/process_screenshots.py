#!/usr/bin/env python3
"""
Store Screenshot Processor
- Resizes screenshots to exact App Store / Google Play dimensions
- Adds localized text overlay at the top
- Reads config from screenshots/config.json
- Outputs to fastlane-compatible directory structure

Source layout (per-language captures are preferred; a flat folder is reused for every language):
  screenshots/ios/{lang}/NN_name.png          or  screenshots/ios/NN_name.png
  screenshots/android/{lang}/NN_name.png      or  screenshots/android/NN_name.png
  screenshots/ios-duo/{outer,inner}/{lang}/   native iPhone Duo captures (optional, see --duo)

Languages = keys of config "texts", else the {lang} subfolders of the source, else en-US.

Usage:
  python3 process_screenshots.py [--platform ios|android|both] [--duo] [--config PATH]
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Error: Pillow not installed. Run: pip3 install Pillow")
    sys.exit(1)

# Store screenshot dimensions
SIZES = {
    # iPhone 6.9" (iPhone 16/17 Pro Max simulator native size)
    "ios_69": {"name": "iPhone 6.9\"", "width": 1320, "height": 2868},
    "ios_67": {"name": "iPhone 6.7\"", "width": 1290, "height": 2796},
    "ios_65": {"name": "iPhone 6.5\"", "width": 1242, "height": 2688},
    "ios_55": {"name": "iPhone 5.5\"", "width": 1242, "height": 2208},
    # iPhone Duo (foldable). Required for every iOS submission from April 2027.
    "ios_duo_outer": {"name": "iPhone Duo outer", "width": 1398, "height": 2034},
    "ios_duo_inner": {"name": "iPhone Duo inner", "width": 2007, "height": 2853},
    "android_phone": {"name": "Android Phone", "width": 1080, "height": 1920},
    # Reuses iOS screenshots, center-cropped top/bottom to a 2:1 ratio
    # (Google Play rejects screenshots taller than 2:1).
    "android_cropped": {"name": "Android (cropped from iOS 6.9\")", "width": 1320, "height": 2640},
}

# Google Play requires full locale codes; config.json commonly uses short
# codes shared with fastlane deliver (iOS). Map short -> Play Store code.
ANDROID_LOCALE_ALIASES = {
    "ko": "ko-KR",
    "ja": "ja-JP",
    "zh": "zh-CN",
    "zh-Hans": "zh-CN",
    "zh-Hant": "zh-TW",
    "it": "it-IT",
    "da": "da-DK",
    "fi": "fi-FI",
    "sv": "sv-SE",
    "no": "no-NO",
    "pl": "pl-PL",
    "ru": "ru-RU",
    "tr": "tr-TR",
    "uk": "uk",
    "he": "iw-IL",
    "cs": "cs-CZ",
    "el": "el-GR",
    "hu": "hu-HU",
    "hi": "hi-IN",
    "ar-SA": "ar",
    "en": "en-US",
}

DEFAULT_CONFIG = {
    "texts": {},
    "fontSize": 56,
    "fontColor": "#FFFFFF",
    "overlayHeight": 200,
    "overlayColor": "rgba(0,0,0,0.6)",
    # Canvas color around a 6.9" capture when it is letterboxed into an iPhone Duo frame
    "duoBackground": "#111111",
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

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


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


def list_images(folder):
    if not folder.is_dir():
        return []
    return sorted(f for f in folder.iterdir() if f.suffix.lower() in IMAGE_SUFFIXES)


def languages_for(sources, config):
    """Config text languages first, then per-language capture folders of any source, else en-US."""
    if config.get("texts"):
        return list(config["texts"])
    subdirs = {d.name for s in sources if s.is_dir() for d in s.iterdir() if d.is_dir() and list_images(d)}
    return sorted(subdirs) or ["en-US"]


def images_for(source, lang):
    """Per-language captures win; a flat source folder is shared by all languages."""
    return list_images(source / lang) or list_images(source)


def output_name(img_path, i):
    """Keep an existing NN_ prefix; number unnumbered files."""
    stem = img_path.stem
    return stem if re.match(r"^\d{2}_", stem) else f"{i + 1:02d}_{stem}"


def resize_for_platform(img, platform_key, w, h):
    """Resize (and center-crop, for android_cropped) an image to the target size."""
    if platform_key == "android_cropped":
        # Scale to the 6.9" frame in the source orientation, then trim the long side to 2:1
        long_side, short_side = SIZES["ios_69"]["height"], SIZES["ios_69"]["width"]
        landscape = w > h
        img = img.resize((long_side, short_side) if landscape else (short_side, long_side), Image.LANCZOS)
        if landscape:
            left = (long_side - w) // 2
            return img.crop((left, 0, left + w, h))
        top = (long_side - h) // 2
        return img.crop((0, top, w, top + h))
    return img.resize((w, h), Image.LANCZOS)


def letterbox(img, w, h, top, background):
    """Fit a phone capture into a wider frame (iPhone Duo) below a `top` caption band."""
    scale = min(w / img.width, (h - top) / img.height)
    fitted = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), background)
    canvas.paste(fitted, ((w - fitted.width) // 2, top + (h - top - fitted.height) // 2))
    return canvas


def add_text_overlay(img, text, config):
    """Add text overlay at the top of the image."""
    if not text:
        return img

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


def output_dir(platform_key, lang, project_root):
    if platform_key.startswith("ios_duo"):
        # Kept out of fastlane/screenshots: deliver rejects sizes it does not know yet.
        kind = platform_key.rsplit("_", 1)[1]
        return project_root / "fastlane" / "screenshots_duo" / lang / kind
    if platform_key.startswith("ios"):
        # fastlane deliver format: fastlane/screenshots/{lang}/
        return project_root / "fastlane" / "screenshots" / lang
    # fastlane supply format (needs full Play Store locale codes)
    play_lang = ANDROID_LOCALE_ALIASES.get(lang, lang)
    return project_root / "fastlane" / "metadata" / "android" / play_lang / "images" / "phoneScreenshots"


def process_platform(platform_key, source, config, project_root, fallback_source=None):
    """Process screenshots for one store size, one output folder per language.

    `fallback_source` (iPhone Duo only): 6.9" captures letterboxed into the Duo frame
    for screens that have no native Duo capture (matched by file name).
    """
    size_w, size_h = SIZES[platform_key]["width"], SIZES[platform_key]["height"]
    texts = config.get("texts", {})
    processed = 0

    for lang in languages_for([s for s in (source, fallback_source) if s], config):
        # file name -> (path, is_native); native captures override fallback ones of the same name
        picked = {}
        if fallback_source:
            picked.update({p.name: (p, False) for p in images_for(fallback_source, lang)})
        picked.update({p.name: (p, True) for p in images_for(source, lang)})
        if not picked:
            print(f"  [!] [{lang}] no images in {source}")
            continue

        entries = [picked[name] for name in sorted(picked)]
        names = [output_name(path, i) for i, (path, _) in enumerate(entries)]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            sys.exit(f"[✗] [{lang}] several sources map to the same output name: {dupes}. Rename them.")

        out_dir = output_dir(platform_key, lang, project_root)
        out_dir.mkdir(parents=True, exist_ok=True)
        lang_texts = texts.get(lang, [])

        for i, ((img_path, native), out_name) in enumerate(zip(entries, names)):
            img = Image.open(img_path).convert("RGB")
            text = lang_texts[i] if i < len(lang_texts) else ""

            # Landscape sources keep landscape store sizes (portrait spec with sides swapped)
            w, h = (size_h, size_w) if img.width > img.height else (size_w, size_h)

            if native or not fallback_source:
                img = resize_for_platform(img, platform_key, w, h)
            else:
                top = config.get("overlayHeight", 200) if text else 0
                img = letterbox(img, w, h, top, config.get("duoBackground", "#111111"))

            img = add_text_overlay(img, text, config)
            img.save(out_dir / f"{out_name}.png", "PNG")
            processed += 1
            mode = "" if native or not fallback_source else " (letterboxed from 6.9\")"
            print(f"  [{lang}] {out_name}.png → {w}x{h}{mode}")

    return processed


def main():
    parser = argparse.ArgumentParser(description="Process store screenshots")
    parser.add_argument("--platform", choices=["ios", "android", "both"], default="both")
    parser.add_argument("--source-ios", default="screenshots/ios", help="iOS source directory")
    parser.add_argument("--source-android", default="screenshots/android", help="Android source directory")
    parser.add_argument("--source-duo", default="screenshots/ios-duo", help="Native iPhone Duo captures ({outer,inner}/{lang}/)")
    parser.add_argument("--config", default="screenshots/config.json", help="Config file path")
    parser.add_argument("--project", default=".", help="Project root directory")
    parser.add_argument(
        "--android-crop",
        action="store_true",
        help="Derive Android screenshots from screenshots/ios instead of screenshots/android, "
             "center-cropping the 6.9\" iOS frame to a 2:1 ratio",
    )
    parser.add_argument(
        "--duo",
        action="store_true",
        help="Also make iPhone Duo outer/inner screenshots into fastlane/screenshots_duo/{lang}/{outer,inner}/",
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
    source_ios = project_root / args.source_ios

    if args.platform in ("ios", "both"):
        print(f"\n=== iOS Screenshots (1320×2868 - iPhone 6.9\") ===")
        total += process_platform("ios_69", source_ios, config, project_root)

        if args.duo:
            for kind in ("outer", "inner"):
                key = f"ios_duo_{kind}"
                print(f"\n=== iPhone Duo {kind} ({SIZES[key]['width']}×{SIZES[key]['height']}) ===")
                total += process_platform(
                    key, project_root / args.source_duo / kind, config, project_root, fallback_source=source_ios,
                )

    if args.platform in ("android", "both"):
        if args.android_crop:
            print(f"\n=== Android Screenshots (1320×2640, cropped from iOS) ===")
            total += process_platform("android_cropped", source_ios, config, project_root)
        else:
            print(f"\n=== Android Screenshots (1080×1920) ===")
            total += process_platform("android_phone", project_root / args.source_android, config, project_root)

    print(f"\n[✓] Processed {total} screenshots total")

    if total > 0:
        print(f"\nOutput directories:")
        if args.platform in ("ios", "both"):
            print(f"  iOS:     {project_root}/fastlane/screenshots/")
            if args.duo:
                print(f"  Duo:     {project_root}/fastlane/screenshots_duo/  (upload manually until ASC supports Duo)")
        if args.platform in ("android", "both"):
            print(f"  Android: {project_root}/fastlane/metadata/android/*/images/phoneScreenshots/")


if __name__ == "__main__":
    main()
