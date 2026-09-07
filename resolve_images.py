#!/usr/bin/env python3
"""resolve_images.py - 按占位符名字自动匹配用户放入的图片并替换占位符

用法: python3 resolve_images.py "<文章md绝对路径>"

规则:
- md 内占位符格式: ![图N-建议内容]()（空链接）
- 用户把图片文件命名为占位符的名字（如 "图1-封面-沙漠星球画面.jpg"），
  放入文章同目录下的 images-{标题}/ 文件夹（中文名即可，无需懂英文）
- 本脚本扫描该文件夹，按文件名（忽略扩展名）自动匹配占位符，
  匹配后自动把图片重命名为英文短名 img1.jpg / img2.jpg ...（Obsidian 解析中文/空格路径不可靠），
  并替换为相对路径引用
- 未匹配的占位符输出缺图清单

匹配规则:
- 精确匹配: 文件名 = 占位符文本
- 宽松匹配: 去掉所有空格后相等（如占位符 "图1 封面" 可匹配文件 "图1封面.jpg"）
"""
import os
import re
import sys


def resolve_images(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 分离 frontmatter 与正文
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]

    md_dir = os.path.dirname(filepath)
    title = os.path.basename(filepath).replace(".md", "")
    img_dir = os.path.join(md_dir, f"images-{title}")
    # 兼容：目录不存在时，自动在 md 同目录下找唯一的 images-* 目录
    # （成稿的图片目录统一用纯英文短名如 images-fermat-proof，避免 Obsidian 解析中文/空格路径失败）
    if not os.path.isdir(img_dir):
        candidates = [
            os.path.join(md_dir, d)
            for d in os.listdir(md_dir)
            if d.startswith("images-") and os.path.isdir(os.path.join(md_dir, d))
        ]
        if len(candidates) == 1:
            img_dir = candidates[0]

    # 提取所有占位符
    placeholders = re.findall(r"!\[([^\]]*)\]\(\)", body)
    if not placeholders:
        print("✅ 无占位符，无需配图")
        return True

    # 扫描图片文件夹，建立 {名字: 文件名} 映射（含宽松匹配）
    available = {}
    if os.path.isdir(img_dir):
        for fn in os.listdir(img_dir):
            base, ext = os.path.splitext(fn)
            if ext.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                available[base] = fn
                available[re.sub(r"\s+", "", base)] = fn

    matched = []
    missing = []
    for ph in placeholders:
        ph_key = re.sub(r"\s+", "", ph)
        if ph in available or ph_key in available:
            matched.append(ph)
        else:
            missing.append(ph)

    # 替换占位符：把匹配到的图片重命名为英文短名 img1.jpg / img2.jpg ...
    # （Obsidian 解析含中文/空格/全角标点的图片路径不可靠，统一转英文名）
    new_body = body
    img_dir_name = os.path.basename(img_dir)
    for i, ph in enumerate(matched, start=1):
        ph_key = re.sub(r"\s+", "", ph)
        old_filename = available.get(ph) or available.get(ph_key)
        old_path = os.path.join(img_dir, old_filename)
        # 目标英文名（保留原扩展名）
        ext = os.path.splitext(old_filename)[1].lower()
        new_filename = f"img{i}{ext}"
        new_path = os.path.join(img_dir, new_filename)
        if old_path != new_path:
            if os.path.exists(new_path):
                os.remove(new_path)  # 覆盖旧残留
            os.rename(old_path, new_path)
        new_body = new_body.replace(
            f"![{ph}]()", f"![{ph}]({img_dir_name}/{new_filename})"
        )

    new_content = new_body if not content.startswith("---") else content.replace(body, new_body)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"✅ 已匹配 {len(matched)} 张并转为英文名: {', '.join(matched) if matched else '无'}")
    if missing:
        print(f"❌ 缺 {len(missing)} 张，请放入 {img_dir}/ 或选择 AI 生图:")
        for m in missing:
            print(f"   - {m}")
        return False
    print("🎉 全部占位符已配齐，可以发布")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 resolve_images.py '<文章md绝对路径>'")
        sys.exit(1)
    ok = resolve_images(sys.argv[1])
    sys.exit(0 if ok else 2)
