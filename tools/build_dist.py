#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从《高性价比人生指南》上游仓库的 book/ 目录重新解析，生成小程序可用的 JSON 分发文件：
  dist/meta.json          版本信息（版本号 = 上游 book/ 最近提交日期，内容不变则版本不变）
  dist/items-index.json   轻量索引
  dist/chapters/NN.json   每章全量字段

复用同目录 parse_book.py 的解析逻辑（解析规则保持一致）。
用法：
  python tools/build_dist.py --book /path/to/HowToLiveBetter/book --out dist
"""
import json
import os
import glob
import sys
import subprocess
import datetime

# 让本脚本能直接 import 同目录的 parse_book
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_book  # noqa: E402


def version_from_git(book_dir):
    """版本号取上游 book/ 目录最近一次提交的日期（YYYY-MM-DD）。"""
    repo = os.path.dirname(os.path.dirname(book_dir))  # book_dir/.. 即仓库根
    try:
        out = subprocess.check_output(
            ["git", "-C", repo, "log", "-1", "--format=%Y-%m-%d", "--", "book/"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip() or None
    except Exception:
        return None


def build(book_dir, out_dir):
    files = sorted(glob.glob(os.path.join(book_dir, "*.md")))
    chapters = []
    index = []
    total = 0
    for path in files:
        ch = parse_book.parse_chapter_file(path)
        if not ch:
            continue
        chapters.append(ch)
        total += ch["count"]
        for it in ch["items"]:
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

    version = version_from_git(book_dir) or datetime.date.today().isoformat()
    meta = {
        "version": version,
        "updatedAt": version,
        "count": total,
        "chapters": len(chapters),
        "source": "HowToLiveBetter",
        "note": "CC BY 4.0，原作者 eternity4719；本数据由 GitHub Actions 自动从上游仓库重新生成。",
    }

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "items-index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)

    ch_dir = os.path.join(out_dir, "chapters")
    os.makedirs(ch_dir, exist_ok=True)
    for ch in chapters:
        with open(os.path.join(ch_dir, f"{ch['chapter']:02d}.json"), "w", encoding="utf-8") as f:
            json.dump(ch, f, ensure_ascii=False, indent=1)

    print(f"BUILT chapters={len(chapters)} items={total} version={version}")
    print(f"OUTPUT={os.path.abspath(out_dir)}")
    return meta


if __name__ == "__main__":
    book = "HowToLiveBetter-main/book"
    out = "dist"
    if "--book" in sys.argv:
        book = sys.argv[sys.argv.index("--book") + 1]
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    build(book, out)
