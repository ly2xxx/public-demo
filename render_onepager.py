# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow"]
# ///
"""Render OnePager-LocalFirst-AI-Stack.html -> common-left.png using headless Chrome.

Run after editing the HTML:  uv run render_onepager.py  (or: python render_onepager.py)
"""
import os
import subprocess
import sys

from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'OnePager-LocalFirst-AI-Stack.html')
OUT = os.path.join(HERE, 'images', 'common-left.png')

WIDTH = 1005          # CSS px; matches the layout the .md pages were built around
MAX_HEIGHT = 1600     # tall canvas, trimmed down to the content afterwards
SCALE = 2             # 2x for a crisp image on GitHub / retina

BROWSERS = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
]


def find_browser():
    for path in BROWSERS:
        if os.path.exists(path):
            return path
    sys.exit('No Chrome or Edge found - edit BROWSERS in this script.')


def trim_bottom(path):
    """Crop the blank page area below the content."""
    with Image.open(path).convert('RGB') as img:
        bg = Image.new('RGB', img.size, img.getpixel((img.width - 1, img.height - 1)))
        box = ImageChops.difference(img, bg).getbbox()
        if box:
            pad = 8 * SCALE
            img.crop((0, 0, img.width, min(img.height, box[3] + pad))).save(path)


def main():
    subprocess.run([
        find_browser(),
        '--headless=new',
        '--disable-gpu',
        '--hide-scrollbars',
        f'--force-device-scale-factor={SCALE}',
        f'--screenshot={OUT}',
        f'--window-size={WIDTH},{MAX_HEIGHT}',
        'file:///' + SRC.replace('\\', '/'),
    ], check=True)
    trim_bottom(OUT)
    with Image.open(OUT) as img:
        print(f'Wrote {OUT} ({img.width}x{img.height})')


if __name__ == '__main__':
    main()
