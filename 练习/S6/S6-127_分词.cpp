/*
题目描述

给定一个包含n个单词的英文词典和m个只由英文字母组成的字符串。
判断这些字符串能否由词典中的单词组成。
比如词典中包含5个单词："Jim", "and", "cat","like", "dog"
这些单词能组成"Jimlikecatanddog"、"doglikecatandcatlikedog"等，
但是不能组成"catlikeme"
为了简化问题，所有的字母都是小写,而且词典中的所有单词长度都一样。

关于输入

第一行两个正整数，n和m（n，m都不超过100）；
接下来n行，每行一个单词，每个单词长度不超过20；
接下来m行，每行一个字符串，长度不超过1000；

关于输出

m行，表示词库中的单词能否组成该字符串，能输出"Yes"，不能输出"No"。

例子输入

10 5
did
not
and
but
hit
run
cat
dog
pig
cow
cathitdoganddogrun
doghitpigbutpigdidnotrun
pighitcowandcowdidrun
cowhitcatandcatcry
catdogpigandcowarehungry

例子输出

Yes
Yes
Yes
No
No
*/

// ─────────────────────────────────────────────────────────────
// 题号：S6-127        阶段：S6 递归与搜索（DFS/回溯）
// 参考行数：91 行   来源：第三阶段编程练习4\分词.cpp
// 样例：测试数据\S6-127_分词.in  →  S6-127_分词.out
//
// 做法提醒：
//   1. 先手算样例，把「输入什么/输出什么/边界在哪」写成一张小卡片
//   2. 数据范围决定数组开多大（n ≤ 1000 就开 1005，永远多开一点）
//   3. 卡 20 分钟看提示、卡 40 分钟看题解，看完必须合上从空白重写一遍
// ─────────────────────────────────────────────────────────────

#include <iostream>
using namespace std;

int main() {
    // TODO: 在这里写你的代码

    return 0;
}
