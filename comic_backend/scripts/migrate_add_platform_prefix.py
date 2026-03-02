"""
数据迁移脚本：为数据库中的漫画ID添加平台前缀
- 主页漫画：ID添加JM前缀
- 推荐页漫画：ID添加JM前缀
- 同步更新封面路径
"""

import json
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.constants import JSON_FILE, RECOMMENDATION_JSON_FILE
from core.platform import add_platform_prefix, Platform


def migrate_comics(data_file: str, platform: Platform = Platform.JM):
    """迁移指定数据库文件中的漫画ID"""
    if not os.path.exists(data_file):
        print(f"文件不存在: {data_file}")
        return

    # 读取数据
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 支持两种键名：comics（主页）和 recommendations（推荐页）
    comics = data.get('comics', []) or data.get('recommendations', [])
    data_type = 'comics' if 'comics' in data else 'recommendations'
    
    if not comics:
        print(f"{data_file}: 没有漫画数据")
        return

    # 统计需要迁移的数量
    need_migration = []
    for comic in comics:
        comic_id = comic.get('id', '')
        if comic_id and not comic_id.startswith('JM') and not comic_id.startswith('PK'):
            need_migration.append(comic)

    if not need_migration:
        print(f"{data_file}: 所有漫画ID已包含平台前缀，无需迁移")
        return

    print(f"\n{data_file}:")
    print(f"  总漫画数: {len(comics)}")
    print(f"  需要迁移: {len(need_migration)}")

    # 创建ID映射
    id_mapping = {}
    for comic in need_migration:
        old_id = comic['id']
        new_id = add_platform_prefix(platform, old_id)
        id_mapping[old_id] = new_id
        comic['id'] = new_id

        # 更新封面路径（只处理本地封面，不处理外部URL）
        if 'cover_path' in comic:
            old_cover = comic['cover_path']
            # 将 /static/cover/123456.jpg 改为 /static/cover/JM/123456.jpg
            if old_cover.startswith('/static/cover/') and not '/JM/' in old_cover and not '/PK/' in old_cover:
                filename = os.path.basename(old_cover)
                comic['cover_path'] = f"/static/cover/JM/{filename}"

    # 显示迁移详情
    print(f"  ID映射示例:")
    for i, (old_id, new_id) in enumerate(list(id_mapping.items())[:5]):
        print(f"    {old_id} -> {new_id}")
    if len(id_mapping) > 5:
        print(f"    ... 还有 {len(id_mapping) - 5} 条")

    # 保存数据
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  ✓ 迁移完成，已保存到 {data_file}")
    return len(need_migration)


def main():
    print("=" * 60)
    print("漫画ID平台前缀迁移工具")
    print("=" * 60)

    total_migrated = 0

    # 迁移主页漫画
    if os.path.exists(JSON_FILE):
        count = migrate_comics(JSON_FILE, Platform.JM)
        if count:
            total_migrated += count
    else:
        print(f"主页数据文件不存在: {JSON_FILE}")

    # 迁移推荐页漫画
    if os.path.exists(RECOMMENDATION_JSON_FILE):
        count = migrate_comics(RECOMMENDATION_JSON_FILE, Platform.JM)
        if count:
            total_migrated += count
    else:
        print(f"推荐页数据文件不存在: {RECOMMENDATION_JSON_FILE}")

    print("\n" + "=" * 60)
    print(f"迁移完成！共迁移 {total_migrated} 部漫画")
    print("=" * 60)
    print("\n请重启后端服务以应用更改")


if __name__ == "__main__":
    main()
