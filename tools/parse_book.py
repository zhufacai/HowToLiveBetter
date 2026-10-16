#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把《高性价比人生指南》仓库 book/ 下 34 个 Markdown 文件解析成小程序可用的结构化数据。

输出：
  miniprogram/data/meta.json         版本信息
  miniprogram/data/items-index.json 轻量索引（主包用，列表/搜索/筛选）
  miniprogram/data/chapters/NN.json 每章全量字段（分包按需加载）

设计要点：
  - 保留「成本标签」注释里的五个维度（钱/时间/毅力/收益/口径），这是原书最被低估的筛选入口
  - 来源字段拆出 url + 文字，供小程序「复制链接」
  - 正文里的「见第 X 节第 Y 条」原样保留，并在 refs 里给出可跳转的 id，前端渲染成可点链接
  - 不改动任何正文字，下游怎么渲染由小程序决定
"""

import json
import os
import re
import glob

# 仓库 book 目录（相对本脚本：tools/ 的上一级）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK_DIR = os.path.join(ROOT, "HowToLiveBetter-main", "book")
# 轻量索引与元信息放主包
DATA_DIR = os.path.join(ROOT, "miniprogram", "data")
# 章节全量数据放分包（pagesA），主包不得引用分包文件
CHAPTER_DIR = os.path.join(ROOT, "miniprogram", "pagesA", "data", "chapters")
VERSION = "2026-10-13"  # 本地包日期，作为数据版本号

# 条目切分：### 1. 标题
ITEM_RE = re.compile(r"^###\s+(\d+)\.\s+(.+)$", re.M)
# 成本标签注释
COST_RE = re.compile(
    r"成本标签:\s*钱=(\S+)\s*时间=(\S+)\s*毅力=(\S+)\s*收益=(\S+)\s*口径=(\S+)"
)
# 单字段提取：从 "- 字段：" 到下一个 "- 字段：" 或结尾
FIELD_KEYS = ["成本", "说人话", "收益", "证据等级", "来源", "备注"]
FIELD_RE = re.compile(
    # 2026-10-16：终结条件补 \n#{2,3}\s——末条目的末字段原来一路吃到文件尾，
    # 把章尾的「## 许可」等整节吞进字段（线上 26-13 备注即此故障，含换行符，
    # 端上渲染时把引用链接挤到下一行）。遇到 ## / ### 标题行即止。
    r"\n-\s*(成本|说人话|收益|证据等级|来源|备注)[:：]\s*(.*?)(?=\n-\s*(?:成本|说人话|收益|证据等级|来源|备注)[:：]|\n#{2,3}\s|\Z)",
    re.S,
)
# 来源中的 url
URL_RE = re.compile(r"https?://\S+")
# 交叉引用：见第 X 节第 Y 条
REF_RE = re.compile(r"见第\s*(\d+)\s*节第\s*(\d+)\s*条")


def parse_chapter_file(path):
    fname = os.path.basename(path)
    # NN-标题.md
    m = re.match(r"^(\d+)-(.*)\.md$", fname)
    if not m:
        return None
    chapter_no = int(m.group(1))
    chapter_title = m.group(2)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    items = []
    # 按条目切分，保留每个块
    matches = list(ITEM_RE.finditer(text))
    for i, mt in enumerate(matches):
        seq = int(mt.group(1))
        title = mt.group(2).strip()
        start = mt.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]

        # 成本标签
        cm = COST_RE.search(block)
        cost = {}
        if cm:
            cost = {
                "money": cm.group(1),
                "time": cm.group(2),
                "will": cm.group(3),
                "benefit": cm.group(4),
                "caliber": cm.group(5),
            }

        # 各字段
        fields = {}
        for fm in FIELD_RE.finditer(block):
            fields[fm.group(1)] = fm.group(2).strip()

        # 来源拆 url
        src_raw = fields.get("来源", "")
        sources = []
        for url in URL_RE.findall(src_raw):
            # 去掉尖括号包裹
            clean = url.strip("<>")
            # 取该 url 前一个分隔符前的文字作为说明
            sources.append({"url": clean, "text": src_raw})
        # 去重（多 url 时 text 相同，只保留 url 不同）
        seen = set()
        uniq_sources = []
        for s in sources:
            if s["url"] not in seen:
                seen.add(s["url"])
                uniq_sources.append({"url": s["url"], "text": s["text"]})

        plain = fields.get("说人话", "")
        detail = fields.get("收益", "")
        note = fields.get("备注", "")

        refs = []
        for rm in REF_RE.finditer(plain + " " + detail + " " + note):
            refs.append(f"{rm.group(1)}-{rm.group(2)}")

        item = {
            "id": f"{chapter_no}-{seq}",
            "chapter": chapter_no,
            "chapterTitle": chapter_title,
            "seq": seq,
            "title": title,
            "cost": cost,
            "costText": fields.get("成本", ""),
            "plain": plain,
            "detail": detail,
            "evidence": fields.get("证据等级", ""),
            "sources": uniq_sources,
            "sourceRaw": src_raw,
            "note": note,
            "refs": refs,
        }
        items.append(item)

    return {
        "chapter": chapter_no,
        "chapterTitle": chapter_title,
        "count": len(items),
        "items": items,
    }


def main():
    files = sorted(glob.glob(os.path.join(BOOK_DIR, "*.md")))
    total = 0
    chapters = []
    index = []
    missing_cost = 0
    missing_evidence = 0
    no_ref_target = 0

    os.makedirs(CHAPTER_DIR, exist_ok=True)

    for path in files:
        ch = parse_chapter_file(path)
        if not ch:
            continue
        chapters.append(ch)
        total += ch["count"]
        for it in ch["items"]:
            if not it["cost"]:
                missing_cost += 1
            if not it["evidence"]:
                missing_evidence += 1
            # 索引：轻量
            index.append(
                {
                    "id": it["id"],
                    "chapter": it["chapter"],
                    "seq": it["seq"],
                    "chapterTitle": it["chapterTitle"],
                    "title": it["title"],
                    "cost": it["cost"],
                    "evidence": it["evidence"],
                }
            )
        # 写章节文件（分包内，导出为 .js 模块，避免微信 require 不支持 .json 扩展名的问题）
        out_path = os.path.join(CHAPTER_DIR, f"{ch['chapter']:02d}.js")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("module.exports = ")
            json.dump(ch, f, ensure_ascii=False, indent=1)
            f.write(";\n")

    meta = {
        "version": VERSION,
        "updatedAt": VERSION,
        "count": total,
        "chapters": len(chapters),
        "source": "HowToLiveBetter-main",
        "note": "CC BY 4.0，原作者 eternity4719；本数据随上游更新需重新生成。",
    }
    with open(os.path.join(DATA_DIR, "meta.js"), "w", encoding="utf-8") as f:
        f.write("module.exports = ")
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write(";\n")
    with open(os.path.join(DATA_DIR, "items-index.js"), "w", encoding="utf-8") as f:
        f.write("module.exports = ")
        json.dump(index, f, ensure_ascii=False, indent=1)
        f.write(";\n")

    # 第 13 章紧急情况离线保底副本，放在主包，供 tabBar 应急页直接读取
    em_ch = next((c for c in chapters if c["chapter"] == 13), None)
    if em_ch:
        with open(os.path.join(DATA_DIR, "emergency.js"), "w", encoding="utf-8") as f:
            f.write("module.exports = ")
            json.dump(em_ch, f, ensure_ascii=False, indent=1)
            f.write(";\n")

    print(f"章节数：{len(chapters)}")
    print(f"总条目：{total}")
    print(f"缺成本标签：{missing_cost}")
    print(f"缺证据等级：{missing_evidence}")
    print(f"索引条数：{len(index)}")
    print(f"章节输出目录：{CHAPTER_DIR}")
    print(f"主包数据目录：{DATA_DIR}")


if __name__ == "__main__":
    main()
