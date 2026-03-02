#!/usr/bin/env python3
"""检查封面图片是否有效"""

import os
from PIL import Image
from core.constants import JM_COVER_DIR, PK_COVER_DIR

def check_cover_images():
    """检查所有封面图片"""
    cover_dirs = [JM_COVER_DIR, PK_COVER_DIR]
    
    for cover_dir in cover_dirs:
        if not os.path.exists(cover_dir):
            print(f"目录不存在: {cover_dir}")
            continue
        
        print(f"\n检查目录: {cover_dir}")
        
        for filename in os.listdir(cover_dir):
            if filename.endswith('.jpg'):
                file_path = os.path.join(cover_dir, filename)
                try:
                    with Image.open(file_path) as img:
                        img.verify()
                        print(f"✓ 有效: {filename} ({img.format}, {img.size})")
                except Exception as e:
                    print(f"✗ 无效: {filename} - {e}")

if __name__ == '__main__':
    check_cover_images()