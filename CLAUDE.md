# 墨墨助记自动生成 Routine

## 任务

为我的墨墨背单词账户里没有助记的单词自动生成并添加优质助记。

## 环境

- 环境变量 MAIMEMO_TOKEN：墨墨开放 API token，已在 Routine secret 中配置
- 助记生成规则与风格：见本仓库根目录 MNEMONIC_RULES.md，生成助记前必须完整读取
- API 限速：60 秒 40 次、5 小时 2000 次

## 墨墨 API 速查

Base URL: https://open.maimemo.com/open/api/v1
Auth header: Authorization: Bearer $MAIMEMO_TOKEN

### 1. 获取今日单词

    POST /study/get_today_items
    Body: { "limit": 1000 }
    Response: { "data": { "today_items": [{ "voc_id": "...", "voc_spelling": "..." }, ...] } }

### 2. 查询未来某日前要复习的词

    POST /study/query_study_records
    Body: { "next_study_date": { "end": "<YYYY-MM-DD>T23:59:59+08:00" }, "limit": 1000 }
    Response: { "data": { "records": [{ "voc_id": "...", "voc_spelling": "..." }, ...] } }

### 3. 创建助记

    POST /notes
    Body: { "note": { "voc_id": "...", "note_type": "<类型>", "note": "<纯文本内容>" } }
    Response: { "data": { "note": { "id": "..." } } }

note_type 可选值：词根词缀 / 词源 / 合成 / 派生 / 辨析 / 固定搭配 / 近反义词 / 串记 / 扩展 / 语法 / 其他

## 状态文件 processed.json

仓库根目录，记录所有已处理过的词，格式精简如下：

    { "voc-xxx": "accordingly", "voc-yyy": "essential" }

key 是 voc_id，value 是 spelling，方便快速查找。
文件不存在时视为空对象 {}。

## 执行流程

### Step 1：读取规则与状态

1. view MNEMONIC_RULES.md
2. 读取 processed.json，构造 done_set（voc_id 的集合）

### Step 2：收集候选单词

三个来源，合并去重：

A. 今日单词
POST /study/get_today_items

B. 未来 2 天要复习的词
POST /study/query_study_records，end 为今天 +2 天

C. 老词补充
POST /study/query_study_records 不加日期过滤，拉全量，按 next_study_date 升序，取不在 A/B 中的最早 50 个

### Step 3：过滤

从 candidates 中移除所有 voc_id 在 done_set 里的词。
剩余词即为本轮待处理词，直接进入 Step 4，不做额外 API 验证。

### Step 4：生成助记并写入

对每个待处理词：

1. 按 MNEMONIC_RULES.md 生成 1 条或 2 条 note（你直接生成，不调用外部 API）
2. 每条 note 分别 POST /notes 写入墨墨
3. 写入成功后立即把该词追加到内存中的 done_set
4. 每次 API 调用间 sleep 1.5 秒

HTTP 429 时等 60 秒重试，最多 3 次。单词失败不阻塞其他词。

### Step 5：写回 processed.json 并提交

1. 把更新后的 done_set 写入 processed.json（key-value 格式）
2. git push：

       git config user.email "routine@claude.ai"
       git config user.name "Claude Routine"
       git add processed.json
       git commit -m "chore: <N> new mnemonics <date>"
       git push origin main

push 失败时把 processed.json 内容输出到 log，下次运行靠墨墨现有数据兜底（不会重复创建，因为写入失败的词下次还会走同样流程但 POST /notes 会因已存在而报错被跳过）。

### Step 6：汇报

输出简短总结：
- 新增：X 词，Y 条 note
- 跳过（已处理）：X 词
- 失败：X 词（原因）
- 样本（5-10 个）：spelling | note_type | note 前 50 字

## 安全约束

- 只创建新助记，绝不删除或修改已有助记
- 速率限制时退避重试，最多 3 次后跳过
