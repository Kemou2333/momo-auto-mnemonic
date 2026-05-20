# 墨墨助记自动生成 Routine

## 任务

为我的墨墨背单词账户里没有助记的单词自动生成并添加优质助记。

## 环境

- MAIMEMO_TOKEN：墨墨开放 API token（已在 Routine secret 中配置）
- 墨墨 API 文档与示例：见 memo-skills/memo-api/ 目录，必须先读 memo-skills/memo-api/SKILL.md
- 助记生成规则与风格：见本仓库根目录 MNEMONIC_RULES.md，生成助记前必须完整读取
- API 限速：60 秒 40 次、5 小时 2000 次，每处理一个词约消耗 2-3 次调用，注意节奏

## 执行流程

### Step 1：读取技能与规则

    view memo-skills/memo-api/SKILL.md
    view memo-skills/memo-api/references/notes-api.md
    view memo-skills/memo-api/references/study-api.md
    view MNEMONIC_RULES.md

### Step 2：收集待处理单词

按以下顺序收集，去重后形成一个候选列表：

A. 今日单词（最高优先级）

    POST /study/get_today_items
    body: { "limit": 1000 }

B. 未来 2 天要复习的词

    POST /study/query_study_records
    body: { "next_study_date": { "end": "<今日+2天>T23:59:59+08:00" }, "limit": 1000 }

C. 老词补充（每次最多 50 个）

从 query_study_records 全量列表中按 add_date 升序，挑出不在 A/B 中的词，补到 50 个。

### Step 3：过滤已有助记的词

对每个候选词，调用：

    GET /notes?voc_id=<id>

若返回的 notes 数组里有 status 为 PUBLISHED 的条目，则跳过该词。

### Step 4：生成并写入助记

对每个待处理词：

1. 严格按 MNEMONIC_RULES.md 的规则与风格生成助记，你（Claude）直接生成，不要调用任何外部 API
2. 写回墨墨：

        POST /notes
        body: { "note": { "voc_id": "...", "note_type": "<选定类型>", "note": "<助记内容>" } }

3. 每处理完一个词 sleep 1-2 秒，避免触发速率限制

### Step 5：汇报

任务结束后输出简短总结：
- 本次处理了多少词
- 跳过了多少（已有助记）
- 失败了多少（附原因）
- 列出新增的 5-10 个词作为样本

## 安全约束

- 不要删除任何已有的助记
- 不要更新已有助记（只创建新的）
- 触发速率限制（HTTP 429）时，等待 60 秒后重试，最多重试 3 次
- 任何一个词处理失败不影响其他词继续处理
