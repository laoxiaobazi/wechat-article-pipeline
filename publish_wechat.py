#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号草稿箱发布工具
功能：把 15-Published 发布/ 下的成稿 markdown 推送到微信公众号草稿箱

用法：
  python3 publish_wechat.py                    # 发布 15-Published 发布/ 下所有待发文章
  python3 publish_wechat.py "文章标题"          # 只发布指定标题的文章
  python3 publish_wechat.py --test             # 只测试 API 凭证是否可用（获取 access_token）

依赖：
  凭证放同目录 .env 文件：
    WECHAT_APPID=...
    WECHAT_APPSECRET=...
  图片：文章内引用 15-Published 发布/images/ 下的本地图片
"""

import os
import sys
import json
import time
import glob
import re
import urllib.request
import urllib.parse
import ssl

# ============================================================
#  ★ 配置区
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLISH_DIR = os.path.join(BASE_DIR, "15-Published 发布")
ENV_FILE = os.path.join(BASE_DIR, ".env")

# 公众号接口域名
API_BASE = "https://api.weixin.qq.com/cgi-bin"


# ============================================================
#  工具函数
# ============================================================

def load_env():
    """从 .env 读取凭证"""
    env = {}
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def http_request(url, data=None, timeout=30):
    """HTTP 请求，带 SSL 容错（macOS Python 常见证书问题）"""
    req = urllib.request.Request(url, data=data)
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
    if data:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except ssl.SSLCertVerificationError:
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode("utf-8")


def get_access_token(appid, appsecret):
    """获取 access_token"""
    url = f"{API_BASE}/token?grant_type=client_credential&appid={appid}&secret={appsecret}"
    resp = json.loads(http_request(url))
    if "access_token" in resp:
        return resp["access_token"]
    raise RuntimeError(f"获取 access_token 失败: {resp}")


def upload_image(access_token, image_path, is_cover=False):
    """上传图片，返回 media_id。is_cover=True 用永久素材(封面)，否则用临时素材(正文)"""
    import mimetypes
    mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"

    if is_cover:
        # 永久素材（图文封面）
        url = f"{API_BASE}/material/add_material?access_token={access_token}&type=image"
    else:
        # 临时素材（正文插图，有效期3天）
        url = f"{API_BASE}/media/uploadimg?access_token={access_token}"

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    filename = os.path.basename(image_path)
    with open(image_path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except ssl.SSLCertVerificationError:
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))

    if "media_id" in result or "url" in result:
        return result
    raise RuntimeError(f"上传图片失败 {image_path}: {result}")


def upload_cover_material(access_token, image_path):
    """上传永久图片素材（用于封面），返回 media_id"""
    return upload_image(access_token, image_path, is_cover=True)


def md_to_html(md_text, img_map=None, base_dir=None):
    """简单把 markdown 正文转 HTML（够用于公众号：标题/段落/加粗/图片/列表/链接）
    img_map: {本地图片路径: 微信可访问URL}，图片 src 优先使用映射值
    base_dir: md 文件所在目录，用于把相对路径图片解析为绝对路径做映射查找"""
    import html as html_mod

    img_map = img_map or {}
    lines = md_text.split("\n")
    html_parts = []
    in_list = False
    in_code = False
    code_buf = []

    def close_list():
        nonlocal in_list
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    for line in lines:
        line = line.rstrip()

        # 代码块
        if line.strip().startswith("```"):
            if in_code:
                html_parts.append("<pre><code>" + html_mod.escape("\n".join(code_buf)) + "</code></pre>")
                code_buf = []
                in_code = False
            else:
                close_list()
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue

        s = line.strip()

        # 空行
        if not s:
            close_list()
            continue

        # 标题
        m = re.match(r"^(#{1,4})\s+(.*)", s)
        if m:
            close_list()
            level = len(m.group(1))
            text = html_mod.escape(m.group(2))
            text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
            html_parts.append(f"<h{level}>{text}</h{level}>")
            continue

        # 图片
        m = re.match(r"!\[(.*?)\]\((.*?)\)", s)
        if m:
            close_list()
            local_path = m.group(2)
            # 图片 src 优先用映射后的微信URL（支持相对/绝对两种key），找不到则本地绝对路径
            abs_path = os.path.join(base_dir, local_path) if base_dir and not os.path.isabs(local_path) else local_path
            src = img_map.get(local_path) or img_map.get(abs_path, local_path)
            if abs_path in img_map:
                src = img_map[abs_path]
            html_parts.append(f'<p><img src="{src}" alt="{m.group(1)}"></p>')
            continue

        # 列表
        m = re.match(r"^[-*]\s+(.*)", s)
        if m:
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            text = html_mod.escape(m.group(1))
            text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
            html_parts.append(f"<li>{text}</li>")
            continue

        # 普通段落
        close_list()
        text = html_mod.escape(s)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        html_parts.append(f"<p>{text}</p>")

    close_list()
    if in_code:
        html_parts.append("<pre><code>" + html_mod.escape("\n".join(code_buf)) + "</code></pre>")

    return "\n".join(html_parts)


def parse_md(filepath):
    """解析成稿 md：frontmatter(title/author/summary) + 正文 + 图片列表"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    meta = {"title": "", "author": "一号设计", "summary": ""}
    body = content

    # 解析 frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            for line in fm.strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
            body = parts[2]

    # 剔除辅助区块（仅供用户审阅，不进公众号正文）：
    # 正文在「备选标题 / 图位清单 / 来源说明」任一二级标题处截止
    aux_cut = re.search(r"^#{1,4}\s*(备选标题|图位清单|来源说明)\s*$", body, re.M)
    if aux_cut:
        body = body[: aux_cut.start()]
    # 去掉正文末尾残留的分隔线/空行
    body = re.sub(r"\n---+\s*$", "", body).rstrip()

    title = meta.get("title") or os.path.basename(filepath).replace(".md", "")
    summary = meta.get("summary", "")
    author = meta.get("author", "一号设计")

    # 收集本地图片
    images = re.findall(r"!\[.*?\]\(([^)]+\.(?:png|jpg|jpeg|gif|webp))\)", body, re.I)
    local_images = []
    for img in images:
        p = img
        if not os.path.isabs(p):
            p = os.path.join(os.path.dirname(filepath), p)
        if os.path.exists(p):
            local_images.append(p)

    # 防呆：检测未配图的占位符 ![xxx]()（空链接）
    placeholders = re.findall(r"!\[([^\]]*)\]\(\)", body)
    if placeholders:
        missing = [f"图{i+1}: {t}" for i, t in enumerate(placeholders)]
        raise RuntimeError(
            "文章存在未配图占位符，拒绝发布。缺图清单：\n  "
            + "\n  ".join(missing)
            + "\n请先完成配图（手动放入 images-{标题}/ 或选择 AI 生图），再重新发布。"
        )

    return {"title": title, "author": author, "summary": summary, "body": body, "images": local_images}


def create_draft(access_token, articles):
    """创建草稿（不群发）"""
    url = f"{API_BASE}/draft/add?access_token={access_token}"
    payload = {"articles": articles}
    resp = json.loads(http_request(url, json.dumps(payload, ensure_ascii=False).encode("utf-8")))
    return resp


def find_articles():
    """查找待发布的成稿 md（支持 15-Published 发布/{日期}/*.md 递归结构）

    排除辅助文件：写作信息-*.md（备选标题/图位清单/来源说明，仅供审阅，不进公众号）
    """
    if not os.path.isdir(PUBLISH_DIR):
        raise RuntimeError(f"发布目录不存在: {PUBLISH_DIR}")
    files = glob.glob(os.path.join(PUBLISH_DIR, "**", "*.md"), recursive=True)
    return sorted(f for f in files if not os.path.basename(f).startswith("写作信息-"))


# ============================================================
#  主流程
# ============================================================

def main():
    env = load_env()
    appid = env.get("WECHAT_APPID", "")
    appsecret = env.get("WECHAT_APPSECRET", "")
    if not appid or not appsecret:
        print("❌ 缺少凭证：请在 .env 中配置 WECHAT_APPID 和 WECHAT_APPSECRET")
        sys.exit(1)

    print(f"[公众号] 获取 access_token ...")
    token = get_access_token(appid, appsecret)
    print(f"✅ access_token 获取成功（前20位: {token[:20]}...）")

    # 测试模式
    if "--test" in sys.argv:
        print("✅ API 凭证可用")
        return

    # 指定标题过滤
    filter_title = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            filter_title = arg

    articles_files = find_articles()
    if filter_title:
        articles_files = [f for f in articles_files if filter_title in os.path.basename(f)]

    if not articles_files:
        print(f"❌ 没有找到待发布文章（目录: {PUBLISH_DIR}）")
        sys.exit(1)

    articles = []
    for af in articles_files:
        print(f"\n[解析] {os.path.basename(af)}")
        md = parse_md(af)

        # 1. 上传封面（取第一张图作为封面）
        cover_media_id = ""
        if md["images"]:
            cover_result = upload_cover_material(token, md["images"][0])
            cover_media_id = cover_result.get("media_id", "")
            print(f"  ✅ 封面已上传: {os.path.basename(md['images'][0])}")

        # 2. 先上传全部正文图片，建立 本地路径→微信URL 映射
        img_map = {}
        md_dir = os.path.dirname(af)  # md 所在目录（日期子文件夹）
        for img_path in md["images"]:
            up_result = upload_image(token, img_path)
            img_url = up_result.get("url", "")
            if img_url:
                img_map[img_path] = img_url
                # md 内引用的是相对路径（如 images-文章名/xxx.jpg），一并映射
                rel = os.path.relpath(img_path, md_dir)
                img_map[rel] = img_url
                print(f"  ✅ 正文图片已上传: {os.path.basename(img_path)}")

        # 3. 转换 HTML 时直接用微信 URL（避免本地路径残留）
        body_html = md_to_html(md["body"], img_map, base_dir=md_dir)

        articles.append({
            "title": md["title"],
            "author": md["author"],
            "digest": md["summary"][:120] if md["summary"] else "",
            "content": body_html,
            "thumb_media_id": cover_media_id,
            "need_open_comment": 1,
            "only_fans_can_comment": 0,
        })

    print(f"\n[草稿箱] 创建草稿（{len(articles)} 篇）...")
    resp = create_draft(token, articles)
    if "media_id" in resp:
        print(f"✅ 草稿创建成功！media_id: {resp['media_id']}")
        print("   请到公众号后台 → 草稿箱 查看并确认发布。")
    else:
        print(f"❌ 创建草稿失败: {resp}")


if __name__ == "__main__":
    main()
