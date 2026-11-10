#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""计算概论 · 训练场（仿 LeetCode 的本地刷题网站，零依赖，只给自己用）

特点：
  * 不用注册、不用登录，打开就能刷（单机，只监听 127.0.0.1）
  * 代码就存在 练习\ 下（VS Code 能直接打开同一份文件）
  * 进度写回 进度追踪表.csv（每次改动自动备份）
  * 判题支持 C++ 17 和 Python 3

依赖：Python 标准库 + 系统里的 g++ / python3。不需要 pip、不需要联网。

启动：双击 启动网站.cmd，或  python server.py
"""

import csv
import datetime
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

# ---------------------------------------------------------------- 路径
APP_DIR = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.dirname(APP_DIR)
PRACTICE = os.path.join(BANK, "练习")
TESTS = os.path.join(BANK, "测试数据")
REPO = os.path.join(BANK, "IntroductionToComputationHomework2022-master")
CSV_PATH = os.path.join(BANK, "进度追踪表.csv")
CSV_TEMPLATE = os.path.join(BANK, "进度追踪表.模板.csv")   # 进度表缺失时用它生成

WEB_DIR = os.path.join(APP_DIR, "web")
RUNS = os.path.join(APP_DIR, "运行")
REF_CACHE = os.path.join(RUNS, "_参考解缓存")
BACKUP_DIR = os.path.join(APP_DIR, "备份")
CORR_PATH = os.path.join(APP_DIR, "题目校正.json")
HISTORY_PATH = os.path.join(APP_DIR, "提交记录.jsonl")

HOST = os.environ.get("TS_HOST") or "127.0.0.1"      # 默认只给本机用
PORT_START = int(os.environ.get("TS_PORT") or os.environ.get("PORT") or 8756)
ON_PAAS = bool(os.environ.get("PORT"))

TIME_LIMIT = 5.0
COMPILE_LIMIT = 60.0
OUT_LIMIT = 512 * 1024
MAX_CODE = 200 * 1024


# ---------------------------------------------------------------- 小工具
def read_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def decode_bytes(b):
    for enc in ("utf-8", "gbk", "gb18030"):
        try:
            return b.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "replace"), "replace"


def norm_lines(text, strict=False):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [l if strict else l.rstrip() for l in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def compare(expected, actual, strict=False, enc_tolerant=False):
    exp, got = norm_lines(expected, strict), norm_lines(actual, strict)
    if exp == got:
        return True, None
    if enc_tolerant:
        for enc in ("gbk", "gb18030"):
            try:
                alt = actual.encode("utf-8", "surrogateescape").decode(enc)
            except (UnicodeDecodeError, UnicodeEncodeError):
                continue
            if norm_lines(alt, strict) == exp:
                return True, enc
    return False, None


def diff_lines(expected, actual, strict, limit=6):
    exp, got = norm_lines(expected, strict), norm_lines(actual, strict)
    out = []
    for i in range(max(len(exp), len(got))):
        e = exp[i] if i < len(exp) else "<没有这一行>"
        g = got[i] if i < len(got) else "<没有这一行>"
        if e != g:
            out.append({"line": i + 1, "expected": e[:400], "actual": g[:400]})
            if len(out) >= limit:
                break
    return out


log_lock = threading.Lock()


def log(msg):
    with log_lock:
        try:
            print("[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), msg))
            sys.stdout.flush()
        except Exception:
            pass


# ---------------------------------------------------------------- 工具链
def find_gpp():
    """按顺序找 g++：本机 w64devkit → 常见安装位置 → PATH。"""
    cands = [
        r"D:\w64devkit\bin\g++.exe",
        r"C:\w64devkit\bin\g++.exe",
        r"C:\msys64\ucrt64\bin\g++.exe",
        r"C:\msys64\mingw64\bin\g++.exe",
        r"C:\MinGW\bin\g++.exe",
        r"C:\Program Files\LLVM\bin\clang++.exe",
        "/usr/bin/g++",
        "/usr/local/bin/g++",
    ]
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if p:
            cands += [os.path.join(p, "g++.exe"), os.path.join(p, "g++")]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


GPP = find_gpp()
PYEXE = sys.executable

CPP_FLAGS = ["-std=c++17", "-O2", "-Wall", "-Wno-unused-variable",
             "-Wno-unused-but-set-variable", "-fdiagnostics-color=never"]
if os.name == "nt":
    # Windows 的 ld 是 PE 格式，栈默认 1 MB，深递归题会崩。
    # 这个参数 Linux 的 ld 不认识，加上会让所有 C++ 编译失败，所以只在 Windows 加。
    CPP_FLAGS.append("-Wl,--stack=16777216")

REF_FLAGS = [f for f in CPP_FLAGS if f != "-Wall"] + ["-w"]

SKEL_CPP = """#include <iostream>
using namespace std;

int main() {
    // TODO: 在这里写你的代码

    return 0;
}
"""


def skel_py(p):
    return (
        "# %s  %s\n"
        "# 从 stdin 读入，答案输出到 stdout\n"
        "import sys\n"
        "\n"
        "\n"
        "def main():\n"
        "    data = sys.stdin.read().split()   # 所有「词」，按空白切开\n"
        "    # data[0]、data[1] … 是各个参数（字符串，要用数字记得 int(...)）\n"
        "    pass\n"
        "\n"
        "\n"
        "main()\n" % (p.pid, p.title))


# ---------------------------------------------------------------- 题面解析
SECTION_KINDS = [
    ("题目描述", "desc"), ("描述", "desc"),
    ("关于输入", "input"), ("输入格式", "input"), ("输入", "input"),
    ("关于输出", "output"), ("输出格式", "output"), ("输出", "output"),
    ("例子输入", "sample_in"), ("样例输入", "sample_in"),
    ("示例输入", "sample_in"), ("输入样例", "sample_in"), ("输入示例", "sample_in"),
    ("例子输出", "sample_out"), ("样例输出", "sample_out"),
    ("示例输出", "sample_out"), ("输出样例", "sample_out"), ("输出示例", "sample_out"),
    ("提示信息", "hint"), ("提示", "hint"), ("说明", "hint"),
    ("样例说明", "hint"), ("数据范围", "hint"), ("注意", "hint"),
]
SECTION_MAP = {}
for _t, _k in SECTION_KINDS:
    SECTION_MAP.setdefault(_t, _k)


def parse_statement(block):
    secs, cur = [], None
    for raw in block.splitlines():
        kind = SECTION_MAP.get(raw.strip().rstrip(":：").strip())
        if kind:
            cur = {"key": kind, "title": raw.strip(), "lines": []}
            secs.append(cur)
        else:
            if cur is None:
                cur = {"key": "pre", "title": "", "lines": []}
                secs.append(cur)
            cur["lines"].append(raw.rstrip())
    out = []
    for s in secs:
        body = s["lines"]
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        if body:
            out.append({"key": s["key"], "title": s["title"], "text": "\n".join(body)})
    return out


# ---------------------------------------------------------------- 题目
class Problem(object):
    def __init__(self, row, corr):
        self.pid = row["题号"].strip()
        self.num = int(row["序号"])
        self.title = row["题目"].strip()
        self.stage = row["阶段"].strip()
        self.stage_name = (row.get("阶段主题") or "").strip()
        self.week = (row.get("建议周次") or "").strip()
        self.loc = int(row["难度(行数)"] or 0)
        self.origin = row["原文件"].strip()
        self.tags = [t for t in (row.get("关键特性") or "").split() if t and t != "—"]
        self.status = (row.get("状态") or "").strip() or "未开始"
        self.passed_date = (row.get("首次通过日") or "").strip()
        self.stem = "%s_%s" % (self.pid, self.title)

        c = corr.get(self.pid, {})
        self.note = c.get("note", "")
        self.strict = bool(c.get("strict"))
        self.enc_tolerant = bool(c.get("encoding_tolerant"))

        self.sections, self.raw, self.raw_block = [], "", ""
        src = os.path.join(REPO, self.origin)
        if os.path.exists(src):
            m = re.search(r"/\*+(.*?)\*+/", read_text(src), re.S)
            if m:
                self.raw_block = m.group(1)
                self.raw = self.raw_block.strip()
                self.sections = parse_statement(self.raw)

        if "cases" in c:
            self.cases = [{"in": x.get("in", ""), "out": x.get("out", "")}
                          for x in c["cases"]]
        else:
            fin = os.path.join(TESTS, self.stem + ".in")
            fout = os.path.join(TESTS, self.stem + ".out")
            self.cases = ([{"in": read_text(fin), "out": read_text(fout)}]
                          if os.path.exists(fin) and os.path.exists(fout) else [])

    @property
    def difficulty(self):
        return "简单" if self.loc <= 40 else ("中等" if self.loc <= 70 else "困难")

    @property
    def cpp_path(self):
        return os.path.join(PRACTICE, self.stage, self.stem + ".cpp")

    @property
    def py_path(self):
        return os.path.join(PRACTICE, self.stage, self.stem + ".py")

    @property
    def ref_exists(self):
        return os.path.exists(os.path.join(REPO, self.origin))

    def prefix_cpp(self):
        return (
            "/*%s*/\n\n" % self.raw_block +
            "// ─────────────────────────────────────────────────────────────\n"
            "// 题号：%s        阶段：%s %s\n"
            "// 参考行数：%d 行   来源：%s\n"
            "// 做法提醒：先手算样例 → 写码 → 提交；卡 40 分钟才看参考解，看完必须合上重写一遍\n"
            "// ─────────────────────────────────────────────────────────────\n\n"
            % (self.pid, self.stage, self.stage_name, self.loc, self.origin))

    def brief(self):
        return {"pid": self.pid, "num": self.num, "title": self.title,
                "stage": self.stage, "stageName": self.stage_name, "week": self.week,
                "loc": self.loc, "difficulty": self.difficulty, "tags": self.tags,
                "status": self.status, "passedDate": self.passed_date,
                "caseCount": len(self.cases), "hasNote": bool(self.note)}


SEP_LINE = re.compile(r"^//\s*[─-]{20,}\s*$")


def split_cpp_prefix(content):
    """把 .cpp 拆成「生成的文件头」和「用户自己写的代码」。"""
    lines = content.split("\n")
    idx = -1
    for i, l in enumerate(lines):
        if SEP_LINE.match(l.strip()):
            idx = i
    if idx < 0:
        return "", content
    user = lines[idx + 1:]
    if user and not user[0].strip():
        user = user[1:]
    return "\n".join(lines[:idx + 1]) + "\n\n", "\n".join(user)


# ---------------------------------------------------------------- 代码读写
def load_code(p, lang):
    if lang == "cpp":
        if os.path.exists(p.cpp_path):
            _, user = split_cpp_prefix(read_text(p.cpp_path))
            if user.strip():
                return user
        return SKEL_CPP
    if os.path.exists(p.py_path):
        t = read_text(p.py_path)
        if t.strip():
            return t
    return skel_py(p)


def save_code(p, lang, code):
    if lang == "cpp":
        write_text(p.cpp_path, p.prefix_cpp() + code.lstrip("\n"))
        return p.cpp_path
    write_text(p.py_path, code)
    return p.py_path


# ---------------------------------------------------------------- 进度（CSV）
_csv_lock = threading.RLock()
_backed_up = [False]


def _backup_csv_once():
    if _backed_up[0]:
        return
    _backed_up[0] = True
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        dst = os.path.join(BACKUP_DIR, "进度追踪表.%s.csv"
                           % datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        shutil.copyfile(CSV_PATH, dst)
        olds = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("进度追踪表."))
        for f in olds[:-5]:
            try:
                os.remove(os.path.join(BACKUP_DIR, f))
            except OSError:
                pass
    except OSError as e:
        log("备份进度表失败（不影响判题）：%s" % e)


def mark_passed(p):
    """把这道题写成「已通过」。已经是已通过的就不动。"""
    if p.status == "已通过":
        return False
    today = datetime.date.today().isoformat()
    with _csv_lock:
        _backup_csv_once()
        rows = list(csv.DictReader(io.open(CSV_PATH, encoding="utf-8-sig")))
        fields = list(rows[0].keys())
        hit = False
        for r in rows:
            if r["题号"].strip() == p.pid:
                r["状态"] = "已通过"
                if not (r.get("首次通过日") or "").strip():
                    r["首次通过日"] = today
                hit = True
                break
        if not hit:
            return False
        tmp = CSV_PATH + ".tmp"
        with io.open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, CSV_PATH)
        p.status = "已通过"
        p.passed_date = p.passed_date or today
    return True


def reload_statuses():
    """重新从 CSV 读一遍状态（VS Code 里手改过 CSV 时也能同步）。"""
    try:
        for r in csv.DictReader(io.open(CSV_PATH, encoding="utf-8-sig")):
            p = BANK_.by_id.get(r["题号"].strip())
            if p:
                p.status = (r.get("状态") or "").strip() or "未开始"
                p.passed_date = (r.get("首次通过日") or "").strip()
    except Exception as e:
        log("重读进度表失败：%s" % e)


# ---------------------------------------------------------------- 执行
# 为什么用 sh + ulimit 而不用 preexec_fn：多线程服务里，preexec_fn 在 fork 之后、
# exec 之前会跑 Python 代码，若别的线程正持着锁就会死锁。ulimit 是 shell 内建，
# 不涉及 Python 代码，趁 exec 前设好就安全。（Windows 没有这些命令，直接不套。）
ULIMIT_SH = (
    "ulimit -c 0 2>/dev/null; "
    "ulimit -t %d 2>/dev/null; "
    "ulimit -v %d 2>/dev/null; "
    "ulimit -f %d 2>/dev/null; "
    "ulimit -s %d 2>/dev/null; "
    "ulimit -u 64 2>/dev/null; "
    'exec "$@"'
) % (int(TIME_LIMIT) + 1, 1024 * 1024, 16 * 1024, 64 * 1024)


def with_limits(cmd):
    if os.name == "nt":
        return cmd
    sh = "/bin/sh" if os.path.exists("/bin/sh") else "sh"
    return [sh, "-c", ULIMIT_SH, "sh"] + list(cmd)


def run_proc(cmd, stdin_path, timeout, cwd, env=None):
    op = os.path.join(cwd, "_o.txt")
    ep = os.path.join(cwd, "_e.txt")
    t0 = time.time()
    timed_out, rc = False, None
    try:
        with open(stdin_path or os.devnull, "rb") as fi, \
                open(op, "wb") as fo, open(ep, "wb") as fe:
            rc = subprocess.run(cmd, stdin=fi, stdout=fo, stderr=fe,
                                timeout=timeout, cwd=cwd, env=env).returncode
    except subprocess.TimeoutExpired:
        timed_out = True
    except OSError as e:
        return None, b"", str(e).encode("utf-8"), 0, True
    ms = int((time.time() - t0) * 1000)
    out = open(op, "rb").read()[:OUT_LIMIT] if os.path.exists(op) else b""
    err = open(ep, "rb").read()[:OUT_LIMIT] if os.path.exists(ep) else b""
    return rc, out, err, ms, timed_out


def py_env():
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def build(lang, code, workdir):
    if lang == "cpp":
        if GPP is None:
            return None, {"ok": False,
                          "message": "找不到 g++。请装 w64devkit，或用 工具\\下载编译器.py"}
        src, exe = os.path.join(workdir, "main.cpp"), os.path.join(workdir, "main.exe")
        write_text(src, code)
        rc, out, err, ms, to = run_proc([GPP] + CPP_FLAGS + [src, "-o", exe],
                                        None, COMPILE_LIMIT, workdir)
        msg, _ = decode_bytes((out or b"") + (err or b""))
        if to:
            return None, {"ok": False, "message": "编译超时（%.0f 秒）" % COMPILE_LIMIT}
        if rc != 0 or not os.path.exists(exe):
            return None, {"ok": False, "message": msg.strip() or "编译失败", "ms": ms}
        return [exe], {"ok": True, "message": msg.strip(), "ms": ms}
    src = os.path.join(workdir, "main.py")
    write_text(src, code)
    return [PYEXE, "-X", "utf8", src], {"ok": True, "message": "", "ms": 0}


def run_case(runner, lang, text_in, workdir, tag, sandbox=True):
    ipath = os.path.join(workdir, "in_%s.txt" % tag)
    with io.open(ipath, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text_in or "")
    env = py_env() if lang != "cpp" else None
    cmd = with_limits(runner) if sandbox else runner
    rc, out, err, ms, to = run_proc(cmd, ipath, TIME_LIMIT, workdir, env=env)
    so, _ = decode_bytes(out)
    se, _ = decode_bytes(err)
    return {"stdout": so, "stderr": se, "rc": rc, "ms": ms, "timeout": to}


# ---------------------------------------------------------------- 参考解
_ref_lock = threading.Lock()


def ensure_ref_exe(p):
    src = os.path.join(REPO, p.origin)
    if not os.path.exists(src):
        return None, "参考解源文件缺失：%s" % p.origin
    if GPP is None:
        return None, "找不到 g++，无法运行参考解"
    os.makedirs(REF_CACHE, exist_ok=True)
    exe = os.path.join(REF_CACHE, p.pid + ".exe")
    with _ref_lock:
        if os.path.exists(exe) and os.path.getmtime(exe) >= os.path.getmtime(src):
            return exe, None
        tmp = os.path.join(REF_CACHE, "_b_" + p.pid)
        os.makedirs(tmp, exist_ok=True)
        rc, out, err, ms, to = run_proc(
            [GPP] + REF_FLAGS + [src, "-o", exe], None, COMPILE_LIMIT, tmp)
        msg, _ = decode_bytes((out or b"") + (err or b""))
        shutil.rmtree(tmp, ignore_errors=True)
        if to or rc != 0 or not os.path.exists(exe):
            return None, "参考解编译失败：\n" + (msg.strip() or "(无输出)")[:1200]
    return exe, None


# ---------------------------------------------------------------- 题库
class Bank(object):
    def __init__(self):
        corr = {}
        if os.path.exists(CORR_PATH):
            try:
                corr = json.loads(read_text(CORR_PATH))
            except Exception as e:
                log("题目校正.json 读取失败：%s" % e)
        rows = list(csv.DictReader(io.open(CSV_PATH, encoding="utf-8-sig")))
        self.problems = [Problem(r, corr) for r in rows]
        self.by_id = {p.pid: p for p in self.problems}
        self.stages = []
        for p in self.problems:
            if p.stage not in self.stages:
                self.stages.append(p.stage)


BANK_ = None
SEM = threading.Semaphore(2)          # 编译太吃 CPU，同时最多两个


def append_history(rec):
    with _csv_lock:
        with io.open(HISTORY_PATH, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "TrainSite/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _err(self, msg, code=400):
        self._json({"ok": False, "error": msg}, code)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > MAX_CODE + 65536:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    # ---- GET ----
    def do_GET(self):
        u = urlparse(self.path)
        path, qs = unquote(u.path), parse_qs(u.query)
        if path in ("/", "/index.html"):
            return self._static("index.html")
        if path.startswith("/api/"):
            return self._api_get(path, qs)
        return self._static(path.lstrip("/"))

    def _static(self, name):
        if name in ("favicon.ico", "apple-touch-icon.png"):
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        full = os.path.normpath(os.path.join(WEB_DIR, name))
        if not full.startswith(WEB_DIR) or not os.path.isfile(full):
            return self._err("找不到 %s" % name, 404)
        ctype = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "application/javascript; charset=utf-8",
                 ".svg": "image/svg+xml", ".json": "application/json; charset=utf-8"
                 }.get(os.path.splitext(full)[1].lower(), "application/octet-stream")
        self._send(200, open(full, "rb").read(), ctype)

    def _api_get(self, path, qs):
        if path == "/api/health":
            return self._json({"ok": True, "status": "up",
                               "problems": len(BANK_.problems),
                               "compiler": bool(GPP), "python": sys.version.split()[0]})

        if path == "/api/meta":
            return self._json({"ok": True, "server": "计算概论 · 训练场",
                               "compiler": GPP or "", "python": PYEXE,
                               "stages": BANK_.stages,
                               "totalProblems": len(BANK_.problems),
                               "bank": BANK})

        if path == "/api/state":
            reload_statuses()
            return self._json({"ok": True,
                               "problems": [p.brief() for p in BANK_.problems],
                               "compiler": GPP or "", "stages": BANK_.stages})

        if path.startswith("/api/problem/"):
            pid = path.rsplit("/", 1)[-1]
            p = BANK_.by_id.get(pid)
            if not p:
                return self._err("没有这道题：%s" % pid)
            reload_statuses()
            d = p.brief()
            d.update({
                "ok": True, "sections": p.sections, "raw": p.raw,
                "cases": p.cases, "strict": p.strict, "note": p.note,
                "origin": p.origin,
                "code": {"cpp": load_code(p, "cpp"), "python": load_code(p, "python")},
                "skeleton": {"cpp": SKEL_CPP, "python": skel_py(p)},
                "refAvailable": p.ref_exists,
            })
            return self._json(d)

        if path == "/api/ref":
            p = BANK_.by_id.get((qs.get("pid") or [""])[0])
            if not p:
                return self._err("没有这道题")
            src = os.path.join(REPO, p.origin)
            if not os.path.exists(src):
                return self._err("参考解源文件缺失")
            return self._json({"ok": True, "pid": p.pid, "title": p.title,
                               "origin": p.origin, "code": read_text(src)})

        if path == "/api/history":
            pid = (qs.get("pid") or [""])[0]
            items = []
            if os.path.exists(HISTORY_PATH):
                for line in io.open(HISTORY_PATH, encoding="utf-8"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    if not pid or r.get("pid") == pid:
                        items.append(r)
            return self._json({"ok": True, "items": items[-40:][::-1]})

        return self._err("未知接口 " + path, 404)

    # ---- POST ----
    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        body = self._body()
        try:
            return self._api_post(path, body)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._err("服务器内部错误：%s: %s" % (type(e).__name__, e), 500)

    def _api_post(self, path, body):
        if path == "/api/code":
            p = BANK_.by_id.get(body.get("pid"))
            lang = body.get("lang")
            if not p or lang not in ("cpp", "python"):
                return self._err("参数不对")
            code = body.get("code") or ""
            if len(code) > MAX_CODE:
                return self._err("代码太长了")
            saved = save_code(p, lang, code)
            return self._json({"ok": True, "saved": os.path.relpath(saved, BANK)})

        if path in ("/api/run", "/api/submit"):
            p = BANK_.by_id.get(body.get("pid"))
            lang = body.get("lang")
            if not p or lang not in ("cpp", "python"):
                return self._err("参数不对")
            code = body.get("code") or ""
            if not code.strip():
                return self._err("代码是空的")
            if len(code) > MAX_CODE:
                return self._err("代码太长了（上限 200 KB）")
            try:
                save_code(p, lang, code)          # 顺手存盘
            except Exception:
                pass
            if path == "/api/run":
                return self._json(self.do_run(p, lang, code, body))
            return self._json(self.do_submit(p, lang, code))

        return self._err("未知接口 " + path, 404)

    def do_run(self, p, lang, code, body):
        text_in = body.get("input") or ""
        with_ref = bool(body.get("withRef"))
        work = os.path.join(RUNS, "w%d_%d" % (int(time.time() * 1000),
                                              threading.get_ident() % 1000))
        os.makedirs(work, exist_ok=True)
        try:
            with SEM:
                runner, cinfo = build(lang, code, work)
                if runner is None:
                    return {"ok": True, "compile": cinfo, "run": None}
                got = run_case(runner, lang, text_in, work, "user")
            res = {"ok": True, "compile": cinfo,
                   "run": {"stdout": got["stdout"], "stderr": got["stderr"],
                           "ms": got["ms"], "timeout": got["timeout"], "rc": got["rc"]}}
            if with_ref:
                exe, err = ensure_ref_exe(p)
                if exe is None:
                    res["ref"] = {"ok": False, "error": err}
                else:
                    with SEM:
                        r2 = run_case([exe], "cpp", text_in, work, "ref", sandbox=False)
                    res["ref"] = {"ok": True, "stdout": r2["stdout"],
                                  "stderr": r2["stderr"], "ms": r2["ms"],
                                  "timeout": r2["timeout"]}
                    if not r2["timeout"]:
                        same, enc = compare(r2["stdout"], got["stdout"],
                                            p.strict, p.enc_tolerant)
                        res["ref"]["match"] = bool(same)
                        res["ref"]["strict"] = p.strict
                        if not same:
                            res["ref"]["diff"] = diff_lines(r2["stdout"], got["stdout"],
                                                            p.strict)
            return res
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def do_submit(self, p, lang, code):
        if not p.cases:
            return {"ok": True, "error": "这道题没有可用的官方样例，请用「运行」自定义测试"}
        work = os.path.join(RUNS, "s%d_%d" % (int(time.time() * 1000),
                                              threading.get_ident() % 1000))
        os.makedirs(work, exist_ok=True)
        t0 = time.time()
        try:
            with SEM:
                runner, cinfo = build(lang, code, work)
            if runner is None:
                append_history({"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                                "pid": p.pid, "title": p.title, "lang": lang,
                                "result": "编译失败", "passed": 0,
                                "total": len(p.cases)})
                return {"ok": True, "compile": cinfo, "cases": [], "passed": 0,
                        "total": len(p.cases), "verdict": "编译失败"}
            results, passed = [], 0
            for i, c in enumerate(p.cases, 1):
                with SEM:
                    got = run_case(runner, lang, c["in"], work, "c%d" % i)
                item = {"idx": i, "input": c["in"], "expected": c["out"],
                        "actual": got["stdout"], "stderr": got["stderr"], "ms": got["ms"]}
                if got["timeout"]:
                    item["status"] = "TLE"
                    item["message"] = "超过 %.0f 秒（多半是死循环）" % TIME_LIMIT
                elif got["rc"] not in (0, None) and not got["stdout"].strip():
                    item["status"] = "RE"
                    item["message"] = ("程序异常结束（返回码 %s）\n" % got["rc"]) + \
                                      got["stderr"][:600]
                else:
                    same, enc = compare(c["out"], got["stdout"], p.strict, p.enc_tolerant)
                    item["status"] = "PASS" if same else "FAIL"
                    if same:
                        passed += 1
                        if enc:
                            item["message"] = "输出是 %s 编码，已按编码容错判对" % enc
                    else:
                        item["diff"] = diff_lines(c["out"], got["stdout"], p.strict)
                        item["message"] = "输出不一致"
                results.append(item)

            total = len(p.cases)
            verdict = "通过" if passed == total else "未通过"
            if passed == total:
                mark_passed(p)
            append_history({"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                            "pid": p.pid, "title": p.title, "lang": lang,
                            "result": verdict, "passed": passed, "total": total,
                            "ms": int((time.time() - t0) * 1000)})
            return {"ok": True, "compile": cinfo, "cases": results, "passed": passed,
                    "total": total, "verdict": verdict,
                    "status": p.status, "passedDate": p.passed_date}
        finally:
            shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------- 启动
def lan_ips():
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return ips


def pick_port(host):
    for port in range(PORT_START, PORT_START + 20):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((host, port))
            return port
        except OSError:
            continue
        finally:
            s.close()
    return PORT_START


def main():
    global BANK_
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass

    if not os.path.exists(CSV_PATH):
        # 从模板生成一份空进度表（仓库里不带任何人的进度）
        if os.path.exists(CSV_TEMPLATE):
            shutil.copyfile(CSV_TEMPLATE, CSV_PATH)
            log("进度表不存在，已从模板生成：%s" % os.path.basename(CSV_PATH))
        else:
            print("找不到 %s，也找不到 %s"
                  % (os.path.basename(CSV_PATH), os.path.basename(CSV_TEMPLATE)))
            return 1
    for d in (RUNS, REF_CACHE):
        os.makedirs(d, exist_ok=True)

    t0 = time.time()
    BANK_ = Bank()
    log("已装载 %d 道题，%d 组用例（%.2f 秒）"
        % (len(BANK_.problems), sum(len(p.cases) for p in BANK_.problems),
           time.time() - t0))
    log("编译器：%s" % (GPP or "⚠️ 未找到 g++，C++ 判题不可用"))
    log("已通过：%d / %d" % (sum(1 for p in BANK_.problems if p.status == "已通过"),
                            len(BANK_.problems)))

    port = PORT_START if ON_PAAS else pick_port(HOST)
    httpd = ThreadingHTTPServer((HOST, port), Handler)
    print("=" * 66)
    log("服务已启动（关掉这个窗口即停止）")
    print("  本机访问： http://127.0.0.1:%d/" % port, flush=True)
    if HOST not in ("127.0.0.1", "localhost"):
        for ip in lan_ips():
            print("  局域网：  http://%s:%d/" % (ip, port), flush=True)
    print("=" * 66, flush=True)

    if not ON_PAAS and not os.environ.get("TS_NO_BROWSER"):
        def open_later():
            time.sleep(0.8)
            try:
                webbrowser.open("http://127.0.0.1:%d/" % port)
            except Exception:
                pass
        threading.Thread(target=open_later, daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("正在退出……")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
