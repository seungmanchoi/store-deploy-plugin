#!/usr/bin/env python3
"""Self-check for process_screenshots.py: python3 scripts/test_process_screenshots.py"""

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

SCRIPT = Path(__file__).with_name("process_screenshots.py")


def png(path, size):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "#336699").save(path)


def run(root, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--project", str(root), *args], capture_output=True, text=True)


def size(path):
    return Image.open(path).size


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    s = root / "screenshots"
    png(s / "ios/ko/01_home.png", (1320, 2868))
    png(s / "ios/ko/02_games.png", (1320, 2868))
    png(s / "ios/en-US/01_home.png", (1320, 2868))
    png(s / "ios-duo/outer/ko/01_home.png", (2034, 1398))  # native, landscape
    png(s / "ios/ko/03_play.png", (2868, 1320))  # landscape
    png(s / "ios-duo/outer/ja/01_home.png", (1398, 2034))  # language only captured natively on Duo

    r = run(root, "--platform", "both", "--duo", "--android-crop")
    assert r.returncode == 0, r.stderr
    f = root / "fastlane"
    assert size(f / "screenshots/ko/02_games.png") == (1320, 2868)
    assert size(f / "screenshots_duo/ko/outer/01_home.png") == (2034, 1398)  # landscape kept
    assert size(f / "screenshots_duo/ko/outer/02_games.png") == (1398, 2034)  # letterbox fills the gap
    assert size(f / "screenshots_duo/ko/inner/01_home.png") == (2007, 2853)
    assert (f / "screenshots_duo/ja/outer/01_home.png").exists()  # Duo-only language kept
    assert size(f / "metadata/android/ko-KR/images/phoneScreenshots/01_home.png") == (1320, 2640)
    assert size(f / "screenshots/ko/03_play.png") == (2868, 1320)
    assert size(f / "metadata/android/ko-KR/images/phoneScreenshots/03_play.png") == (2640, 1320)

    # Two sources that would land on the same output name must fail, not overwrite
    png(s / "ios/fr-FR/02_home.png", (1320, 2868))
    png(s / "ios/fr-FR/home.png", (1320, 2868))  # numbered 02_home too
    r = run(root, "--platform", "ios")
    assert r.returncode != 0 and "same output name" in r.stderr, r.stderr

print("ok")
