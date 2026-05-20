# 墨墨助记自动生成 Routine

## 任务

为我的墨墨背单词账户里没有助记的单词自动生成并添加优质助记。

## 环境

- 环境变量 `MAIMEMO_TOKEN`：墨墨开放 API token，已在 Routine secret 中配置
- 助记生成规则与风格：见本仓库根目录 `MNEMONIC_RULES.md`，**生成助记前必须完整读取**
- API 限速：60 秒 40 次、5 小时 2000 次

## 墨墨 API 速查（本任务只用以下 4 个端点）

Base URL: `https://open.maimemo.com/open/api/v1`
Auth header: `Authorization: Bearer $MAIMEMO_TOKEN`

### 1. 获取今日单词

    POST /study/get_today_items
    Content-Type: application/json
    Body: { "limit": 1000 }

    Response: { "today_items": [{ "voc_id": "...", "voc_spelling": "...", "is_new": bool, "is_finished": bool }, ...] }

### 2. 查询未来某日前要复习的词

    POST /study/query_study_records
    Content-Type: application/json
    Body: {
      "next_study_date": { "end": "<YYYY-MM-DD>T23:59:59+08:00" },
      "limit": 1000
    }

    Response: { "records": [{ "voc_id": "...", "voc_spelling": "...", "next_study_date": "..." }, ...] }

### 3. 查询某词的助记（用于二次安全验证）

    GET /notes?voc_id=<voc_id>

    Response: { "notes": [{ "id": "...", "note_type": "...", "note": "...", "status": "PUBLISHED" }, ...] }

### 4. 创建助记

    POST /notes
    Content-Type: application/json
    Body: {
      "note": {
        "voc_id": "...",
        "note_type": "<词根词缀|词源|派生|辨析|近反义词|串记|合成|固定搭配|扩展|语法|其他>",
        "note": "<助记内容纯文本>"
      }
    }

    Response: { "note": { "id": "...", ... } }

## 状态文件 processed.json

仓库根目录的 `processed.json` 记录已处理过的单词，结构：

    [
      { "voc_id": "voc-xxx", "spelling": "accordingly", "added_at": "2026-05-20T05:30:00+08:00", "note_type": "词根词缀" }
    ]

如果文件不存在，视为空数组 `[]`。

## 执行流程

### Step 1：读取规则与状态

1. `view MNEMONIC_RULES.md`，完整理解助记风格与 note_type 选择规则
2. 读取 `processed.json`（不存在则视为空数组），构造一个 voc_id 集合，称为 `done_set`

### Step 2：收集候选单词

按顺序拼接三个来源，去重后形成 `candidates` 列表（保留 voc_id 与 spelling）：

**A. 今日单词**
调用 `/study/get_today_items` body `{"limit":1000}`，取所有 `today_items`。

**B. 未来 2 天要复习的词**
计算日期：`tomorrow_plus_1 = 今天 + 2 天`，调用 `/study/query_study_records` body：
`{"next_study_date":{"end":"<tomorrow_plus_1>T23:59:59+08:00"},"limit":1000}`

**C. 老词补充**
调用 `/study/query_study_records` body `{"limit":1000}` 拉取已添加的记忆计划（按 next_study_date 升序），从中筛出**不在 A、B、`done_set` 中**的最早 50 个词。

### Step 3：过滤 done_set

把 `candidates` 中 voc_id 已在 `done_set` 里的词全部移除。

### Step 4：二次安全验证

对剩余每个候选词，调用 `GET /notes?voc_id=<id>`：
- 如果返回的 notes 数组里有任何 status 为 PUBLISHED 的条目 → 跳过该词，并把它**加入 done_set 写回文件**（说明 processed.json 漏记了）
- 否则进入 Step 5

每次 API 调用间 sleep 1 秒以避免触发速率限制。

### Step 5：生成助记并写入

对每个通过验证的词：

1. **生成助记**：严格按 `MNEMONIC_RULES.md` 生成。你（Claude）直接生成，不调用外部 API
2. **写入墨墨**：POST /notes，body 见上方端点 4
3. **更新本地状态**：把这个词追加到 `done_set` 内存列表
4. sleep 1.5 秒

如果某次 POST 失败（HTTP 429 限速），等待 60 秒后重试，最多 3 次。其他失败记录下来，不阻塞后续词。

### Step 6：写回 processed.json 并提交

1. 把更新后的 `done_set` 序列化为格式化 JSON，写入仓库根目录 `processed.json`
2. 执行 git 命令提交并推送：

       git config user.email "routine@claude.ai"
       git config user.name "Claude Routine"
       git add processed.json
       git commit -m "chore: update processed.json - <N> new mnemonics on <date>"
       git push origin main

3. 如果 push 失败，把 processed.json 的内容输出到 routine log，方便人工排查

### Step 7：汇报

输出本次运行总结：
- 本次新增了多少助记
- 跳过了多少（在 processed.json 中）
- 二次验证拦截了多少（processed.json 漏记）
- 失败了多少及原因
- 列出新增的 5-10 个词作为样本（spelling + note_type + note 前 60 字）

## 安全约束

- **绝对不删除任何已有助记**（不允许 status=DELETED，不允许 DELETE 调用）
- **绝对不更新已有助记**（不允许 POST /notes/{id}）
- 本任务只读取学习数据、查询 notes、创建新 notes
- 触发速率限制时退避重试，最多 3 次后跳过该词

## 失败兜底

如果 git push 失败（罕见），processed.json 没能写回但助记已经创建，下次运行会通过 Step 4 的二次验证自动跳过，不会重复创建。这是设计上的容错。
