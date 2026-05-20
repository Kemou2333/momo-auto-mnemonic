# 墨墨助记自动生成 Routine

## 任务

为我的墨墨背单词账户里**没有助记的单词**自动生成并添加优质助记。

## 环境

- `MAIMEMO_TOKEN`：墨墨开放 API token（已在 Routine secret 中配置）
- 墨墨 API 文档与示例：见 `memo-skills/memo-api/` 目录，**必须先读 `memo-skills/memo-api/SKILL.md`**
- 助记生成规则与风格：见本仓库根目录 `MNEMONIC_RULES.md`，**生成助记前必须完整读取**
- API 限速：60 秒 40 次、5 小时 2000 次。每处理一个词约消耗 2-3 次调用，注意节奏

## 执行流程

### Step 1：读取技能与规则
- `view memo-skills/memo-api/SKILL.md`
- `view memo-skills/memo-api/references/notes-api.md`
- `view memo-skills/memo-api/references/study-api.md`
- `view MNEMONIC_RULES.md`

### Step 2：收集待处理单词

按以下顺序收集，去重后形成一个 `voc_id` 列表：

**A. 今日单词**（最高优先级）
