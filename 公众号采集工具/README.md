---
title: 采集说明
type: 项目
role: 其他
status: 进行中
tags:
  - 爬取
---

# 公众号文章采集工具

纯 Python 脚本，无需浏览器、无需安装第三方库，开箱即用。

## 支持的公众号

| 公众号 | 来源 | 图片 |
|--------|------|------|
| APPSO | 网易号 | ✅ |
| 硅星人 | 网易号 | ✅ |
| 极客公园 | 网易号 | ✅ |
| 新智元 | 官网（秒追ASI） | 短资讯无图 |

## 环境要求

- macOS / Windows / Linux 均可
- Python 3.6+（macOS 自带，Windows 需安装）
- 无需 pip install 任何东西

## 使用方法（3步）

### 第1步：修改输出路径

用文本编辑器打开 `collect_articles.py`，找到顶部的配置区，修改 `OUTPUT_DIR`：

```python
# ① 输出目录：改成你的 Obsidian 库路径
OUTPUT_DIR = "/Users/你的名字/Documents/MyObsidian/00_收集"
```

- macOS 示例：`"/Users/zhangsan/Documents/Obsidian库/00_收集"`
- Windows 示例：`"C:/Users/zhangsan/Documents/Obsidian库/00_收集"`（注意用正斜杠 `/`）

### 第2步：运行脚本

打开终端（macOS：启动台 → 其他 → 终端），进入脚本所在目录，运行：

```bash
cd ~/Desktop/Laoxiaobazi/scripts/公众号采集工具
python3 collect_articles.py
```

或

```
python3 ~/Desktop/Laoxiaobazi/scripts/公众号采集工具/collect_articles.py
```

Windows 用户如果 `python3` 不行，试试 `python collect_articles.py`。

### 第3步：查看结果

采集完成后，在你的 Obsidian 库中会出现：

```
00_收集/
└── 公众号采集-2026-09-05/          ← 以采集日期命名
    ├── 汇总表.md                      ← 当天采集总览
    ├── APPSO-文章标题1.md             ← 每篇文章一个md
    ├── APPSO-文章标题2.md
    ├── 硅星人-文章标题.md
    ├── 极客公园-文章标题.md
    ├── 新智元-文章标题.md
    └── images/                        ← 所有图片统一放这里
        ├── APPSO_01_01.jpg
        ├── APPSO_01_02.jpg
        └── ...
```

在 Obsidian 中打开任意一篇 `.md`，图片会自动渲染显示。

## 配置说明

脚本顶部有3个可配置项：

```python
# ① 输出目录（必改）
OUTPUT_DIR = "/你的/Obsidian/库路径/00_收集"

# ② 采集日期（默认当天，补采历史时修改）
COLLECT_DATE = "2026-09-05"

# ③ 要采集的公众号列表（可自由增删，添加新号只需加一行）
ACCOUNTS = [
    {"name": "APPSO",     "type": "wangyi", "id": "T1484029335663"},
    {"name": "硅星人",     "type": "wangyi", "id": "T1506509934914"},
    {"name": "极客公园",   "type": "wangyi", "id": "T1463596751368"},
    {"name": "新智元",     "type": "xinyuan"},
]
```

|公众号|网易号媒体 ID|
|---|---|
|APPSO|T1484029335663|
|硅星人|T1506509934914|
|数字生命卡兹克|T1677946819646|
|极客公园|T1463596751368|
|脑极体|T1494736203795|
|智东西|T1409815021259|
|数据猿|T1644155447945|
|Founder Park|T1705485947430|
|优设 AIGC|T1473846008574|
### 补采历史日期

把 `COLLECT_DATE` 改成目标日期即可，例如：
```python
COLLECT_DATE = "2026-09-04"
```

### 添加新的公众号

**如果该公众号有网易号**（大部分科技类公众号都有），只需在 `ACCOUNTS` 列表中加一行：

```python
{"name": "公众号名字", "type": "wangyi", "id": "Txxxxxxxxxx"},
```

**如何获取网易号 ID：**
1. 浏览器打开该公众号的网易号主页，URL 格式为 `https://m.163.com/news/sub/Txxxxxxxxxx.html`
2. URL 中 `/sub/` 后面的 `T` 开头字符串就是 ID
3. 或者在网易号文章页，点击作者头像/名字进入主页，看地址栏

**删除/暂停公众号：** 删掉对应行，或在前面加 `#` 注释掉。

### 支持的采集类型

| type | 说明 | 需要的字段 |
|------|------|-----------|
| `wangyi` | 网易号同步发布 | `name`, `id`（网易号订阅页ID） |
| `xinyuan` | 新智元官网秒追ASI | `name`（不需要id） |

## 常见问题

**Q：运行报错 `No module named 'xxx'`？**
A：本脚本只用 Python 标准库，不需要安装任何第三方库。如果报错，检查 Python 版本是否为 3.6+。

**Q：图片不显示？**
A：确认 `.md` 文件和 `images/` 文件夹在同一级目录下，markdown 中的图片路径是 `images/xxx.jpg`（相对路径）。

**Q：新智元的文章很短、没有图？**
A：新智元官网首页是"秒追 ASI"短资讯流（每天10-20条，每条几百字），属于快讯类内容。如果需要深度长文，可以后续扩展采集"ASI 启示录"频道。

**Q：能加其他公众号吗？**
A：可以。大部分科技类公众号都有网易号同步发布，只需在 `ACCOUNTS` 列表中加一行 `{"name": "公众号名", "type": "wangyi", "id": "Txxx"}` 即可。如果是其他平台（非网易号、非新智元），需要单独写采集逻辑。

**Q：运行报错 `SSL: CERTIFICATE_VERIFY_FAILED`？**
A：这是 macOS 上 Python 的常见问题（未安装 SSL 根证书）。本脚本已内置容错处理，遇到此错误会自动降级为不验证证书，不影响正常使用。如果想彻底解决，可运行：
```bash
/Applications/Python 3.11/Install Certificates.command
```
（路径中的 3.11 替换为你实际的 Python 版本）

**Q：会不会被封IP？**
A：本脚本请求频率很低（每篇文章间隔自然处理时间），正常使用不会被封。如果一次性采集大量历史文章，建议在请求之间加 `time.sleep(1)`。

## 文件说明

```
公众号采集工具/
├── collect_articles.py    ← 主脚本（唯一需要的文件）
└── README.md               ← 本说明文件
```

只需要把 `collect_articles.py` 发给朋友，改个路径就能用。
