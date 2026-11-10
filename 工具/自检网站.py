# -*- coding: utf-8 -*-
r"""训练网站验收：启动 → 判题 → 代码落盘 → 进度回写 → 恢复原状。

用法：python 工具\自检网站.py
跑完会把动过的文件和进度表按开测前的字节原样写回。"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

try:                                   # Windows 控制台默认 GBK，打不出 ✓ ✗
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BANK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(BANK, "训练网站")
PRACTICE = os.path.join(BANK, "练习")
CSV = os.path.join(BANK, "进度追踪表.csv")
PORT = None
FAILS = []


def log(s=""):
    print(s)


def check(c, label, extra=""):
    log(("   ✓ " if c else "   ✗ ") + label + ("" if c else "  " + str(extra)))
    if not c:
        FAILS.append(label)


def req(path, obj=None):
    url = "http://127.0.0.1:%d%s" % (PORT, path)
    try:
        if obj is None:
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        rq = urllib.request.Request(url, data=json.dumps(obj).encode("utf-8"),
                                    headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(rq, timeout=180) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(b)
        except Exception:
            return e.code, {"ok": False, "error": b[:200]}


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def main():
    global PORT
    cpp_s1 = os.path.join(PRACTICE, "S1", "S1-001_点和正方形的关系.cpp")
    cpp_s2 = os.path.join(PRACTICE, "S1", "S1-002_最受欢迎的医生.cpp")
    # 开测前把会被动到的文件按字节存下来，结束时原样写回（保证 md5 一字节不差）
    touched = [cpp_s1, cpp_s2,
               os.path.join(PRACTICE, "S1", "S1-003_能被357整除的数.cpp"),
               os.path.join(PRACTICE, "S3", "S3-065_重排空格.cpp"),
               CSV, os.path.join(APP, "提交记录.jsonl")]
    orig = dict((fp, (open(fp, "rb").read() if os.path.exists(fp) else None))
                for fp in touched)
    bdir = os.path.join(APP, "备份")
    baks_before = set(os.listdir(bdir)) if os.path.isdir(bdir) else set()
    h1_before, h2_before = md5(cpp_s1), md5(cpp_s2)
    csv_before = open(CSV, "rb").read()

    env = dict(os.environ)
    env.update({"TS_NO_BROWSER": "1", "PYTHONIOENCODING": "utf-8",
                "TS_HOST": "127.0.0.1"})
    lp = os.path.join(tempfile.gettempdir(), "ts_solo.log")
    fo = open(lp, "wb")
    p = subprocess.Popen([sys.executable, "server.py"], cwd=APP, env=env,
                         stdout=fo, stderr=subprocess.STDOUT)
    try:
        for _ in range(200):
            time.sleep(0.4)
            t = open(lp, "rb").read().decode("utf-8", "replace") if os.path.exists(lp) else ""
            if "服务已启动" in t:
                if "127.0.0.1:" in t:
                    PORT = int(t.split("127.0.0.1:")[1].split("/")[0])
                break
        check(PORT is not None, "服务启动",
              open(lp, "rb").read().decode("utf-8", "replace")[-500:])
        if not PORT:
            return 1
        head = open(lp, "rb").read().decode("utf-8", "replace")
        log("   启动日志:")
        for ln in head.strip().splitlines()[:5]:
            log("     " + ln)
        log()

        st, d = req("/api/health")
        check(d.get("problems") == 250, "健康检查 250 题", d)
        check(d.get("compiler") is True, "找得到 g++")

        st, d = req("/api/state")
        check(len(d["problems"]) == 250, "题目列表 250 条")
        check(sorted(d["stages"]) == ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9"],
              "9 个阶段")
        passed = [x["pid"] for x in d["problems"] if x["status"] == "已通过"]
        check(passed == ["S1-001"], "进度表里的已通过被正确读出", passed)

        log()
        log("[1] 读代码：S1-001 应该是原来那份")
        st, d = req("/api/problem/S1-001")
        code = d["code"]["cpp"]
        check(len(code.encode()) == 280, "用户代码 280 字节", len(code.encode()))
        check("scanf" in code, "含你注释的 scanf")
        check("#include" in code and code.lstrip().startswith("#include"), "没有重复文件头")
        check("题目描述" not in code, "文件头被剥掉了（所以编辑器里只看代码）")
        check(d["code"]["python"].startswith("# S1-001"), "Python 是空骨架")
        check(len(d["cases"]) == 1 and d["cases"][0]["out"].strip() == "yes", "官方样例正常")
        check("题目描述" in d["raw"], "题面能解析")

        log()
        log("[2] 判题")
        st, d = req("/api/submit", {"pid": "S1-001", "lang": "cpp", "code": code})
        check(d.get("verdict") == "通过", "C++ 提交通过", d.get("verdict"))
        py = ('import sys\nd=sys.stdin.read().replace(","," ").split()\n'
              'x,y=float(d[0]),float(d[1])\n'
              'print("yes" if -1<=x<=1 and -1<=y<=1 else "no")\n')
        st, d = req("/api/submit", {"pid": "S1-001", "lang": "python", "code": py})
        check(d.get("verdict") == "通过", "Python 提交通过", d.get("verdict"))
        st, d = req("/api/submit", {"pid": "S1-001", "lang": "cpp",
                                    "code": '#include <iostream>\nint main(){std::cout<<"no";}\n'})
        check(d.get("verdict") == "未通过", "错误解判未通过")
        check(d["cases"][0]["diff"][0]["expected"] == "yes", "给出逐行差异")
        st, d = req("/api/submit", {"pid": "S1-001", "lang": "cpp", "code": "int main(){ 坏 }"})
        check(d.get("verdict") == "编译失败", "编译错误能识别")

        log()
        log("[3] 运行 + 参考解对比")
        st, d = req("/api/run", {"pid": "S1-001", "lang": "cpp", "code": code,
                                 "input": "2,0\n", "withRef": True})
        check(d["run"]["stdout"].strip() == "no", "自定义输入跑出 no")
        check(d["ref"]["ok"] is True and d["ref"]["match"] is True, "和参考解一致")
        st, d = req("/api/run", {"pid": "S1-001", "lang": "cpp",
                                 "code": '#include <iostream>\nint main(){std::cout<<"yes";}\n',
                                 "input": "2,0\n", "withRef": True})
        check(d["ref"]["match"] is False and d["ref"]["diff"], "故意写错能报出差异")

        log()
        log("[4] 严格比较的题（重排空格，行尾空格也算错）")
        st, d = req("/api/submit", {"pid": "S3-065", "lang": "cpp",
                                    "code": '#include <iostream>\nint main(){std::cout<<"this  is  a  sentence";}'})
        check(d.get("verdict") == "未通过", "少末尾空格判错")
        st, d = req("/api/submit", {"pid": "S3-065", "lang": "cpp",
                                    "code": '#include <iostream>\nint main(){std::cout<<"this  is  a  sentence  "<<"\\n";}'})
        check(d.get("verdict") == "通过", "带末尾空格判对")
        # 还原 S3-065 的模板（上面提交把它写成了测试代码）
        tam = os.path.join(PRACTICE, "S3", "S3-065_重排空格.cpp")
        hdr = open(tam, encoding="utf-8").read()
        sep = "// " + "\u2500" * 61
        i = hdr.rfind(sep)
        end = hdr.find("\n", hdr.find("\n", i) + 1) + 1
        io.open(tam, "w", encoding="utf-8", newline="\n").write(
            hdr[:end] + "\n#include <iostream>\nusing namespace std;\n\nint main() {\n"
            "    // TODO: 在这里写你的代码\n\n    return 0;\n}\n")

        log()
        log("[5] 代码落盘到 练习\\ 且能还原")
        h_now = md5(cpp_s1)
        check(h_now != h1_before, "提交时把代码写进了 练习\\S1\\S1-001.cpp")
        t = open(cpp_s1, encoding="utf-8").read()
        check("题目描述" in t, "文件里带着题面注释（VS Code 打开能看到题）")
        check("TODO" not in t, "不再是空模板")
        # 主刀：把 S1-001 写回原样
        io.open(cpp_s1, "w", encoding="utf-8", newline="\n").write(
            t[:t.rfind(sep)] + sep + "\n" + sep.replace("─", "─") + "\n\n" + code)

        log()
        log("[6] 进度回写 CSV")
        csv_mid = open(CSV, "rb").read()   # [4] 里 S3-065 变已通过，得重新取基准
        st, d = req("/api/submit", {"pid": "S1-002", "lang": "cpp",
                                    "code": '#include <iostream>\nint main(){return 0;}\n'})
        check(d.get("verdict") == "未通过", "S1-002 空程序判未通过")
        check(open(CSV, "rb").read() == csv_mid, "未通过不会改 CSV")

        s3_code = (
            '#include <iostream>\n'
            'using namespace std;\n'
            'int main() {\n'
            '    int n;\n'
            '    if (!(cin >> n)) return 0;\n'
            '    bool a = n % 3 == 0, b = n % 5 == 0, c = n % 7 == 0;\n'
            '    int k = a + b + c;\n'
            '    if (k == 3) cout << "3 5 7";\n'
            '    else if (a && b) cout << "3 5";\n'
            '    else if (a && c) cout << "3 7";\n'
            '    else if (b && c) cout << "5 7";\n'
            '    else if (a) cout << "3";\n'
            '    else if (b) cout << "5";\n'
            '    else if (c) cout << "7";\n'
            '    else cout << "n";\n'
            '    return 0;\n'
            '}\n')
        st, d = req("/api/submit", {"pid": "S1-003", "lang": "cpp", "code": s3_code})
        check(d.get("verdict") == "通过", "S1-003 正确解判通过",
              "%s %s/%s" % (d.get("verdict"), d.get("passed"), d.get("total")))
        csv_after = open(CSV, "rb").read()
        check(csv_after != csv_before, "通过后会写 CSV")
        import csv as _csv
        rows = list(_csv.DictReader(io.open(CSV, encoding="utf-8-sig")))
        s3 = [r for r in rows if r["题号"] == "S1-003"][0]
        check(s3["状态"] == "已通过" and s3["首次通过日"], "CSV 里 S1-003 变成已通过", s3)

        log()
        log("[7] 静态资源 / 确实没有账号接口")
        for path, must in (("/", b"editor"), ("/style.css", b"editor-wrap"),
                           ("/app.js", b"renderList")):
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (PORT, path),
                                        timeout=30) as r:
                body = r.read()
            check(r.status == 200 and must in body, "静态资源 " + path)
        st, d = req("/api/login", {})
        check(st == 404, "没有 /api/login（单机版）")
        st, d = req("/api/leaderboard")
        check(st == 404, "没有排行榜接口（单机版）")
    finally:
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
        fo.close()
        if os.path.exists(lp):
            os.remove(lp)

        # ---------- 还原：按开测前的字节原样写回 ----------
        log()
        log("[还原]")
        for fp, blob in orig.items():
            if blob is None:
                if os.path.exists(fp):
                    os.remove(fp)
                    log("   删掉测试新建的 %s" % os.path.basename(fp))
            else:
                with open(fp, "wb") as fh:
                    fh.write(blob)
        log("   %d 个文件已按开测前的字节写回" % len(orig))
        # 测试过程中服务器自动生成的进度表备份，也清掉
        if os.path.isdir(bdir):
            for f in sorted(set(os.listdir(bdir)) - baks_before):
                try:
                    os.remove(os.path.join(bdir, f))
                    log("   删掉测试产生的备份 %s" % f)
                except OSError:
                    pass
        for f in ("S1-001_点和正方形的关系.py",):
            fp = os.path.join(PRACTICE, "S1", f)
            if os.path.exists(fp):
                os.remove(fp)
                log("   删掉测试留下的 %s" % f)
        if os.path.isdir(os.path.join(APP, "运行")):
            shutil.rmtree(os.path.join(APP, "运行"), ignore_errors=True)
        hp = os.path.join(APP, "提交记录.jsonl")
        if os.path.exists(hp):
            kept = [l for l in io.open(hp, encoding="utf-8")
                    if '"pid": "S1-001"' not in l and '"pid": "S1-002"' not in l
                    and '"pid": "S1-003"' not in l and '"pid": "S3-065"' not in l]
            io.open(hp, "w", encoding="utf-8", newline="\n").writelines(kept)
            if not kept:
                os.remove(hp)

        log()
        check(md5(cpp_s1) == h1_before, "S1-001 恢复后 md5 == 测试前")
        check(md5(cpp_s2) == h2_before, "S1-002 恢复后 md5 == 测试前")
        check(md5(CSV) == hashlib.md5(csv_before).hexdigest(),
              "进度表恢复后 md5 == 测试前")
        check(sorted(set(os.listdir(bdir)) - baks_before) == [],
              "测试产生的备份已清理")

    log()
    if FAILS:
        log("❌ %d 项没通过：%s" % (len(FAILS), FAILS))
        return 1
    log("✅ 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
