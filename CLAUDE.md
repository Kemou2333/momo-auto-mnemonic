# 墨墨助记 + 例句自动生成

## 今晚要做什么

为 Kemou（高三）墨墨账户今日剩余 + 明日要背的**新词**，同时生成助记和例句，写入墨墨。

风格规则：
- 助记 → MNEMONIC_RULES.md
- 例句 → PHRASE_RULES.md

环境变量 `MAIMEMO_TOKEN` 和 `GH_TOKEN` 已注入，脚本会自动用。

## 四步走

### 1. 读规则

```
view MNEMONIC_RULES.md
view PHRASE_RULES.md
```

### 2. 拉词

```
python3 run_mnemonics.py --fetch
```

输出"本次无新增" → 汇报"今晚无新增"并结束。否则继续。

### 3. 填模板

`--fetch` 会打印两块模板（`ALL_NOTES` 和 `ALL_PHRASES`），照着列出的词逐个填进 `run_mnemonics.py` 的同名区块。

- 多义词的例句**顺序必须和助记义项一致**（见 PHRASE_RULES.md "与助记的对应关系"）
- 同一个 `voc_id` 在 `ALL_PHRASES` 可以出现 1~3 次（多义词），单义词 1 次
- **所有文本字段（`note_text` / `phrase_en` / `phrase_zh`）必须用 Python 三引号 `"""..."""` 包裹**——不管内容里有没有引号、斜杠都用三引号，换行直接换行，不要写 `\n`

示例：

```python
ALL_NOTES = [
    ("voc-xxx", "hold up", "固定搭配", """核心画面：把东西固定住不让它动
不让掉 → 支撑
不让走 → 延误
不让动 → 抢劫"""),
]

ALL_PHRASES = [
    # 同一 voc_id 三条，顺序对应助记的 支撑 → 延误 → 抢劫
    ("voc-xxx", "hold up", """These pillars hold up the roof.""", """这些柱子支撑着屋顶。"""),
    ("voc-xxx", "hold up", """The flight was held up by bad weather.""", """航班因恶劣天气延误了。"""),
    ("voc-xxx", "hold up", """Two men held up the bank.""", """两个人抢劫了银行。"""),
]
```

### 4. 提交

```
python3 run_mnemonics.py
```

脚本会自动 POST 墨墨 → 更新 processed.json → 推到 main。

- 看到 `Git push: ✓ 成功` → 汇报结果，**任务结束**
- 看到 `Git push: ✗ 失败` → 把错误信息原样汇报给用户

## 硬性禁令

- ❌ 不在脚本之外做任何 git 操作（不 add / commit / push / 切分支 / 创 PR）
- ❌ 不用 MCP 工具修改任何文件
- ❌ 不修改 CLAUDE.md / MNEMONIC_RULES.md / PHRASE_RULES.md / README.md / settings.json / processed.json
- ❌ 不直接调墨墨 API（脚本会处理限速和重试）
- ❌ 不调外部 LLM API（你直接生成助记和例句）
- ✅ 只能改 `run_mnemonics.py` 的 `ALL_NOTES` 和 `ALL_PHRASES` 两个区块

token 无效 / 网络持续失败 → 立即停止并把错误原样告诉用户，不要自己想办法绕。

## 想了解项目背景

读 CONTEXT.md（仅在需要时读，日常 Routine 跑不用读）。
