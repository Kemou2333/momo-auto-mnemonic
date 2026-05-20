# 墨墨助记自动生成

## 每次运行流程

1. view MNEMONIC_RULES.md，理解助记风格和 note_type 选择规则
2. 运行 `python3 run_mnemonics.py --fetch`，查看今日待处理词及其 voc_id
3. 按 MNEMONIC_RULES.md 为每个词生成助记（1 条或 2 条），填入脚本的 ALL_NOTES 列表
4. 运行 `python3 run_mnemonics.py`，脚本会自动提交助记、更新 processed.json 并 push 到 main

## ALL_NOTES 格式

每条助记是一个 tuple，填入 run_mnemonics.py 的 ALL_NOTES 列表：

    (voc_id, spelling, note_type, note_text)

--fetch 输出会直接给出可粘贴的模板，按提示填写 note_type 和 note_text 即可。

## 硬性约束（违反会导致系统损坏）

- 不允许修改任何文件，除了往 run_mnemonics.py 的 ALL_NOTES 填内容
- 不允许直接读写 processed.json，只能通过运行脚本间接操作
- 不允许创建 git 分支，不允许创建 PR，只能 push 到 main
- 不允许为了测试而临时删除或修改 processed.json 里的条目
- 不允许自行调用墨墨 API，所有 API 调用都通过脚本完成
- 助记由你（Claude）直接生成，不调用外部 LLM API
- 如遇 MAIMEMO_TOKEN 无效或 GH_TOKEN 无效，立即停止并说明原因，不要自行探索其他方案

## 如果今日无新词

若 --fetch 返回"本次无新增"，直接汇报结束，不要做任何其他操作。
