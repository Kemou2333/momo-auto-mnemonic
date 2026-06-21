# 词书模式（--wordbook）操作指南

给一整本词书（尤其**云词库**，如《有道四级核心 500 词之真题词汇》）里的词
**提前批量预生成助记**。这样无论你哪天在 App 里选中其中某个词，助记都已经就位，
彻底解决"新词书每天只冒 3~4 个词、临场才背"的尴尬。

> ⚠️ **这是手动模式，不是日常 Routine。** 日常 Routine 永远跑 `--fetch`（日常模式），
> 只有你明确说"用词书模式处理某本书"时才走这套流程。AI 不要默认进词书模式。

---

## 为什么词表要自己给（API 拉不到云词库）

实测墨墨开放 API **只能读到你自己创建的云词本**（`/notepads` 返回的是你建的词本），
**拉不到官方云词库**（《有道四级核心 500 词》这种）——没有 `/books`、没有搜索接口，
`/notepads` 的 keyword 参数被忽略。

所以词书模式的词表用**文本文件**给：一行一个单词。你可以从词库页面复制粘贴，
或用任何方式导出。脚本会把每个拼写用 `GET /vocabulary` 解析成 `voc_id`
（结果缓存到 `.wordbook_cache.json`，分批跑不重复查）。

> 关于"添加单词"：创建助记（note）**不会**把词加进你的学习计划——只有 App 里"选词"
> 才会。所以词书模式的本质是**预置助记**：词还没选时先把助记挂好，等你选了就直接看到。
> 已经选过的词，日常 Routine 滚动复习时也会照顾到，所以默认**未选词优先**。

---

## 用法

```bash
# 1) 把词书的单词存成文本文件，一行一个（# 或 // 开头的行会被忽略）
#    文件名建议 wordbook*.txt —— 已在 .gitignore，不会误提交
cat > wordbook.txt <<'EOF'
abandon
ability
abnormal
...
EOF

# 2) 看待处理清单（默认只列"未选词"，未选优先）
python3 run_mnemonics.py --wordbook wordbook.txt

# 分批：本批最多 N 个
python3 run_mnemonics.py --wordbook wordbook.txt --limit 50

# 连"已选但还没助记"的词也一起生成
python3 run_mnemonics.py --wordbook wordbook.txt --include-selected

# 3) 按 MNEMONIC_RULES.md 给清单里的词生成助记，填入 run_mnemonics.py 的 ALL_NOTES

# 4) 提交（和日常一样）——POST 墨墨 → 更新 processed.json → push
python3 run_mnemonics.py
```

脚本输出会告诉你：读到多少词、命中/查无多少 voc_id、已有助记多少、
待处理多少（未选 / 已选拆开）、本批输出多少。查无 voc_id 的词会单独列出，
核对拼写后可手工处理。

---

## 词量大（200~300 词）怎么办：分批 + 可选子 agent

单个 agent 一次性给两三百个词写助记会超时。两种做法：

### A. 分批，主 agent 自己写（简单、可控）

每次 `--limit 50`，主 agent 生成 50 条 → 提交 → 再跑下一批。`.wordbook_cache.json`
让重复跑不再重复解析 voc_id；processed.json 让已提交的词自动跳过。
跑几轮就清完一本书。**这是默认推荐做法。**

### B. 派子 agent 并行（量特别大时）

一次性把整本书的待处理清单（`--limit` 不传，输出全部）切成几段，
每段派一个子 agent：给它该段的 `(voc_id, spelling)` 列表 + 让它读 `MNEMONIC_RULES.md`
按风格生成助记，回填 `ALL_NOTES`，最后主 agent 统一跑一次提交。

> 注意（来自 CONTEXT.md 的教训）：每派一个子 agent，系统提示 + `MNEMONIC_RULES.md`
> 都要重发一遍，token 开销不小。**所以子 agent 只在一次性大批量（如整本 230 词）
> 时才值得用；日常几十词坚决不派。** 派子 agent 仅限词书模式这种一次性场景。

### 速率与时限提醒

- voc_id 解析每词约 0.4s；231 词首次解析约 1.5~2 分钟（之后走缓存）
- 提交助记每条 sleep 1.6s，50 词约 1.5 分钟
- 注意墨墨 5 小时 2000 次 API 速率上限，别短时间反复狂跑
- 一批别贪太多，50~80 词/批比较稳

---

## 两本目标词书

- 《有道四级核心 500 词之真题词汇》（正在背，约 231 词，~110 已选 / ~130 未选）
- 《4 级核心高频词》（备选）

两本都是官方云词库，API 拉不到，按上面的"文本文件"流程给词表即可。
未选词优先生成，已选词留给日常 Routine 或加 `--include-selected` 一并处理。
