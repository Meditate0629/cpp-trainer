# -*- coding: utf-8 -*-
r"""下载 w64devkit（C++ 编译工具链）。

为什么用 Python 而不是 curl/PowerShell：
  这台机器上 curl 报 `schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS`，
  PowerShell 的 Invoke-WebRequest 报 "The SSL connection could not be established"。
  两者都走 Windows Schannel，在沙箱里拿不到凭证。
  Python 的 ssl 走 OpenSSL + 自带 CA，绕开这个问题。

用法：python 下载编译器.py
产物：工具\_dl\w64devkit-x64-<版本>.zip
"""

import io
import json
import os
import ssl
import sys
import urllib.request

API = "https://api.github.com/repos/skeeto/w64devkit/releases/latest"
HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "_dl")

# 直连 GitHub 只有 0.05 MB/s（实测），这些镜像快得多，按顺序试
MIRRORS = [
    "https://gh-proxy.com/",     # 实测 3.27 MB/s
    "https://ghfast.top/",       # 实测 0.19 MB/s
    "",                          # 直连，兜底
]


def open_url(url, extra_headers=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; w64devkit-fetch)",
        "Accept": "application/vnd.github+json",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    return urllib.request.urlopen(req, timeout=120, context=ctx)


def download(url, dst, size, tries=8):
    """带断点续传的下载（GitHub 大文件经常中途被重置）。"""
    for attempt in range(1, tries + 1):
        have = os.path.getsize(dst) if os.path.exists(dst) else 0
        if have >= size:
            return True
        headers = {"Range": "bytes=%d-" % have} if have else None
        try:
            with open_url(url, headers) as r:
                # 服务端如果不认 Range 会返回 200 而不是 206，此时必须从头写，否则拼出坏文件
                if have and getattr(r, "status", 200) != 206:
                    print("\n  服务端不支持断点续传，从头开始")
                    have = 0
                    fh = open(dst, "wb")
                else:
                    fh = open(dst, "ab")
                with fh:
                    while True:
                        chunk = r.read(1024 * 256)
                        if not chunk:
                            break
                        fh.write(chunk)
                        have += len(chunk)
                        sys.stdout.write("\r  进度 %5.1f%%  %.1f/%.1f MB (第 %d 次尝试)"
                                         % (have * 100.0 / size, have / 1048576.0,
                                            size / 1048576.0, attempt))
                        sys.stdout.flush()
            print("")
        except Exception as e:
            print("\n  第 %d 次中断: %s" % (attempt, e))
        if os.path.exists(dst) and os.path.getsize(dst) >= size:
            return True
    return False


def main():
    os.makedirs(DEST, exist_ok=True)

    print("查询最新版本 ...")
    with open_url(API) as r:
        rel = json.load(r)
    tag = rel["tag_name"]
    print("最新版本: %s" % tag)

    names = [a["name"] for a in rel["assets"]]
    print("资源列表: %s" % ", ".join(names))

    pick = None
    for a in rel["assets"]:
        n = a["name"]
        if n.startswith("w64devkit-x64-") and n.endswith(".zip"):
            pick = a
            break
    if pick is None:
        for a in rel["assets"]:
            n = a["name"]
            if n.startswith("w64devkit-x64-") and n.endswith(".7z.exe"):
                pick = a
                break
    if pick is None:
        print("!! 没找到 x64 的 zip/7z.exe 资源")
        return 1

    url, name, size = pick["browser_download_url"], pick["name"], pick["size"]
    dst = os.path.join(DEST, name)

    if os.path.exists(dst) and os.path.getsize(dst) == size:
        print("已存在且大小一致，跳过下载: %s" % dst)
        return 0

    print("目标 %s  (%.1f MB)" % (name, size / 1024.0 / 1024.0))

    for m in MIRRORS:
        label = m or "直连 GitHub"
        print("--- 尝试 %s ---" % label)
        if download(m + url, dst, size):
            got = os.path.getsize(dst)
            print("完成: %s  (%d 字节)" % (dst, got))
            if got != size:
                print("!! 大小不符，期望 %d" % size)
                return 1
            return 0
        print("   %s 没成功，换下一个源" % label)

    print("!! 所有源都失败")
    return 1


if __name__ == "__main__":
    sys.exit(main())
