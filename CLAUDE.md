# 墨墨助记自动生成

## 这是什么

这个项目每天自动为 Kemou（高三学生）的墨墨背单词账户生成助记。
墨墨是一个间隔复习 App，每天会安排一批单词复习。
你的任务是：晚上拉取明日词单和今日剩余词 → 为每个还没有助记的词生成助记 → 写入墨墨账户。

助记风格见 MNEMONIC_RULES.md，核心是找到词根/画面/本质逻辑串联所有义项，而不是简单翻译。

## 运行时机与设计

每天晚上 9 点跑一次。

为什么放晚上：墨墨学习日以凌晨 4:00 为分界。早晨跑的话，因为用户还没打开 App，
墨墨可能没有生成当日词单（API 返回空）。晚上 9 点用户已经背完今天的词，明天的词单
也已经被算法确定，这时候拉取最可靠。

脚本会同时拉取：
- 今日剩余的词（万一白天有什么没处理完）
- 明日已安排的词

合并去重后扣掉 processed.json 里已处理的部分，剩下的就是本次要生成助记的词。

## 认证方式

所有操作只能通过环境变量和脚本完成，不允许使用 MCP 工具操作 GitHub：

- 墨墨 API 认证：环境变量 MAIMEMO_TOKEN，由脚本自动读取
- GitHub 推送认证：环境变量 GH_TOKEN，由脚本自动读取并配置 remote URL
- MCP GitHub 工具：仅可读取（查看文件/分支等），不允许用它推送代码或修改文件

## 运行流程

### 第一步：了解规则

    view MNEMONIC_RULES.md

### 第二步：拉取今日+明日待处理单词

    python3 run_mnemonics.py --fetch

如果输出"本次无新增"，直接汇报结束。

### 第三步：在脚本里填入助记

按 MNEMONIC_RULES.md 生成助记，编辑 run_mnemonics.py 的 ALL_NOTES 列表：

    (voc_id, spelling, note_type, note_text)

note_text 用 \n 换行，纯文本，60-140 字。一个词可填多条（不同 note_type）。

注意：你修改 run_mnemonics.py 的 ALL_NOTES 部分是被允许的（这是脚本预留的填写区），
但提交完成后，脚本会自动把 ALL_NOTES 还原为空。不要担心，也不要试图自己处理。

### 第四步：提交

    python3 run_mnemonics.py

脚本会自动完成所有后续操作：
- POST 助记到墨墨 API
- 更新 processed.json
- 把 ALL_NOTES 还原为空
- git add processed.json（只这一个文件）
- git commit + git push origin HEAD:main（直接推到 main，即使当前在 feature 分支）

执行完脚本之后，你的任务就完成了。直接汇报结果即可。

## 极其重要：不要在脚本之外做任何 git 操作

脚本已经完整处理了 git push 流程。你不需要、也不应该自己执行任何额外的 git 命令。

具体禁止：
- 不要 git add 任何文件（除非是脚本内部的操作）
- 不要 git commit
- 不要 git push
- 不要 git checkout、git branch、创建新分支
- 不要创建 Pull Request
- 不要使用 MCP 工具修改任何文件

如果脚本运行后报告 "Git push: ✓ 成功"，说明一切都已完成。

如果脚本报告 "Git push: ✗ 失败"，把错误信息原样汇报给用户，让用户处理。
不要自己尝试用其他方式推送或创建 PR。

## 关于 API 限速

墨墨 API 限速：10 秒 20 次 / 60 秒 40 次 / 5 小时 2000 次。
脚本已内置 sleep 和重试逻辑。你不需要手动处理。

## 关于 processed.json

记录所有已处理过的词（voc_id → {spelling, date}），是查重的唯一依据。
脚本自动读取和更新。你不需要、也不应该手动修改它。

## 硬性约束（违反会损坏系统）

- 不允许直接读写 processed.json（只能通过脚本间接操作）
- 不允许为了测试临时删除 processed.json 里的条目
- 不允许在脚本之外做任何 git 操作（脚本会自己 push）
- 不允许创建分支或 PR
- 不允许直接调用墨墨 API（所有 API 调用通过脚本完成）
- 不允许修改 CLAUDE.md、MNEMONIC_RULES.md、README.md、settings.json 的内容
- run_mnemonics.py 只允许修改 ALL_NOTES 区块（脚本会自动还原），其他部分不能动
- 助记由你直接生成，不调用外部 LLM API
- 遇到 token 无效、网络持续失败等无法解决的问题，立即停止并说明原因
