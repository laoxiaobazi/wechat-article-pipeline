#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公众号文章采集工具（纯Python版，无需浏览器）
支持：APPSO、硅星人、极客公园（网易号）+ 新智元（官网）

使用方法：
  1. 修改下面的 OUTPUT_DIR 为你的 Obsidian 库路径
  2. 终端运行：python3 collect_articles.py
  3. 采集结果自动保存到 输出目录/公众号采集-YYYY-MM-DD/
"""

import os
import re
import json
import time
import ssl
import urllib.request
from html.parser import HTMLParser
from datetime import datetime

# ============================================================
#  ★ 配置区（只需要改这里）
# ============================================================

# ① 输出目录：改成你的 Obsidian 库路径，例如 "/Users/xxx/Documents/MyObsidian"
OUTPUT_DIR = "/你的/Obsidian库/公众号采集流水线-分享包/00-Inbox 原始"

# ② 采集日期：默认自动取当天，格式 "YYYY-MM-DD"
#    如需补采历史日期，改成具体日期，例如 "2026-09-04"
COLLECT_DATE = datetime.now().strftime("%Y-%m-%d")

# ③ 要采集的公众号列表（添加新号只需加一行）
#    格式说明：
#      - 网易号：{"name": "公众号名", "type": "wangyi", "id": "Txxxxxxxxxx"}
#      - 新智元官网：{"name": "新智元", "type": "xinyuan"}
#    如何获取网易号ID：
#      1. 浏览器打开该公众号的网易号主页（m.163.com/news/sub/Txxx.html）
#      2. URL中 /sub/ 后面的 T 开头字符串就是 ID
ACCOUNTS = [
    {"name": "APPSO",     "type": "wangyi", "id": "T1484029335663"},
    {"name": "硅星人",     "type": "wangyi", "id": "T1506509934914"},
    {"name": "极客公园",   "type": "wangyi", "id": "T1463596751368"},
    {"name": "新智元",     "type": "xinyuan"},
    # ↓↓↓ 添加新公众号示例（取消注释并修改）↓↓↓
    # {"name": "智东西",     "type": "wangyi", "id": "T1409815021259"},
    # {"name": "脑极体",     "type": "wangyi", "id": "T1494736203795"},
    # {"name": "数据猿",     "type": "wangyi", "id": "T1644155447945"},
]

# ============================================================
#  以下为脚本逻辑，一般不需要修改
# ============================================================

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) '
                  'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
}

# 需要跳过的无关文本
SKIP_TEXTS = ['打开网易新闻', '查看精彩图片', '分享到', '扫码添加客服']


# ---------- 工具函数 ----------
def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except urllib.error.URLError as e:
        # macOS Python 未安装SSL根证书时，降级为不验证证书
        if 'CERTIFICATE_VERIFY_FAILED' in str(e):
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read().decode('utf-8', errors='replace')
        raise


def sanitize_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:80]


def get_img_ext(src):
    s = src.lower()
    if '.gif' in s: return 'gif'
    if '.png' in s: return 'png'
    if '.webp' in s: return 'webp'
    return 'jpg'


def download_image(url, filepath):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                with open(filepath, 'wb') as f:
                    f.write(resp.read())
        except urllib.error.URLError as e:
            if 'CERTIFICATE_VERIFY_FAILED' in str(e):
                ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                    with open(filepath, 'wb') as f:
                        f.write(resp.read())
            else:
                raise
        return True
    except Exception as e:
        print(f"    图片下载失败: {e}")
        return False


# ---------- 网易号：文章列表 ----------
def parse_wy_list(html):
    articles = []
    li_blocks = re.findall(r'<li[^>]*class="[^"]*news[^"]*"[^>]*>(.*?)</li>', html, re.DOTALL)
    if not li_blocks:
        li_blocks = re.findall(r'<li[^>]*>(.*?)</li>', html, re.DOTALL)

    for block in li_blocks:
        href_m = re.search(r'href="([^"]*article[^"]*)"', block)
        if not href_m:
            continue
        href = href_m.group(1)
        if href.startswith('//'):
            href = 'http:' + href
        href = href.split('?')[0]

        title_m = re.search(r'class="news-title"[^>]*>(.*?)</p>', block, re.DOTALL)
        if not title_m:
            title_m = re.search(r'<a[^>]*>(.*?)</a>', block, re.DOTALL)
        if not title_m:
            continue
        title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
        if len(title) < 8 or len(title) > 100:
            continue

        if not any(a['href'] == href for a in articles):
            articles.append({'title': title, 'href': href})

    return articles


# ---------- 网易号：正文提取 ----------
class WYArticleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.in_body = False
        self.body_depth = 0
        self.skip_tags = {'script', 'style'}
        self.skip_depth = 0
        self.publish_time = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag in self.skip_tags:
            self.skip_depth += 1
            return
        if self.skip_depth > 0:
            return
        if tag == 'time':
            dt = attrs_dict.get('datetime', '')
            if dt:
                self.publish_time = dt
        if not self.in_body and 'article-body' in attrs_dict.get('class', ''):
            self.in_body = True
            self.body_depth = 1
            return
        if self.in_body:
            self.body_depth += 1
            if tag == 'img':
                src = attrs_dict.get('data-src') or attrs_dict.get('src', '')
                src = src.split('?')[0]
                if src and 'empty.png' not in src and 'frontend/images' not in src and len(src) > 10:
                    self.items.append({'type': 'image', 'src': src})
            elif tag == 'br':
                self.items.append({'type': 'break'})

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth > 0:
            return
        if self.in_body:
            self.body_depth -= 1
            if self.body_depth <= 0:
                self.in_body = False
            elif tag in ('p', 'div', 'section', 'h1', 'h2', 'h3', 'h4', 'li', 'figure', 'blockquote'):
                self.items.append({'type': 'para_end'})

    def handle_data(self, data):
        if self.skip_depth > 0:
            return
        if self.in_body:
            text = data.strip()
            if text:
                self.items.append({'type': 'text', 'content': text})


def clean_wy_items(items):
    filtered = []
    for item in items:
        if item['type'] == 'text':
            t = item['content']
            if any(s in t for s in SKIP_TEXTS): continue
            if re.match(r'^\d{4}-\d{2}-\d{2}', t): continue
            if re.match(r'^\d+$', t) and len(t) <= 3: continue
            if t in ('·', '|', '/', '广东', '北京', '上海'): continue
            filtered.append(item)
        elif item['type'] == 'para_end':
            if filtered and filtered[-1]['type'] != 'para_end':
                filtered.append(item)
        elif item['type'] == 'image':
            if any(k in item['src'] for k in ['dingyue.ws.126.net/2026/', 'dingyue.ws.126.net/2025/', 'nimg.ws.126.net']):
                filtered.append(item)

    merged = []
    for item in filtered:
        if item['type'] == 'text' and merged and merged[-1]['type'] == 'text':
            merged[-1]['content'] += ' ' + item['content']
        else:
            merged.append(item)
    return merged


# ---------- 新智元：官网采集 ----------
def collect_xzy(target_date):
    print("[新智元] 请求 feed.json ...")
    url = f"https://www.aiera.com.cn/feed.json?t={int(time.time() * 1000)}"
    data = json.loads(http_get(url))
    print(f"[新智元] 获取到 {len(data)} 篇文章")

    # target_date 格式 "2026-09-05" → 转为 "09/05"
    md_target = target_date[5:7] + '/' + target_date[8:10]

    today_articles = []
    for aid, item in data.items():
        md = item.get('md', '')
        if md == md_target:
            today_articles.append({
                'id': aid,
                'title': item.get('t', ''),
                'paragraphs': item.get('d', []),
                'source': item.get('s', ''),
                'summary': item.get('r', ''),
                'time': f"{item.get('md', '')} {item.get('hm', '')}",
                'images': [],
            })

    print(f"[新智元] {target_date} 共 {len(today_articles)} 篇")
    return today_articles


# ---------- 网易号：完整采集 ----------
def collect_wy_account(account_name, sub_id, target_date):
    print(f"\n[{account_name}] 获取文章列表 ...")
    list_url = f"http://m.163.com/news/sub/{sub_id}.html"
    list_html = http_get(list_url)
    articles = parse_wy_list(list_html)
    print(f"[{account_name}] 列表共 {len(articles)} 篇，逐篇检查发布时间...")

    result = []
    for i, art in enumerate(articles):
        try:
            article_html = http_get(art['href'])
            parser = WYArticleParser()
            parser.feed(article_html)
            items = clean_wy_items(parser.items)

            # 用精确发布时间判断日期
            ptime = parser.publish_time
            if not ptime:
                continue
            article_date = ptime[:10]  # "2026-09-05"
            if article_date != target_date:
                continue

            images = [it['src'] for it in items if it['type'] == 'image']
            texts = [it['content'] for it in items if it['type'] == 'text']

            result.append({
                'title': art['title'],
                'href': art['href'],
                'publish_time': ptime,
                'items': items,
                'images': images,
                'word_count': sum(len(t) for t in texts),
            })
            print(f"  [{len(result)}] {ptime[11:16]} | {art['title'][:45]} | {len(images)}图")
        except Exception as e:
            print(f"  采集失败 [{art['title'][:30]}]: {e}")

    print(f"[{account_name}] {target_date} 共 {len(result)} 篇")
    return result


# ---------- Markdown 生成 ----------
def generate_wy_markdown(account, title, items, publish_time, img_prefix, article_idx):
    lines = [f"# {title}", "",
             f"**公众号：** {account}  ",
             f"**采集日期：** {COLLECT_DATE}  ",
             f"**发布时间：** {publish_time}  ",
             f"**来源：** 网易号同步发布  ",
             "", "---", ""]

    img_counter = 0
    for item in items:
        if item['type'] == 'text':
            text = item['content'].strip()
            if text:
                lines.append(text)
                lines.append("")
        elif item['type'] == 'image':
            img_counter += 1
            ext = get_img_ext(item['src'])
            img_filename = f"{img_prefix}_{article_idx:02d}_{img_counter:02d}.{ext}"
            lines.append(f"![图片{img_counter}](images/{img_filename})")
            lines.append("")
    return '\n'.join(lines), img_counter


def generate_xzy_markdown(title, paragraphs, summary, source, time_str):
    lines = [f"# {title}", "",
             f"**公众号：** 新智元  ",
             f"**采集日期：** {COLLECT_DATE}  ",
             f"**发布时间：** {time_str}  ",
             f"**来源：** {source}  ",
             "", "---", ""]
    if summary:
        lines.append(f"> {summary}")
        lines.append("")
    for p in paragraphs:
        if p.strip():
            lines.append(p.strip())
            lines.append("")
    return '\n'.join(lines)


# ---------- 主流程 ----------
def main():
    base_dir = os.path.join(OUTPUT_DIR, f"公众号采集-{COLLECT_DATE}")
    img_dir = os.path.join(base_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    account_names = [a['name'] for a in ACCOUNTS]

    print("=" * 60)
    print(f"公众号采集工具（纯Python版）")
    print(f"采集日期: {COLLECT_DATE}")
    print(f"输出目录: {base_dir}")
    print(f"采集号: {', '.join(account_names)}")
    print("=" * 60)

    all_results = []

    # 遍历配置列表，根据type采集
    for cfg in ACCOUNTS:
        name = cfg['name']
        acct_type = cfg.get('type', 'wangyi')

        if acct_type == 'wangyi':
            wy_id = cfg.get('id', '')
            if not wy_id:
                print(f"\n[{name}] 跳过：未配置网易号ID")
                continue
            articles = collect_wy_account(name, wy_id, COLLECT_DATE)
            for idx, art in enumerate(articles):
                downloaded = 0
                for img_idx, img_url in enumerate(art['images']):
                    ext = get_img_ext(img_url)
                    img_filename = f"{name}_{idx+1:02d}_{img_idx+1:02d}.{ext}"
                    img_path = os.path.join(img_dir, img_filename)
                    if download_image(img_url, img_path):
                        downloaded += 1

                md_content, _ = generate_wy_markdown(
                    name, art['title'], art['items'],
                    art['publish_time'], name, idx + 1
                )
                safe_title = sanitize_filename(art['title'])
                md_filename = f"{name}-{safe_title}.md"
                with open(os.path.join(base_dir, md_filename), 'w', encoding='utf-8') as f:
                    f.write(md_content)

                all_results.append({
                    'account': name, 'title': art['title'],
                    'images': downloaded, 'words': art['word_count'],
                    'file': md_filename, 'publish_time': art['publish_time'],
                })

        elif acct_type == 'xinyuan':
            xzy_articles = collect_xzy(COLLECT_DATE)
            for art in xzy_articles:
                md_content = generate_xzy_markdown(
                    art['title'], art['paragraphs'], art['summary'], art['source'], art['time']
                )
                safe_title = sanitize_filename(art['title'])
                md_filename = f"{name}-{safe_title}.md"
                with open(os.path.join(base_dir, md_filename), 'w', encoding='utf-8') as f:
                    f.write(md_content)

                word_count = sum(len(p) for p in art['paragraphs'])
                all_results.append({
                    'account': name, 'title': art['title'],
                    'images': 0, 'words': word_count,
                    'file': md_filename, 'publish_time': art['time'],
                })

        else:
            print(f"\n[{name}] 跳过：不支持的采集类型 '{acct_type}'")

    # 生成汇总表
    summary_path = os.path.join(base_dir, "汇总表.md")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(f"# 公众号采集汇总表 - {COLLECT_DATE}\n\n")
        f.write(f"**采集时间：** {datetime.now().strftime('%Y-%m-%d %H:%M')}  \n")
        f.write(f"**采集范围：** {COLLECT_DATE} 当天发布的文章  \n")
        f.write(f"**采集公众号：** {'、'.join(account_names)}  \n")
        f.write(f"**文章总数：** {len(all_results)} 篇  \n")
        f.write(f"**图片总数：** {sum(r['images'] for r in all_results)} 张  \n\n")
        f.write("---\n\n## 采集明细\n\n")
        f.write("| 序号 | 公众号 | 文章标题 | 字数 | 图片数 | 发布时间 |\n")
        f.write("|------|--------|----------|------|--------|----------|\n")
        for i, r in enumerate(all_results):
            short = r['title'][:40] + ('...' if len(r['title']) > 40 else '')
            f.write(f"| {i+1} | {r['account']} | {short} | {r['words']} | {r['images']} | {r['publish_time'][:16]} |\n")

        f.write("\n---\n\n## 各号更新情况\n\n")
        f.write("| 公众号 | 今日文章数 | 状态 |\n|--------|-----------|------|\n")
        counts = {}
        for r in all_results:
            counts[r['account']] = counts.get(r['account'], 0) + 1
        for acc in account_names:
            c = counts.get(acc, 0)
            f.write(f"| {acc} | {c} | {'已更新' if c > 0 else '今日无更新'} |\n")

    print("\n" + "=" * 60)
    print(f"采集完成！共 {len(all_results)} 篇，{sum(r['images'] for r in all_results)} 张图")
    print(f"输出目录: {base_dir}")
    print("=" * 60)


if __name__ == '__main__':
    main()
