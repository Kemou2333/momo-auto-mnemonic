# maimemo-mnemonic-bot

每天自动为墨墨背单词中的今日单词生成助记，并通过墨墨开放 API 写回账户。
助记风格以词根词源、空间画面、近义辨析为主，力求用一个核心逻辑串联单词的所有义项，而不是简单罗列释义。
由 Claude Code Routines 驱动，每天早晚各运行一次。

## 工作原理

1. 每天从墨墨 API 拉取今日单词列表
2. 与本地记录（`processed.json`）对比，过滤掉已处理的词
3. 由 Claude 为每个新词生成 1-2 条助记（风格规则见 `MNEMONIC_RULES.md`）
4. 通过墨墨开放 API 写入账户
5. 更新 `processed.json` 并推回仓库（以便后面查重）


## 缘起

有时候问 AI 单词意思，会得到很有启发的解释——比如聊到 *hold up* 才发现「支撑、延误、抢劫」背后其实是同一个动作，或者 *determine* 的「测定」和「决心」原来共享同一个词根画面。这类助记比死记硬背有趣得多，于是开始手动往墨墨里加。

加着加着就在想：能不能让 LLM 每天自动帮我做这件事？于是就有了这个项目。

鄙人只是一枚高三生，纯 vibe coding 实现，功过都归 Claude（x）。代码能跑就行，还请多多体谅 www

---

*Powered by [Claude Code Routines](https://claude.ai/code) × [墨墨开放 API](https://open.maimemo.com)*
