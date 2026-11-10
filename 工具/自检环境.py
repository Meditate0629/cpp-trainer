# -*- coding: utf-8 -*-
r"""环境自检 —— 拿到这份题库后先跑一次，全绿就能开始刷题。

用法：
  python 工具/自检环境.py          （Windows: python 工具\自检环境.py）

检查六件事：
  1. Python 版本够不够（需要 3.8+）
  2. 能不能找到 C++ 编译器（g++ / clang++，走 PATH）
  3. 编译器真能编译并跑出一个程序（比只看版本号可靠）
  4. 题库文件齐不齐（250 份模板 / 250 组样例 / 250 份参考解）
  5. 网站文件在不在、启动脚本是不是纯 ASCII（含中文会双击闪退）
  6. 进度表能不能读、有多少题已通过

退出码 0 = 全绿，1 = 有项目没过。
"""
import csv
import io
import os
import shutil
import subprocess
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(BASE, "训练网站")
PRACTICE = os.path.join(BASE, "练习")
TESTS = os.path.join(BASE, "测试数据")
REFS = os.path.join(BASE, "IntroductionToComputationHomework2022-master")
CSV_PATH = os.path.join(BASE, "进度追踪表.csv")
CSV_TPL = os.path.join(BASE, "进度追踪表.模板.csv")

OK_ALL = True
WARN = []


def mark(ok, label, extra="", warn=False):
    """warn=True 的项目不过只提醒，不算失败（比如没有 gdb）。"""
    global OK_ALL
    if not ok and not warn:
        OK_ALL = False
    tag = "OK" if ok else ("??" if warn else "!!")
    print("  [%s] %s%s" % (tag, label, ("  " + extra) if extra else ""))


def find_exe(names):
    """在 PATH 里找可执行文件，返回第一个找到的绝对路径。"""
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def run(exe, args, cwd=None, stdin_data=None, timeout=60):
    """跑一个程序，返回 (返回码, 合并输出)。不依赖 shell，中文路径也安全。"""
    try:
        p = subprocess.run([exe] + args, cwd=cwd, timeout=timeout,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           input=stdin_data)
        return p.returncode, p.stdout.decode("utf-8", "replace").strip()
    except Exception as e:
        return None, str(e)


def count(d, ext):
    if not os.path.isdir(d):
        return 0
    n = 0
    for _dp, _dn, fn in os.walk(d):
        n += sum(1 for f in fn if f.endswith(ext))
    return n


def main():
    print("=" * 66)
    print("计算概论 · 训练场 —— 环境自检")
    print("  题库目录：%s" % BASE)
    print("=" * 66)

    # ---------- 1. Python
    print("\n[1] Python")
    ver = sys.version_info
    mark(ver >= (3, 8), "Python %d.%d.%d" % ver[:3], sys.executable)
    if ver < (3, 8):
        WARN.append("网站要求 Python 3.8 以上。")

    # ---------- 2. 编译器
    print("\n[2] C++ 编译器")
    gpp = find_exe(["g++", "g++.exe", "clang++", "clang++.exe"])
    mark(bool(gpp), "PATH 里找得到 g++ / clang++", gpp or "没找到")
    if gpp:
        code, out = run(gpp, ["--version"])
        mark(code == 0, "能报出版本号",
             (out.splitlines()[0] if out else ""))
    else:
        WARN.append("没有 C++ 编译器：C++ 判题会全部失败。"
                    "Windows 装 w64devkit（见 README「装编译器」），"
                    "或者跑 工具\\下载编译器.py；Linux/macOS 用系统包管理器装 g++。")
    gdb = find_exe(["gdb", "gdb.exe", "lldb"])
    mark(bool(gdb), "有调试器（VS Code 断点调试要用）", gdb or "没有，不影响判题",
         warn=True)

    # ---------- 3. 真编一个程序跑一遍
    print("\n[3] 编译 + 运行自测")
    if gpp:
        tmp = tempfile.mkdtemp(prefix="chk_")
        src = os.path.join(tmp, "a.cpp")
        exe = os.path.join(tmp, "a.exe" if os.name == "nt" else "a.out")
        with io.open(src, "w", encoding="utf-8", newline="\n") as fh:
            fh.write('#include <iostream>\nint main(){int a,b;'
                     'if(std::cin>>a>>b) std::cout<<a+b<<"\\n"; return 0;}\n')
        code, out = run(gpp, ["-std=c++17", "-O2", src, "-o", exe])
        mark(code == 0, "编译 -std=c++17 成功", "" if code == 0 else out[:200])
        if code == 0:
            code, out = run(exe, [], stdin_data=b"1 2\n")
            mark(code == 0 and out.strip() == "3", "运行结果正确（1+2=3）", out[:200])
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        mark(False, "跳过（没有编译器）")

    # ---------- 4. 题库文件
    print("\n[4] 题库文件")
    n_practice = count(PRACTICE, ".cpp")
    n_in = count(TESTS, ".in")
    n_out = count(TESTS, ".out")
    n_ref = count(REFS, ".cpp")
    mark(n_practice == 250, "练习模板 %d / 250" % n_practice)
    mark(n_in == 250, "测试输入 %d / 250" % n_in)
    mark(n_out == 250, "测试输出 %d / 250" % n_out)
    mark(n_ref == 250, "参考答案 %d / 250" % n_ref)
    mark(os.path.isfile(CSV_PATH) or os.path.isfile(CSV_TPL),
         "进度追踪表.csv（或模板）",
         "" if os.path.isfile(CSV_PATH) else "只有模板，启动网站时会自动生成")

    # ---------- 5. 网站
    print("\n[5] 网站")
    for f in ("server.py", "题目校正.json", "README.md",
              os.path.join("web", "index.html"), os.path.join("web", "style.css"),
              os.path.join("web", "app.js"), "启动网站.cmd"):
        mark(os.path.isfile(os.path.join(SITE, f)), "训练网站/" + f.replace(os.sep, "/"))
    raw = b""
    try:
        raw = open(os.path.join(SITE, "启动网站.cmd"), "rb").read()
    except OSError:
        pass
    mark(bool(raw) and all(c < 128 for c in raw),
          "启动网站.cmd 是纯 ASCII（含中文会双击闪退）")
    try:
        head = open(os.path.join(SITE, "server.py"), encoding="utf-8").read(4000)
    except OSError:
        head = ""
    mark("sqlite3" not in head, "server.py 是单机版（不需要数据库、不用注册）")

    # ---------- 6. 进度表
    print("\n[6] 进度表")
    if not os.path.isfile(CSV_PATH) and os.path.isfile(CSV_TPL):
        shutil.copyfile(CSV_TPL, CSV_PATH)
        print("       进度表不存在，已从模板生成")
    try:
        rows = list(csv.DictReader(io.open(CSV_PATH, encoding="utf-8-sig")))
        passed = [r for r in rows if (r.get("状态") or "").strip() == "已通过"]
        mark(len(rows) == 250, "读到 %d 行（应为 250）" % len(rows))
        print("       已通过 %d 题：%s" % (
            len(passed), "、".join(r["题号"] for r in passed[:10]) or "（还没有）"))
    except Exception as e:
        mark(False, "进度表读不了", str(e)[:200])

    print("\n" + "=" * 66)
    if OK_ALL:
        print("全部通过 —— 双击 训练网站/启动网站.cmd 就能开始刷题")
    else:
        print("有项目没过，见上面的 [!!]")
    for w in WARN:
        print("* 提醒：" + w)
    print("=" * 66)
    return 0 if OK_ALL else 1


if __name__ == "__main__":
    sys.exit(main())
