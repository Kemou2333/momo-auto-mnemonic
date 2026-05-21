# 项目上下文文档

本文档记录这个项目的完整设计背景、决策理由和踩过的坑。
新开对话的 AI 读完这一份文档应该能完全理解项目并参与改进。

---

## 项目缘起与愿景

**用户 Kemou** 是一名高三学生，正在用墨墨背单词 App 准备高考。日均背词约 40 个，
新词约 5 个，累计已背 1500+ 词。

**触发点**：在和 Claude 聊天时，发现 AI 能给出极有启发性的单词解释——
例如 *hold up* 看似"支撑/延误/抢劫"三个无关含义，本质都是「把东西固定住不让它动」
这个核心动作的不同投影；*determine* 的"测定"与"决心"共享「给模糊事物画上边界」
这个词根画面。这类助记比死记硬背高效得多。

**愿景**：让 LLM 自动每天为正在学习的单词生成这种风格的助记，写入墨墨账户，
背词时直接看到，无需手动操作。

---

## 助记风格指南（核心！）

这是整个项目的灵魂。让 AI 模仿 Kemou 风格生成助记，最重要的是这一节。

### 总原则

**用最少的字，理清单词的不同义项为什么是这些意思**。找到它们的共同本质（物理画面、
空间感、动作隐喻、词根含义、类比逻辑），串成一个画面或逻辑链。**不是简单罗列翻译**。

「看的清楚最重要」——背词每个词只看几秒钟，所以排版要换行、要扫读友好。

### 风格范例（已通过用户审查的写法）

**多义词找共同画面：**

```
survey
核心画面：从高处扫视全局
居高看地形 → 勘测
居高看民意 → 调查问卷
居高看全貌 → 综述、总览
全是同一个动作，只是对象不同。
```

```
plain
核心：没有多余的东西
没装饰 → 朴素的
没障碍 → 平原
没修饰 → 清楚明白的（plain English）
没加料 → 原味的（plain yogurt）
```

```
hold up
核心画面：把东西固定住不让它动
不让掉 → 支撑
不让走 → 延误
不让动 → 抢劫
```

**词根拆解（只在用户能秒 get 时才追）：**

```
determine
de-（彻底）+ termine（边界，同根 terminal、terminate）
给模糊的东西画上边界
给客观值划边界 → 测定
给主观意志划边界 → 决心
```

```
emerge
e-（出来）+ merge（沉入，同根 submerge）
从沉入状态出来 → 浮现、出现、脱颖而出
```

**同根词群对比：**

```
sympathy / empathy / apathy
-pathy = 感受
sym-（共同）→ 一起感受 → 同情
em-（进入）→ 进入对方感受 → 共情
a-（没有）→ 没有感受 → 冷漠
```

**近义辨析：**

```
essential vs necessary
essential：没有就不成其为这个东西（本质层面）
necessary：逻辑上、条件上需要
```

**简单词一句话搞定（不要硬凑）：**

```
seaside
sea + side，海边。英式偏好 seaside，美式更常说 beach。
```

**否定句常驻词：说明使用场景：**

```
budge
几乎只用于否定：won't budge / can't budge
人不挪步、物不移动、立场不变，都能用
```

### 反面教材（避免的写法）

❌ "accordingly 因此、相应地。表示根据前文做相应处理。" （只是翻译没本质）
❌ "ac 加 cord 加 ly 等于 accordingly" （拆了没解释）
❌ "由 according 加 ly 派生而来" （太简单没信息）
❌ 把汉字读音/谐音/口诀写进去（这些 note_type 被明确禁用）
❌ 列出五条独立例句作为助记内容
❌ "这是 X 的全部逻辑"、"本质就是…"这种总结废话
❌ 一句话能讲清的硬扩成 200 字

### 格式硬约束

- 纯文本，不要任何 markdown（不要加粗、不要标题、不要列表符号）
- 换行很重要，每个义项、每层推导单独一行
- 用箭头 → 表示"推出"，用 / 表示"或"，用括号补充
- 60-140 字为宜
- 简单词可以更短

### 一词多条 note

一个词可以生成多条不同 note_type 的 note（比如词根词缀 + 辨析）。
但每条要独立完整，不要把两种内容塞同一条 note 里。

详细的 note_type 选择规则见 MNEMONIC_RULES.md（不在本文档重复）。

---

## 系统架构

### 数据流

```
墨墨 API ←─── run_mnemonics.py ────→ GitHub 仓库
   ↑              ↑       │              ↑
   │              │       │              │
   │            Claude（生成助记）         │
   │              │       │              │
   │           CLAUDE.md  MNEMONIC_      processed.json
   │           （流程）   RULES.md        （查重）
   │                     （风格）              │
   │                                          │
   │                                          ↓
   └────── 写入助记 ────────────────── GitHub Actions
                                       （生成 chart.svg）
```

### 触发链路

1. **Claude Code Routine** 每天晚上 9 点（北京时间）触发
2. Routine 拉取 GitHub 仓库到云端环境，由启动脚本注入两个环境变量：
   - `MAIMEMO_TOKEN` - 墨墨开放 API token
   - `GH_TOKEN` - GitHub Personal Access Token
3. Claude 读 `CLAUDE.md` 了解流程，读 `MNEMONIC_RULES.md` 了解风格
4. Claude 跑 `python3 run_mnemonics.py --fetch` 拉今日剩余+明日待处理词
5. Claude 把生成的助记填入 `run_mnemonics.py` 的 `ALL_NOTES` 列表
6. Claude 跑 `python3 run_mnemonics.py` 提交
7. 脚本完成：POST 墨墨 API → 更新 processed.json → 清空 ALL_NOTES → git push 到 main
8. GitHub Actions 监测到 processed.json 变更，自动生成最新 chart.svg 并 commit

### 文件清单与作用

| 文件 | 作用 | 谁能改 |
|---|---|---|
| `CLAUDE.md` | Routine 每次运行时 Claude 读的流程指令 | 只能人类改 |
| `MNEMONIC_RULES.md` | 助记风格规则与 note_type 选择指南 | 只能人类改 |
| `PHRASE_RULES.md` | 例句风格规则（写作规范 TODO，先有骨架） | 只能人类改 |
| `run_mnemonics.py` | 唯一脚本，负责拉词/提交/推送一条龙 | 只能人类改逻辑，Claude 只能改 ALL_NOTES / ALL_PHRASES 区块 |
| `processed.json` | 记录所有已处理过的词，查重的唯一依据 | 只能脚本写 |
| `.claude/settings.json` | 权限配置（哪些 bash 命令允许/拒绝） | 只能人类改 |
| `scripts/gen_chart.py` | GitHub Actions 用，生成累计词数折线图 | 偶尔改 |
| `.github/workflows/update-chart.yml` | GitHub Actions 配置 | 偶尔改 |
| `chart.svg` | 进度图，README 引用 | Actions 自动生成 |
| `README.md` | 项目对外说明 | 人类改 |
| `CONTEXT.md` | 本文档，给新 AI 看的设计上下文 | 人类改 |

### 脚本三种模式

```bash
python3 run_mnemonics.py --fetch         # 拉今日+明日待处理，输出 ALL_NOTES 模板
python3 run_mnemonics.py --backfill 100  # 拉 N 个未处理的老词（批量回填用）
python3 run_mnemonics.py                 # 提交 ALL_NOTES 里的助记
```

---

## 关键技术决策

### 为什么晚上 9 点跑，不是早上 5 点半

最初设置 5:30 跑，结果发现：墨墨学习日以**凌晨 4:00** 为分界（不是午夜），
但 4:00 后用户没打开 App 之前，墨墨服务器**不会生成当日词单**，API 返回空列表。
晚上 9 点用户已背完今天的词，明天的词单也已被算法确定，这时候拉取最稳。

脚本同时拉今日剩余 + 明日，合并去重，一次解决。

### 为什么用 Python tuple + 三引号字符串

最初用普通字符串 `"..."` 装 note_text，结果 Claude 写助记时如果用到英文双引号
（比如 `"下巴"`），就会引号冲突导致 Python 语法错误。试过几次都翻车。

改用三引号 `"""..."""` 后彻底解决——三引号内可以容纳任何字符（除非连续三个双引号，
中文助记里不可能出现）。换行也直接在源码里真换行，比 \n 更清晰。

考虑过用 JSON 文件分离数据，但工程量大且增加复杂度。三引号方案是最优 tradeoff。

### 为什么 processed.json 查重，不是每次问 API

之前考虑过两种查重方式：
- A：仅用 processed.json（本地状态）
- B：processed.json 过滤 + 每个候选词再调 `GET /notes?voc_id=X` 二次验证

最终选 A。理由：API 调用慢，每天 50 词就要多 50 次调用消耗速率配额。
processed.json 由脚本一致维护，足够可靠。极端情况（脚本写入但 push 失败）下，
墨墨 API 会因为 note 已存在而拒绝重复创建，是天然兜底。

### 为什么用 Claude Code Routines，不是 cron + LLM API

- Claude Routines 直接用 Claude，不需要付 Anthropic API token 钱
- 云端跑，电脑关着也行
- 直接绑定 GitHub 仓库，环境隔离
- 缺点：每次运行是无状态的，需要把所有上下文写进 CLAUDE.md

### 为什么直推 main，不走 PR

Routine 默认会把改动推到 `claude/...` 前缀的 feature 分支，再让用户合 PR。
对这个项目来说太麻烦了——每天一次的小改动（processed.json 加几行）都要手动合，
体验很差。

解决方案：脚本里直接用 `git push origin HEAD:main`，绕过 feature 分支，
即使 Claude 当前在某个 feature 分支也能直接把 commit 推到 main。

### 为什么 settings.json 用默认 deny + 白名单

Claude 在 Routine 里有"过度热情"倾向，完成主要任务后还想做额外的事——
比如脚本已经把数据推到 main 了，它还想 push 一次 feature 分支、创建 PR、
"以备不时之需"。这些都是脚本之外的画蛇添足。

settings.json 现在用 `defaultMode: "deny"`，allow 列表精确列出脚本必需的命令，
其他全拒绝。Claude 没法"再多干点"，因为命令根本跑不出来。

---

## 已知陷阱与教训

### Token 泄漏

聊天里贴 token 是绝对禁忌。整个项目搭建过程中，Kemou 多次把墨墨 token 和
GitHub token 直接贴在聊天里，每次都需要事后去重置。

正确做法：
- 墨墨 token 放启动脚本的 export 语句里（脚本本身不进 git）
- GitHub token 同样
- Routine 里不在 prompt 写明文 token

如果新 AI 在帮 Kemou 调试时看到 token 直接贴出来，**立即提醒重置**，
而不是把它带进自己的代码示例里继续放大暴露面。

### Claude 的"过度热情"

历次跑 Routine 都见过几种"画蛇添足"行为：
- 任务完成后还想推 feature 分支
- 想创建 PR "以防万一"
- 为了测试擅自从 processed.json 删条目
- 把整个填好 ALL_NOTES 的脚本提交到 git

现已通过 settings.json 的 deny 列表 + CLAUDE.md 的明确禁令完全堵死。
新 AI 改代码时不要回退这些约束。

### 引号冲突

note_text 必须用三引号。已写进 CLAUDE.md 和 MNEMONIC_RULES.md。新 AI 改流程时
不要把这条要求改掉。

### feature 分支堆积

Claude Code Routines 会创建 `claude/xxx-yyy-zzz` 这种 feature 分支。
脚本用 `HEAD:main` 后这些分支虽然不需要了，但还是会留在仓库里。
不影响功能但有点乱。定期可以批量删一下。

---

## 未来扩展规划

### 例句生成（已实现）

每日 Routine 现在同时生成助记和例句。墨墨 API 的 `/phrases` 端点用于创建例句，每条
例句需要 `voc_id`、英文句子（`phrase`）、中文翻译（`interpretation`）、`tags`（传空）、
`origin`（传 "AI 生成"）。墨墨 App 会自己识别英文句子中的目标词位置并在 UI 上高亮，
中文翻译里对应短语的虚线标注也是 App 渲染的，API 不需要也不接受高亮位置参数。

#### 数据结构

`run_mnemonics.py` 里有两个并列的填写区：

- `ALL_NOTES`：`(voc_id, spelling, note_type, note_text)`，每词 1~N 条
- `ALL_PHRASES`：`(voc_id, spelling, phrase_en, phrase_zh)`，每词 1~3 条（多义词覆盖不同义项）

`processed.json` 升级为 `{voc_id: {spelling, note_date, phrase_date}}`，分别记录助记
和例句的提交日期。旧格式（`{spelling, date}`）启动时自动归一化成
`note_date = date, phrase_date = null`，无需手动迁移。

#### 待处理判定

`--fetch` 列出的"待处理"是任意一项还缺的词：`note_date` 缺 → 列入 ALL_NOTES 模板，
`phrase_date` 缺 → 列入 ALL_PHRASES 模板。两个都缺则两块都出现。

副作用：所有 1500+ 老词当前都只有 note_date 没有 phrase_date，将来出现在今日/明日
复习队列里时会自动被标记成"待补例句"。这是预期行为，例句通过日常复习自然回填，
不需要单独的 backfill 模式（也是当时设计取舍的结果——避免一次性补几百条例句把
Routine 撑爆，也避免 API 在短时间内被打满）。

#### 风格规则

写在 PHRASE_RULES.md。文件目前是骨架，具体写作风格留待 Kemou 和 AI 单独讨论后补全。
在规则定稿前 AI 跑 Routine 遇到待补例句应该暂停确认，不要拍脑袋写。

#### 未来可能的扩展

- 老词例句的批量回填（`--backfill-phrases N`），目前没做，靠日常复习自然回填
- 给例句加 `tags` 或 `origin` 来区分批次（比如 `origin="AI 生成 2026 高考"`）

### 老词批量回填（用户已请求，本次实现）

已实现 `--backfill N` 模式。用法见下方"老词回填操作指南"。

### 助记质量评估

目前生成的助记只在 push 后由人眼抽查。可以做的改进：
- 每条助记附一个"自评分数"（Claude 评估自己生成的助记 1-5 分）
- 低分助记标记在 processed.json，定期 review 改进
- 用户挑出"特别好"和"特别差"的样本，喂回 MNEMONIC_RULES.md 作为正反例

### 公开助记交换

墨墨允许用户公开助记换免费单词上限。如果哪天 Kemou 想这么做，
设计：
- 增加一个"public"标记，标注哪些 note 可以公开
- 公开前人工 review（避免 AI 内容被官方判定为低质量）

---

## 老词回填操作指南

如果想给以前学过但没助记的老词补上，按这个流程：

### 方式一：临时启用一次

在 Claude Code（或者云端 Claude）里说一句：

> "用 backfill 模式处理 50 个老词。先跑 `python3 run_mnemonics.py --backfill 50` 看待处理词，
> 按 MNEMONIC_RULES.md 生成助记填入 ALL_NOTES，然后跑 `python3 run_mnemonics.py` 提交。"

可以分批做，比如每天 50-100 个，慢慢回填。

### 方式二：新建一个 Routine 自动回填

创建第二个 Routine：
- 触发：每天一次（比如下午 3 点，错开晚上的主 Routine）
- Prompt：

```
你正在为 Kemou 的墨墨账户批量回填老词助记。
按 CLAUDE.md 的流程，但这次跑 --backfill 100 而不是 --fetch。
其他都一样：读规则 → fetch → 填 ALL_NOTES → submit。
助记风格严格遵循 MNEMONIC_RULES.md。
```

回填完成（脚本提示"没有更多老词需要回填"）之后关掉这个 Routine 即可。
1500 词以 100/天 的速度，约半个月跑完。

### 注意事项

- 一次别超过 100 个，避免 Routine 单次运行超时
- 每次 Routine 运行限速约 50 词/分钟（脚本 sleep 1.5 秒），100 词需要约 2.5 分钟提交
  加上 Claude 生成助记的时间，整体约 30 分钟，仍在 Routine 时限内
- 注意 5 小时 2000 次的 API 速率限制，不要短时间内反复跑回填

---

## 开发与维护建议

### 改 CLAUDE.md 时

只改给 Routine 看的执行流程相关内容。不要把 CLAUDE.md 变成大文档——
Routine 每次都要读，太长会拖慢启动。

设计与背景信息放本文档（CONTEXT.md），人类和新 AI 需要时主动读。

### 改 run_mnemonics.py 时

保持单文件、零依赖（只用标准库）。Routine 环境是临时的，多一个依赖就多一份维护成本。

任何新功能都先考虑能不能通过加 `--xxx` 子命令实现，而不是改主流程。

### 改 settings.json 时

allow 列表越短越好。每加一项前问自己：这真的必要吗？能不能用更精确的模式串？

deny 列表是兜底，不是主防线。主防线是 allow 极简 + defaultMode=deny。

### Token 处理

环境变量是唯一渠道。任何文档示例里都用 `$MAIMEMO_TOKEN`、`$GH_TOKEN` 表示，
绝不写明文。这是给所有未来 AI 的硬约束。

