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

    n = 0
    for root, _, files in os.walk(dist_dir):
        for fname in sorted(files):
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, dist_dir).replace("\\", "/")
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
