# 墨墨助记自动生成

## 今晚要做什么

为 Kemou（高三）墨墨账户今日剩余 + 明日要背的**新词**生成助记，写入墨墨。

环境变量 `MAIMEMO_TOKEN` 和 `GH_TOKEN` 已注入，脚本自动用。

## 三步走

### 1. 拉词

```
python3 run_mnemonics.py --fetch
```

输出"本次无新增" → 汇报"今晚无新增"并结束。否则记下打印出的待处理词列表和**词数 N**，进入第 2 步。

**主 agent 不要读 MNEMONIC_RULES.md，也不要读子 agent 写入的助记内容**——这俩都很长，主上下文留给协调用。

### 2. 派发子 agent 生成助记（子 agent 自己直接写脚本）

#### 按词数决定派几个子 agent

| 待处理词数 N | 子 agent 数量 |
|---|---|
| N ≤ 40 | 1 个 |
| 41 ≤ N ≤ 60 | 2 个 |
| 61 ≤ N ≤ 90 | 3 个 |
| 91 ≤ N ≤ 120 | 4 个 |
| 更多 | 每 30 词 +1 个 |

把待处理词**均分**到各子 agent。

#### 派发方式

- **一次只派一个子 agent，等它返回再派下一个**（避免对同一文件并发 Edit 冲突）
- 全部用 Sonnet（`subagent_type: general-purpose`，明确指定 `model: sonnet`），**别用 Haiku**

#### 发给子 agent 的提示词模板

```
为以下单词生成墨墨助记，然后直接 Edit 写入 run_mnemonics.py 的 ALL_NOTES 列表。

步骤：
1. view MNEMONIC_RULES.md 理解风格
2. 为每个词生成 1~N 条助记，格式：
       ("voc-xxx", "spelling", "note_type", """note_text"""),
   note_text 必须三引号，换行就直接换行不写 \n
3. 用 Edit 工具把你写的所有元组追加到 run_mnemonics.py 的 ALL_NOTES 里。
   匹配以下精确锚点（这是 ALL_NOTES 结尾后的唯一标识）：

       old_string:
       ]

       ALL_PHRASES = [

       new_string:
           ("voc-1", "...", "...", """..."""),
           ("voc-2", "...", "...", """..."""),
           （...你的所有元组，每行一条，行首 4 空格缩进...）
       ]

       ALL_PHRASES = [

4. 完成后只报告：写了几个 voc_id、列出 voc_id（不要返回助记内容）

不要做：
- 不要读 MNEMONIC_RULES.md 以外的项目文件
- 不要碰 ALL_PHRASES
- 不要调外部 API、不要 git 操作

待处理词：
[贴入这一批的 voc_id + spelling 列表]
```

### 3. 提交 + 对账

```
python3 run_mnemonics.py
```

脚本自动 POST 墨墨 → 更新 processed.json → 推到 main。看脚本最后一行 `新增助记：X 词，Y 条成功，Z 条失败`：

| 情况 | 你要怎么报告 |
|---|---|
| X = N（待处理数） && Z = 0 && `Git push: ✓ 成功` | "今晚搞定 N 词，全部成功" + 结束 |
| X < N | "漏了 (N-X) 个词，子 agent 可能没写完" + 列漏掉的 voc_id |
| Z > 0 | "X 词处理完，Z 条 API 失败" + 把失败原因原样贴出 |
| SyntaxError / 脚本崩溃 | "脚本崩了，可能子 agent 写坏了" + 贴 traceback |
| `Git push: ✗ 失败` | 把 git 报错原样汇报 |

## 硬性禁令

- ❌ **不要创建 PR**（不调 `mcp__github__create_pull_request`、不跑 `gh pr create`，PR 是浪费 token）
- ❌ 不在脚本之外做任何 git 操作（不 add / commit / push / 切分支 / 拉远端）
- ❌ 不用 MCP 工具修改任何文件
- ❌ 不修改 CLAUDE.md / MNEMONIC_RULES.md / README.md / settings.json / processed.json / run_mnemonics.py 里 `ALL_NOTES` 之外的代码
- ❌ 不直接调墨墨 API（脚本会处理限速和重试）
- ❌ 不调外部 LLM API（子 agent 自己生成）
- ❌ **主 agent 不要读子 agent 写入的助记内容**（违背架构初衷，浪费上下文）
- ❌ **不要填 ALL_PHRASES**（例句功能已暂停）
- ✅ 只能间接改 `run_mnemonics.py` 的 `ALL_NOTES` 区块（通过子 agent 的 Edit）

token 无效 / 网络持续失败 → 立刻停止并把错误原样告诉用户，不要自己想办法绕。

## 想了解项目背景

读 CONTEXT.md（仅在需要时读，日常 Routine 跑不用读）。
