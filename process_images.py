from PIL import Image
import os

images = [
    '2023-rag.png',
    '2024-agent.png',
    '2025-mcp.png',
    '2026-eval.png',
    '2026-obs.png',
    '2026-obs2.png'
]

def find_split_point(img):
    w, h = img.size
    start_x = int(w * 0.3)
    end_x = int(w * 0.7)
    
    best_x = -1
    max_white_score = -1
    
    for x in range(start_x, end_x):
        white_pixels = 0
        for y in range(h):
            r, g, b = img.getpixel((x, y))
            if r > 240 and g > 240 and b > 240:
                white_pixels += 1
        if white_pixels > max_white_score:
            max_white_score = white_pixels
            best_x = x
            
    return best_x

# Extract common left from 2026-obs2.png
base_img_name = '2026-obs2.png'
if os.path.exists(base_img_name):
    with Image.open(base_img_name).convert('RGB') as img:
        split_x = find_split_point(img)
        left_img = img.crop((0, 0, split_x, img.height))
        left_img.save('common-left.png')
        print(f"Saved common-left.png (split at {split_x})")

# Process all right halves
for img_name in images:
    if os.path.exists(img_name):
        with Image.open(img_name).convert('RGB') as img:
            split_x = find_split_point(img)
            right_img = img.crop((split_x, 0, img.width, img.height))
            out_name = img_name.replace('.png', '-right.png')
            right_img.save(out_name)
            print(f"Saved {out_name} (split at {split_x})")
