# 墨墨助记自动生成

## 今晚要做什么

为 Kemou（高三）墨墨账户今日剩余 + 明日要背的**新词**生成助记，写入墨墨。

环境变量 `MAIMEMO_TOKEN` 和 `GH_TOKEN` 已注入，脚本自动用。

## 三步走

### 1. 拉词

```
python3 run_mnemonics.py --fetch
```

输出"本次无新增" → 汇报"今晚无新增"并结束。否则记下打印出的待处理词列表，进入第 2 步。

**主 agent 不要读 MNEMONIC_RULES.md**——规则文件很长，让子 agent 自己读，省主 agent 上下文。

### 2. 派发子 agent 生成助记

把第 1 步列出的待处理词**分批**（每批 20~30 个），逐批用 Agent 工具派发给 **Sonnet 子 agent**（`subagent_type: general-purpose`，**别用 Haiku**）。多批可以一条消息里并行多个 Agent 调用。

发给每个子 agent 的提示词模板：

```
为以下单词生成墨墨助记。先 view MNEMONIC_RULES.md 理解风格，
再按格式输出 Python 元组，不要解释、不要废话，直接输出代码块：

    ("voc-xxx", "spelling", "note_type", """note_text"""),
    ...

note_text 必须用三引号 """..."""，换行就直接换行不写 \n。

待处理词：
[贴入这一批的 voc_id + spelling]
```

### 3. 合并 + 提交

把所有子 agent 返回的元组拼到 `run_mnemonics.py` 的 `ALL_NOTES = [...]` 里，然后：

```
python3 run_mnemonics.py
```

脚本会自动 POST 墨墨 → 更新 processed.json → 推到 main。

- 看到 `Git push: ✓ 成功` → 简短汇报今晚搞定几个词、几条成功几条失败，**任务结束**
- 看到 `Git push: ✗ 失败` → 把错误信息原样汇报给用户

## 硬性禁令

- ❌ **不要创建 PR**（不调 `mcp__github__create_pull_request`、不跑 `gh pr create`，脚本 push 完就完事，创 PR 是浪费 token）
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
