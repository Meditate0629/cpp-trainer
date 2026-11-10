# -*- coding: utf-8 -*-
r"""按《进度追踪表.csv》生成：
  1. 练习\<阶段>\<题号>_<题目>.cpp   —— 空模板（只有题面 + 空 main，不含答案）
  2. 测试数据\<题号>_<题目>.in / .out —— 从题面注释里抽出的样例输入输出

训练网站和判题器都是靠这两个文件名（不含扩展名）对上号的。

用法：
  python 工具\生成练习.py                 重建模板 + 测试数据（不覆盖已写过的题）
  python 工具\生成练习.py --tests-only    只重建测试数据
"""

import csv
import io
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "IntroductionToComputationHomework2022-master")
CSV = os.path.join(BASE, "进度追踪表.csv")
CSV_TPL = os.path.join(BASE, "进度追踪表.模板.csv")
if not os.path.exists(CSV) and os.path.exists(CSV_TPL):
    import shutil as _sh
    _sh.copyfile(CSV_TPL, CSV)          # 仓库里只带模板，首次运行时自己生成
OUT_PRACTICE = os.path.join(BASE, "练习")
OUT_TESTS = os.path.join(BASE, "测试数据")

IN_KEYS = ["例子输入", "样例输入", "示例输入", "输入样例", "输入示例"]
OUT_KEYS = ["例子输出", "样例输出", "示例输出", "输出样例", "输出示例"]

# 抽「例子输入/例子输出」时，遇到下一个章节标题就要停。
# 否则「例子输出」后面的「提示信息」「说明」会被当成期望输出 —— 250 个文件里踩了 90 个。
TODO_SENTINEL = "// TODO: 在这里写你的代码"
SECTION_KEYS = set([
    "题目描述", "关于输入", "关于输出", "输入", "输出",
    "例子输入", "样例输入", "示例输入", "输入样例", "输入示例",
    "例子输出", "样例输出", "示例输出", "输出样例", "输出示例",
    "提示信息", "提示", "说明", "样例说明", "样例解释", "数据范围", "数据规模",
    "注意", "注释", "注意事項", "输入数据", "输出数据", "题目来源", "评分标准",
])

BAD_CHARS = r'<>:"/\|?*'


def read_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def find_idx(lines, keys):
    """按优先级找标记行。必须先找「例子输入/例子输出」，
    否则会命中题面里的「关于输入/关于输出」描述段。"""
    for k in keys:
        for i, l in enumerate(lines):
            if l.strip().rstrip(":：").strip() == k:
                return i
    return -1


def cut_at_section(seg):
    """截到下一个章节标题为止。"""
    out = []
    for l in seg:
        if l.strip().rstrip(":：").strip() in SECTION_KEYS:
            break
        out.append(l)
    return out


def split_statement_and_sample(code):
    m = re.search(r"/\*+(.*?)\*+/", code, re.S)
    if not m:
        return None, None, None
    block = m.group(1)
    lines = [l.rstrip() for l in block.splitlines()]
    io_i, out_i = find_idx(lines, IN_KEYS), find_idx(lines, OUT_KEYS)
    if io_i < 0 or out_i < 0 or out_i <= io_i:
        return block, None, None

    def clean(seg):
        seg = list(seg)
        while seg and seg[0].strip() == "":
            seg.pop(0)
        while seg and seg[-1].strip() == "":
            seg.pop()
        return "\n".join(seg) + "\n"

    return (block,
            clean(cut_at_section(lines[io_i + 1:out_i])),
            clean(cut_at_section(lines[out_i + 1:])))


def safe(name):
    return "".join("_" if c in BAD_CHARS else c for c in name).strip(" .")


TEMPLATE = """{statement}

// ─────────────────────────────────────────────────────────────
// 题号：{no}        阶段：{stage} {theme}
// 参考行数：{loc} 行   来源：{origin}
// 样例：测试数据\\{stem}.in  →  {stem}.out
//
// 做法提醒：
//   1. 先手算样例，把「输入什么/输出什么/边界在哪」写成一张小卡片
//   2. 数据范围决定数组开多大（n ≤ 1000 就开 1005，永远多开一点）
//   3. 卡 20 分钟看提示、卡 40 分钟看题解，看完必须合上从空白重写一遍
// ─────────────────────────────────────────────────────────────

#include <iostream>
using namespace std;

int main() {{
    // TODO: 在这里写你的代码

    return 0;
}}
"""


def main():
    tests_only = "--tests-only" in sys.argv
    if not os.path.exists(CSV):
        print("找不到 " + CSV)
        return 1

    rows = list(csv.DictReader(io.open(CSV, encoding="utf-8-sig")))
    print("进度表 %d 行%s" % (len(rows), "（只重建测试数据，不动你的代码）" if tests_only else ""))

    n_tpl = n_test = n_nosample = n_missing = n_kept = 0
    nosample = []

    for r in rows:
        no = r["题号"]
        title = safe(r["题目"])
        stage = r["阶段"]
        theme = r["阶段主题"]
        loc = r["难度(行数)"]
        origin = r["原文件"]
        stem = "%s_%s" % (no, title)

        src_path = os.path.join(SRC, origin)
        if not os.path.exists(src_path):
            print("!! 源文件不存在: %s" % src_path)
            n_missing += 1
            continue

        block, sin, sout = split_statement_and_sample(read_text(src_path))
        statement = "/*" + block + "*/" if block else "/* 原题面未找到 */"

        if not tests_only:
            d = os.path.join(OUT_PRACTICE, stage)
            os.makedirs(d, exist_ok=True)
            tpl = os.path.join(d, stem + ".cpp")
            # 已经写过的题绝不覆盖
            if os.path.exists(tpl) and TODO_SENTINEL not in read_text(tpl):
                n_kept += 1
            else:
                with io.open(tpl, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(TEMPLATE.format(statement=statement, no=no, stage=stage,
                                             theme=theme, loc=loc, origin=origin, stem=stem))
                n_tpl += 1

        if sin is not None and sout is not None:
            os.makedirs(OUT_TESTS, exist_ok=True)
            with io.open(os.path.join(OUT_TESTS, stem + ".in"), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(sin)
            with io.open(os.path.join(OUT_TESTS, stem + ".out"), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(sout)
            n_test += 1
        else:
            n_nosample += 1
            nosample.append("%s  (%s)" % (stem, origin))

    print("\n生成模板: %d 个%s  -> %s" % (
        n_tpl, ("（跳过已写过的 %d 题，没动它们）" % n_kept) if n_kept else "", OUT_PRACTICE))
    print("生成测试数据: %d 组  -> %s" % (n_test, OUT_TESTS))
    print("缺样例的题: %d 个" % n_nosample)
    for x in nosample:
        print("   " + x)
    if n_missing:
        print("源文件缺失: %d" % n_missing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
