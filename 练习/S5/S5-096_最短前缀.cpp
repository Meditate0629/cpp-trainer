/*
题目描述

一个字符串的前缀是从该字符串的第一个字符起始的一个子串。例如 "carbon"的字串是: "c", "ca", "car", "carb", "carbo",
和 "carbon"。注意到这里我们不认为空串是字串, 但是每个非空串是它自身的字串. 我们现在希望能用前缀来缩略的表示单词。
例如, "carbohydrate" 通常用"carb"来缩略表示. 现在给你一组单词, 要求你找到唯一标识每个单词的最短前缀
在下面的例子中，"carbohydrate" 能被缩略成"carboh", 但是不能被缩略成"carbo" (或其余更短的前缀) 因为已经有一个单词
用"carbo"开始
一个精确匹配会覆盖一个前缀匹配，例如，前缀"car"精确匹配单词"car". 因此 "car" 是 "car"的缩略语是没有二义性的,“car”
不会被当成"carriage"或者任何在列表中以"car"开始的单词.

关于输入

输入包括至少2行，至多1000行. 每行包括一个以小写字母组成的单词，单词长度至少是1，至多是20.

关于输出

输出的行数与输入的行数相同。每行输出由相应行输入的单词开始，后面跟着一个空格接下来是相应单词的没有二义性的最短前缀
标识符。

例子输入

carbohydrate
cart
carburetor
caramel
caribou
carbonic
cartilage
carbon
carriage
carton
car
carbonate

例子输出

carbohydrate carboh
cart cart
carburetor carbu
caramel cara
caribou cari
carbonic carboni
cartilage carti
carbon carbon
carriage carr
carton carto
car car
carbonate carbona
*/

// ─────────────────────────────────────────────────────────────
// 题号：S5-096        阶段：S5 函数·结构体·排序
// 参考行数：81 行   来源：试手练习\最短前缀.cpp
// 样例：测试数据\S5-096_最短前缀.in  →  S5-096_最短前缀.out
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
