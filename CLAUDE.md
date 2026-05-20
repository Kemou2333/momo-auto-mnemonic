# 墨墨助记自动生成

## 每次运行流程

1. view MNEMONIC_RULES.md，理解助记风格和 note_type 选择规则
2. 运行 `python3 run_mnemonics.py --fetch`，查看今日待处理词及其 voc_id
3. 按 MNEMONIC_RULES.md 为每个词生成助记（1 条或 2 条），在脚本中填入 ALL_NOTES 列表
4. 运行 `python3 run_mnemonics.py`，提交助记并自动 push 回仓库

## ALL_NOTES 格式

每条助记是一个 tuple，填入 run_mnemonics.py 的 ALL_NOTES 列表：

    (voc_id, spelling, note_type, note_text)

--fetch 输出会直接给出可粘贴的模板，按提示填写 note_type 和 note_text 即可。

## 约束

- 助记由你（Claude）直接生成，不调用外部 API
- 唯一允许写入的文件是 processed.json（脚本自动处理）
- 不修改 CLAUDE.md、MNEMONIC_RULES.md、README.md、run_mnemonics.py 的逻辑部分
- 如遇 MAIMEMO_TOKEN 无效或 GH_TOKEN 无效，立即停止并说明原因
