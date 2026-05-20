# 墨墨助记自动生成

## 这是什么

这个项目每天自动为 Kemou（高三学生）的墨墨背单词账户生成助记。
墨墨是一个间隔复习 App，每天会安排一批单词复习。
你的任务是：晚上拉取明日词单和今日剩余词 → 为每个还没有助记的词生成助记 → 写入墨墨账户。

助记风格见 MNEMONIC_RULES.md，核心是找到词根/画面/本质逻辑串联所有义项，而不是简单翻译。

## 运行时机与设计

每天晚上 9 点跑一次。

为什么放晚上：墨墨学习日以凌晨 4:00 为分界。早晨 5 点跑的话，因为用户还没打开 App，
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

脚本会自动：
- 拉取今日剩余词（get_today_items）
- 拉取明日已安排的词（query_study_records 按日期范围）
- 合并去重并对照 processed.json 过滤
- 输出待处理词列表及可直接粘贴的 ALL_NOTES 模板

如果输出"本次无新增"，直接汇报结束即可。

### 第三步：生成助记

在 run_mnemonics.py 的 ALL_NOTES 列表里填入每个词的助记：

    (voc_id, spelling, note_type, note_text)

- voc_id 和 spelling 从 --fetch 输出里复制
- note_type 从 MNEMONIC_RULES.md 的规则选
- note_text 是你生成的助记正文，纯文本，用 \n 换行，60-140 字

一个词可以填两条（不同 note_type），分两行写。

### 第四步：提交

    python3 run_mnemonics.py

脚本会自动：
- POST 助记到墨墨 API（每条间隔 1.6 秒，避免触发限速）
- 更新 processed.json（记录已处理的词和日期）
- git push 到 main 分支
- 打印本次汇报

## 关于 API 限速

墨墨 API 限速：10 秒 20 次 / 60 秒 40 次 / 5 小时 2000 次。
脚本已内置 sleep 和重试逻辑，遇到 429 会自动等待 60 秒重试，最多 3 次。
你不需要手动处理限速，交给脚本就好。

## 关于 processed.json

记录所有已处理过的词（voc_id → {spelling, date}），是查重的唯一依据。
脚本运行时会自动读取和更新，你不需要也不应该手动修改它。

## 硬性约束

- 不允许创建 git 分支，不允许创建 PR，只能 push 到 main
- 不允许手动修改 processed.json（只能通过脚本写入）
- 不允许为了测试临时删除 processed.json 里的条目
- 不允许直接调用墨墨 API（所有 API 调用通过脚本完成）
- 不允许使用 MCP 工具修改或推送任何文件
- 不允许修改 run_mnemonics.py、MNEMONIC_RULES.md、README.md、settings.json 的内容
- 助记由你直接生成，不调用外部 LLM API
- 遇到 token 无效、网络持续失败等无法解决的问题，立即停止并说明原因
