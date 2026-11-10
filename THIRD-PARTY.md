# 第三方内容与出处

## 题目、参考答案、测试数据

`IntroductionToComputationHomework2022-master/` 目录、`练习/` 里的题面注释、
`测试数据/` 里的样例（以及由它们派生的 `进度追踪表.模板.csv` 题目清单）
都来自：

- **仓库**：https://github.com/z-hz/IntroductionToComputationHomework2022
- **作者**：Zhang Huangzhao
- **许可**：MIT License, Copyright (c) 2022 Zhang Huangzhao

```
MIT License

Copyright (c) 2022 Zhang Huangzhao

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 本仓库做了哪些改动

- 从每份参考解顶部抽出**题面**，生成 `练习/S1..S9/*.cpp` 空模板（题面注释 + 空 `main`）
- 自动抽取**样例输入 / 输出**到 `测试数据/`，并用 250 份参考解逐题反跑核对；
  不一致的 14 处做了人工校正，写在 `训练网站/题目校正.json` 里
- 编写了判题网站 `训练网站/`、自检与重建脚本 `工具/`
- 排了一份 26 周学习路线 `C++零基础到250题通关计划.md`

⚠️ 参考解**不是神**：其中 3 道题的参考解有 bug（猴子分苹果、井底之蛙、矩阵取数游戏），
判题时以官方样例为准，细节见 `训练网站/README.md` 第四节。

## 编译器

[`工具/下载编译器.py`](工具/下载编译器.py) 只是从
[skeeto/w64devkit](https://github.com/skeeto/w64devkit/releases) 的官方发布页下载压缩包，
本仓库不重新分发编译器二进制。
