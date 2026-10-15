#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 build_dist.py 生成的 dist/ 目录上传到腾讯云 COS，全部设为公开读。
环境变量（在 GitHub Secrets 中配置）：
  COS_SECRET_ID    子账号 SecretId
  COS_SECRET_KEY   子账号 SecretKey
  COS_BUCKET       桶名，例如 htlb-data-1251500892
  COS_REGION       地域，例如 ap-guangzhou（默认）
  COS_PREFIX       上传路径前缀，默认 data（即 data/meta.json 等）
用法：
  python tools/upload_cos.py --dist dist
"""
import os
import sys
from qcloud_cos import CosConfig, CosS3Client


def upload(dist_dir):
    sid = os.environ["COS_SECRET_ID"]
    skey = os.environ["COS_SECRET_KEY"]
    region = os.environ.get("COS_REGION", "ap-guangzhou")
    bucket = os.environ["COS_BUCKET"]
    prefix = os.environ.get("COS_PREFIX", "data").strip("/")

    config = CosConfig(Region=region, SecretId=sid, SecretKey=skey)
    client = CosS3Client(config)

    # 确保桶公开读（幂等）
    try:
        client.put_bucket_acl(Bucket=bucket, ACL="public-read")
    except Exception as e:
        print("WARN put_bucket_acl:", e)

    # 收集全部待上传文件，按「章节 → 索引 → meta」的顺序传：
    # meta.json 是小程序端的版本开关，必须最后一个落。若中途失败
    # （网络抖、密钥过期），版本号不变，端上继续用旧数据自洽，下次
    # 重传自动修复；否则 meta 已覆盖而后半截章节还是旧内容，端上按
    # 新版本全量拉取会得到半新半旧的数据，且永不自愈（版本号已最新，
    # 之后每次同步都判定无需更新）。items-index.json 排在 meta 之前、
    # 章节之后：它先落地无害——端上只在版本号变化时才拉新 index。
    entries = []
    for root, _, files in os.walk(dist_dir):
        for fname in files:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, dist_dir).replace("\\", "/")
            entries.append((rel, full))

    def upload_order(item):
        rel = item[0]
        if rel == "meta.json":
            return (2, rel)
        if rel == "items-index.json":
            return (1, rel)
        return (0, rel)

    entries.sort(key=upload_order)

    n = 0
    for rel, full in entries:
        key = prefix + "/" + rel
        with open(full, "rb") as fh:
            body = fh.read()
        client.put_object(
            Bucket=bucket,
            Body=body,
            Key=key,
            ACL="public-read",
            ContentType="application/json; charset=utf-8",
        )
        n += 1
        print(f"PUT {key} ({len(body)} bytes)")
    print(f"UPLOADED {n} files to {bucket}/{prefix}/")
    return n


if __name__ == "__main__":
    dist = "dist"
    if "--dist" in sys.argv:
        dist = sys.argv[sys.argv.index("--dist") + 1]
    upload(dist)
