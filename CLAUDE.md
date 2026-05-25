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

### 2. 生成助记并写入脚本

1. 读 MNEMONIC_RULES.md 理解助记风格
2. 为每个待处理词生成 1~N 条助记，格式：

   ```
   ("voc-xxx", "spelling", "note_type", """note_text"""),
   ```

   note_text 必须用三引号 `"""..."""`，换行就直接换行不写 `\n`
3. 用 Edit 工具把所有元组写入 `run_mnemonics.py` 的 `ALL_NOTES` 列表，
   行首 4 空格缩进。

### 3. 提交 + 对账

```
python3 run_mnemonics.py
```

脚本自动 POST 墨墨 → 更新 processed.json → 推到 main。看脚本最后一行 `新增助记：X 词，Y 条成功，Z 条失败`：

| 情况 | 你要怎么报告 |
|---|---|
| X = N（待处理数） && Z = 0 && `Git push: ✓ 成功` | "今晚搞定 N 词，全部成功" + 结束 |
| X < N | "漏了 (N-X) 个词" + 列漏掉的 voc_id |
| Z > 0 | "X 词处理完，Z 条 API 失败" + 把失败原因原样贴出 |
| SyntaxError / 脚本崩溃 | "脚本崩了" + 贴 traceback |
| `Git push: ✗ 失败` | 把 git 报错原样汇报 |

## 硬性禁令

- ❌ **不要创建 PR**（不调 `mcp__github__create_pull_request`、不跑 `gh pr create`，PR 是浪费 token）
- ❌ 不在脚本之外做任何 git 操作（不 add / commit / push / 切分支 / 拉远端）
- ❌ 不用 MCP 工具修改任何文件
- ❌ 不修改 CLAUDE.md / MNEMONIC_RULES.md / README.md / settings.json / processed.json / run_mnemonics.py 里 `ALL_NOTES` 之外的代码
- ❌ 不直接调墨墨 API（脚本会处理限速和重试）
- ❌ 不调外部 LLM API（你自己生成助记）
- ❌ **不要填 ALL_PHRASES**（例句功能已暂停）
- ✅ 只能改 `run_mnemonics.py` 的 `ALL_NOTES` 区块

token 无效 / 网络持续失败 → 立刻停止并把错误原样告诉用户，不要自己想办法绕。

## 想了解项目背景

读 CONTEXT.md（仅在需要时读，日常 Routine 跑不用读）。
