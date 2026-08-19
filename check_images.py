from PIL import Image
import os
import sys

images = [
    '2023-rag.png',
    '2024-agent.png',
    '2025-mcp.png',
    '2026-eval.png',
    '2026-obs.png',
    '2026-obs2.png'
]

for img_name in images:
    img_path = os.path.join('images', img_name)
    if os.path.exists(img_path):
        with Image.open(img_path) as img:
            print(f"{img_name}: {img.size}")
    else:
        print(f"{img_name}: Not found")
