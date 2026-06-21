#!/usr/bin/env python3
"""
墨墨助记自动提交脚本

四种用法：
  python3 run_mnemonics.py --fetch              # 拉取今日+明日待处理词（日常模式）
  python3 run_mnemonics.py --backfill 100       # 拉取 N 个老词（批量回填用）
  python3 run_mnemonics.py --wordbook FILE      # 词书模式：从词表文件批量预生成助记
  python3 run_mnemonics.py                       # 正式提交（ALL_NOTES 已填好时）

设计：晚上 9 点跑一次，拉取明天的词单 + 今天还没处理的剩余词，
查重后批量生成助记，第二天早晨打开 App 就已经全部就绪。

批量回填：如果想给以前学过但没助记的老词补上助记，用 --backfill N。
建议每次 50-100 个，避免单次 Routine 跑太久。

词书模式（--wordbook）：给一整本词书（尤其云词库，如《有道四级核心 500 词》）
里的词提前批量生成助记。墨墨开放 API 拉不到官方云词库，所以词表用文本文件给：
一行一个单词。脚本把每个拼写解析成 voc_id（结果缓存到 .wordbook_cache.json），
默认只处理"还没选入学习计划"的词（已选词交给日常 routine），按未选优先排序输出。
词量大时配合 --limit N 分批，详见 WORDBOOK.md。注意：词书模式只在用户明确要求时
手动运行，日常 Routine 永远跑 --fetch，不要默认进词书模式。
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import subprocess
from datetime import datetime, timezone, timedelta

# ── 配置 ──────────────────────────────────────────────────────────────────────

BASE_URL       = "https://open.maimemo.com/open/api/v1"
SCRIPT_PATH    = os.path.abspath(__file__)
PROCESSED_PATH = os.path.join(os.path.dirname(SCRIPT_PATH), "processed.json")
VOC_CACHE_PATH = os.path.join(os.path.dirname(SCRIPT_PATH), ".wordbook_cache.json")
REPO_DIR       = os.path.dirname(SCRIPT_PATH)
SLEEP_BETWEEN  = 1.6
RETRY_WAIT     = 60
MAX_RETRIES    = 3

TZ_SHANGHAI = timezone(timedelta(hours=8))
MAIMEMO_DAY_START_HOUR = 4

# ── ▼▼▼ Claude 每次填写这里 ▼▼▼ ──────────────────────────────────────────────
#
# 助记格式：(voc_id, spelling, note_type, note_text)
#
# 【重要】note_text 必须使用 Python 三引号字符串 """..."""
# 这样内容里有任何符号（双引号、单引号、反斜杠）都不会和 Python 语法冲突。
# 换行直接在源码里换行（不要写 \n）。示例：
#
#     ("voc-xxx", "nowadays", "合成", """now + a + days（如今这些日子）
# 强调"和过去对比的此刻"，常和时间状语连用"""),
#
# note_type 可选：词根词缀 / 词源 / 合成 / 派生 / 辨析 / 固定搭配 /
#                近反义词 / 串记 / 扩展 / 语法 / 其他
#
# ALL_PHRASES 例句功能目前暂停（墨墨 API 不支持词义高亮，App 体验不佳），
# 保留代码以便未来恢复。Routine 跑的时候不要填这个。

ALL_NOTES = [
    # (voc_id, spelling, note_type, note_text),
]

ALL_PHRASES = [
    # (voc_id, spelling, phrase_en, phrase_zh),
]

# ── ▲▲▲ 填写区结束 ▲▲▲ ────────────────────────────────────────────────────────


def get_token():
    token = os.environ.get("MAIMEMO_TOKEN", "")
    if not token:
        print("错误：环境变量 MAIMEMO_TOKEN 未设置", file=sys.stderr)
        sys.exit(1)
    return token


def maimemo_today():
    now = datetime.now(TZ_SHANGHAI)
    if now.hour < MAIMEMO_DAY_START_HOUR:
        now = now - timedelta(days=1)
    return now.date()


def date_range_iso(target_date):
    start = datetime.combine(target_date, datetime.min.time()).replace(
        hour=MAIMEMO_DAY_START_HOUR, tzinfo=TZ_SHANGHAI)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    return start.isoformat(), end.isoformat()


def _normalize_entry(spelling, raw):
    """把任意历史结构归一为 {spelling, note_date, phrase_date}。

    历史结构：
      - 纯字符串：spelling                → note_date=unknown, phrase_date=None
      - {spelling, date}                  → note_date=date,    phrase_date=None
      - {spelling, note_date, phrase_date} → 直接用
    """
    if isinstance(raw, str):
        return {"spelling": raw, "note_date": "unknown", "phrase_date": None}
    spelling = raw.get("spelling", spelling)
    if "note_date" in raw or "phrase_date" in raw:
        return {
            "spelling": spelling,
            "note_date": raw.get("note_date"),
            "phrase_date": raw.get("phrase_date"),
        }
    return {
        "spelling": spelling,
        "note_date": raw.get("date", "unknown"),
        "phrase_date": None,
    }


def load_processed():
    try:
        with open(PROCESSED_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {item["voc_id"]: _normalize_entry(item.get("spelling", ""), item)
                    for item in data}
        return {voc_id: _normalize_entry(voc_id, val) for voc_id, val in data.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def needs_note(entry):
    return entry is None or not entry.get("note_date")


def needs_phrase(entry):
    return entry is None or not entry.get("phrase_date")


def save_processed(done_map):
    with open(PROCESSED_PATH, "w", encoding="utf-8") as f:
        json.dump(done_map, f, ensure_ascii=False, indent=2)


def api_post(path, body, token):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return True, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            last = attempt + 1 >= MAX_RETRIES
            if e.code == 429:
                print(f"    ⏳ 限速 429，等待 {RETRY_WAIT}s（第 {attempt+1}/{MAX_RETRIES} 次）...")
                time.sleep(RETRY_WAIT)
            elif e.code in (500, 502, 503, 504) and not last:
                wait = 5 * (2 ** attempt)  # 5s, 10s, 20s...
                print(f"    ⏳ 服务端 {e.code}，等待 {wait}s 重试（第 {attempt+1}/{MAX_RETRIES} 次）...")
                time.sleep(wait)
            else:
                return False, f"HTTP {e.code}: {err[:200]}"
        except urllib.error.URLError as e:
            if attempt + 1 >= MAX_RETRIES:
                return False, str(e)
            wait = 5 * (2 ** attempt)
            print(f"    ⏳ 网络错误（{e.reason}），等待 {wait}s 重试（第 {attempt+1}/{MAX_RETRIES} 次）...")
            time.sleep(wait)
        except Exception as ex:
            return False, str(ex)
    return False, f"已达最大重试次数（{MAX_RETRIES}）"


def fetch_today(token):
    ok, result = api_post("/study/get_today_items", {"limit": 1000}, token)
    if not ok:
        return [], f"获取今日词失败：{result}"
    items = result["data"]["today_items"]
    return [{"voc_id": i["voc_id"], "voc_spelling": i["voc_spelling"]} for i in items], None


def fetch_by_date(target_date, token):
    start, end = date_range_iso(target_date)
    ok, result = api_post("/study/query_study_records",
                          {"next_study_date": {"start": start, "end": end}, "limit": 1000},
                          token)
    if not ok:
        return [], f"获取 {target_date} 词单失败：{result}"
    records = result["data"]["records"]
    return [{"voc_id": r["voc_id"], "voc_spelling": r["voc_spelling"]} for r in records], None


def fetch_all_records(token):
    """拉取学习计划中所有词（用于 backfill / wordbook）。

    单次 limit=1000，理论上用 offset 翻页。但实测墨墨这个端点**不认 offset**：
    无论 offset 传多少，都返回同一批前 1000 条。所以这里以"本页是否带来新 voc_id"
    作为翻页是否生效的判据——一旦某页没有任何新词（说明 offset 没被服务端尊重，
    或已到末尾），立即停止，避免死循环 + 内存暴涨。
    """
    all_map = {}
    offset = 0
    while True:
        ok, result = api_post("/study/query_study_records",
                              {"limit": 1000, "offset": offset}, token)
        if not ok:
            return [], f"拉取学习计划失败：{result}"
        records = result["data"]["records"]
        if not records:
            break
        before = len(all_map)
        for r in records:
            all_map[r["voc_id"]] = r["voc_spelling"]
        if len(all_map) == before:   # 本页没带来新词 → offset 没生效或已到底
            break
        if len(records) < 1000:
            break
        offset += len(records)
    return [{"voc_id": v, "voc_spelling": s} for v, s in all_map.items()], None


def api_get(path, token):
    """GET 请求，复用 POST 那套 429 / 5xx / 网络重试逻辑。"""
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return True, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            last = attempt + 1 >= MAX_RETRIES
            if e.code == 429:
                print(f"    ⏳ 限速 429，等待 {RETRY_WAIT}s（第 {attempt+1}/{MAX_RETRIES} 次）...")
                time.sleep(RETRY_WAIT)
            elif e.code in (500, 502, 503, 504) and not last:
                wait = 5 * (2 ** attempt)
                print(f"    ⏳ 服务端 {e.code}，等待 {wait}s 重试（第 {attempt+1}/{MAX_RETRIES} 次）...")
                time.sleep(wait)
            else:
                return False, f"HTTP {e.code}: {err[:200]}"
        except urllib.error.URLError as e:
            if attempt + 1 >= MAX_RETRIES:
                return False, str(e)
            wait = 5 * (2 ** attempt)
            print(f"    ⏳ 网络错误（{e.reason}），等待 {wait}s 重试（第 {attempt+1}/{MAX_RETRIES} 次）...")
            time.sleep(wait)
        except Exception as ex:
            return False, str(ex)
    return False, f"已达最大重试次数（{MAX_RETRIES}）"


def load_voc_cache():
    try:
        with open(VOC_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_voc_cache(cache):
    try:
        with open(VOC_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠ 写入 voc 缓存失败：{e}")


def resolve_voc_id(spelling, token, cache):
    """拼写 → voc_id。命中缓存直接返回（None 表示曾查过但查不到）。"""
    key = spelling.lower()
    if key in cache:
        return cache[key]
    ok, result = api_get(f"/vocabulary?spelling={urllib.parse.quote(spelling)}", token)
    voc_id = None
    if ok:
        voc = result.get("data", {}).get("voc")
        if voc:
            voc_id = voc.get("id")
    cache[key] = voc_id
    return voc_id


def read_wordbook_file(path):
    """读词表文件：一行一个单词，忽略空行和 // 或 # 开头的注释行，去重保序。"""
    words, seen = [], set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            w = line.strip()
            if not w or w.startswith("//") or w.startswith("#"):
                continue
            key = w.lower()
            if key not in seen:
                seen.add(key)
                words.append(w)
    return words


def parse_str_argument(flag, default):
    """从 sys.argv 中提取 --flag VALUE 的字符串值"""
    for i, arg in enumerate(sys.argv):
        if arg == flag and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def parse_n_argument(flag, default):
    """从 sys.argv 中提取 --flag N 的 N 值"""
    for i, arg in enumerate(sys.argv):
        if arg == flag and i + 1 < len(sys.argv):
            try:
                return int(sys.argv[i + 1])
            except ValueError:
                pass
    return default


def cmd_fetch():
    token = get_token()
    done_map = load_processed()

    today    = maimemo_today()
    tomorrow = today + timedelta(days=1)

    today_items, err_t = fetch_today(token)
    if err_t:
        print(err_t, file=sys.stderr)
        today_items = []

    tomorrow_items, err_m = fetch_by_date(tomorrow, token)
    if err_m:
        print(err_m, file=sys.stderr)
        tomorrow_items = []

    seen_ids = set()
    combined = []
    for item in today_items + tomorrow_items:
        if item["voc_id"] not in seen_ids:
            seen_ids.add(item["voc_id"])
            combined.append(item)

    # 跟原来助记的逻辑完全一致：voc_id 在 processed.json 就跳过
    pending = [i for i in combined if i["voc_id"] not in done_map]
    already_done = len(combined) - len(pending)

    # 跳过拼写为空的词：墨墨偶尔会返回 voc_spelling 为空的条目，
    # 没有词无法生成助记，硬填会得到"（拼写为空，助记暂缺）"之类的垃圾助记。
    blank = [i for i in pending if not (i["voc_spelling"] or "").strip()]
    pending = [i for i in pending if (i["voc_spelling"] or "").strip()]

    print(f"今日剩余：{len(today_items)} 词")
    print(f"明日安排：{len(tomorrow_items)} 词")
    print(f"合并去重：{len(combined)} 词  |  已处理：{already_done}  |  待处理：{len(pending)}")
    if blank:
        print(f"⚠ 跳过拼写为空的词 {len(blank)} 个（不生成助记）：{[i['voc_id'] for i in blank]}")
    print()

    if not pending:
        print("本次无新增，所有词均已处理。")
        return

    print('全部 note_text 必须用三引号 """..."""\n')

    print("─── ALL_NOTES（每词 1~N 条助记）───\n")
    for item in pending:
        print(f'    # {item["voc_spelling"]}')
        print(f'    ("{item["voc_id"]}", "{item["voc_spelling"]}", "note_type", """note_text"""),')
        print()


def cmd_backfill():
    n = parse_n_argument("--backfill", 100)
    token = get_token()
    done_map = load_processed()

    print(f"批量回填模式（仅助记）：本次拉取最多 {n} 个老词\n")

    all_words, err = fetch_all_records(token)
    if err:
        print(err, file=sys.stderr)
        sys.exit(1)

    # 去重（query_study_records 可能有重复条目）
    seen = set()
    unique = []
    for w in all_words:
        if w["voc_id"] not in seen:
            seen.add(w["voc_id"])
            unique.append(w)

    # 同样跳过拼写为空的词
    blank = [w for w in unique if not (w["voc_spelling"] or "").strip()]
    unique = [w for w in unique if (w["voc_spelling"] or "").strip()]

    pending_all = [w for w in unique if needs_note(done_map.get(w["voc_id"]))]
    pending = pending_all[:n]
    if blank:
        print(f"⚠ 跳过拼写为空的词 {len(blank)} 个（不回填助记）：{[w['voc_id'] for w in blank]}\n")

    note_done = sum(1 for v in done_map.values() if v.get("note_date"))
    print(f"学习计划共 {len(unique)} 词")
    print(f"已有助记 {note_done} 词")
    print(f"剩余待回填 {len(pending_all)} 词，本次取 {len(pending)} 词\n")

    if not pending:
        print("没有更多老词需要回填，全部已处理完毕。")
        return

    print('待处理词（复制填入 ALL_NOTES，note_text 必须用三引号 """..."""）：\n')
    for item in pending:
        print(f'    # {item["voc_spelling"]}')
        print(f'    ("{item["voc_id"]}", "{item["voc_spelling"]}", "note_type", """note_text"""),')
        print()


def cmd_wordbook():
    """词书模式：从词表文件批量预生成助记的待处理清单。

    用法：python3 run_mnemonics.py --wordbook FILE [--limit N] [--include-selected]
      FILE                词表文件，一行一个单词
      --limit N           本批最多输出 N 个待处理词（不传=全部）
      --include-selected  连"已选入学习计划"的词也一并输出（默认只输出未选词）
    """
    path = parse_str_argument("--wordbook", None)
    if not path:
        print("用法：python3 run_mnemonics.py --wordbook <词表文件> [--limit N] [--include-selected]")
        sys.exit(1)
    if not os.path.isfile(path):
        print(f"错误：词表文件不存在：{path}", file=sys.stderr)
        sys.exit(1)

    n = parse_n_argument("--limit", 0)  # 0 = 全部
    include_selected = "--include-selected" in sys.argv

    token = get_token()
    done_map = load_processed()
    words = read_wordbook_file(path)
    print(f"词书模式：从 {path} 读到 {len(words)} 个去重单词\n")
    if not words:
        print("词表为空，没什么可做的。")
        return

    # 已选入学习计划的 voc_id（用于"未选优先"排序）
    studied, err = fetch_all_records(token)
    if err:
        print(f"⚠ 获取学习计划失败（无法区分已选/未选，全部按未选处理）：{err}")
        studied_ids = set()
    else:
        studied_ids = {w["voc_id"] for w in studied}

    # 拼写 → voc_id（带缓存，避免分批时重复查询）
    cache = load_voc_cache()
    resolved, unresolved = [], []
    new_lookups = 0
    print("解析 voc_id 中（首次较慢，结果缓存到 .wordbook_cache.json）...")
    for i, w in enumerate(words, 1):
        is_cached = w.lower() in cache
        voc_id = resolve_voc_id(w, token, cache)
        if voc_id:
            resolved.append((w, voc_id))
        else:
            unresolved.append(w)
        if not is_cached:
            new_lookups += 1
            if new_lookups % 20 == 0:
                save_voc_cache(cache)
            time.sleep(0.4)
    save_voc_cache(cache)
    print(f"  解析完成：命中 {len(resolved)} / 查无 {len(unresolved)}（本次新查询 {new_lookups} 次）\n")

    # 过滤已有助记
    pending = [(w, v) for w, v in resolved if needs_note(done_map.get(v))]
    already_noted = len(resolved) - len(pending)

    # 未选优先
    unselected = [(w, v) for w, v in pending if v not in studied_ids]
    selected   = [(w, v) for w, v in pending if v in studied_ids]
    ordered = unselected + selected if include_selected else unselected

    print(f"已有助记：{already_noted} 词")
    print(f"待处理：{len(pending)} 词（未选 {len(unselected)} / 已选 {len(selected)}）")
    if not include_selected and selected:
        print(f"  默认只输出未选词；已选 {len(selected)} 词交给日常 routine，"
              f"如需一并生成请加 --include-selected")
    if unresolved:
        print(f"⚠ {len(unresolved)} 个词 API 查无 voc_id（核对拼写后可手工处理）：{unresolved[:30]}")
    print()

    batch = ordered[:n] if n > 0 else ordered
    if not batch:
        print("本批无待处理词。")
        return

    print(f"本批输出 {len(batch)} 词" + (f"（--limit {n}）" if n > 0 else "（全部待处理）"))
    print('全部 note_text 必须用三引号 """..."""\n')
    print("─── ALL_NOTES（每词 1~N 条助记）───\n")
    for w, v in batch:
        print(f'    # {w}')
        print(f'    ("{v}", "{w}", "note_type", """note_text"""),')
        print()


def clear_filled_areas_in_script():
    try:
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        new_content, n1 = re.subn(
            r"ALL_NOTES = \[.*?\n\]",
            "ALL_NOTES = [\n    # (voc_id, spelling, note_type, note_text),\n]",
            content,
            count=1,
            flags=re.DOTALL
        )
        new_content, n2 = re.subn(
            r"ALL_PHRASES = \[.*?\n\]",
            "ALL_PHRASES = [\n    # (voc_id, spelling, phrase_en, phrase_zh),\n]",
            new_content,
            count=1,
            flags=re.DOTALL
        )
        if n1 == 1 and n2 == 1:
            with open(SCRIPT_PATH, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("  ✓ ALL_NOTES / ALL_PHRASES 已清空（脚本已还原）")
            return True
        print(f"  ⚠ 清空失败，匹配数：ALL_NOTES={n1}, ALL_PHRASES={n2}")
        return False
    except Exception as e:
        print(f"  ⚠ 清空填写区失败：{e}")
        return False


def cmd_submit():
    if not ALL_NOTES and not ALL_PHRASES:
        print("ALL_NOTES 和 ALL_PHRASES 都为空，请先填写再运行。")
        sys.exit(0)

    token    = get_token()
    gh_token = os.environ.get("GH_TOKEN", "")
    done_map = load_processed()
    date     = maimemo_today().strftime("%Y-%m-%d")

    # ── 分流：分别筛出需要提交的助记 / 例句 ────────────────────────────────
    # 兜底：拼写为空的词一律不提交，避免把"（拼写为空，助记暂缺）"这类
    # 占位助记写进墨墨。正常情况下 --fetch / --backfill 已经过滤掉它们了，
    # 这里是第二道防线。
    notes_blank = [(v, s) for v, s, _, _ in ALL_NOTES if not (s or "").strip()]
    notes_to_submit = [
        (v, s, t, n) for v, s, t, n in ALL_NOTES
        if (s or "").strip() and needs_note(done_map.get(v))
    ]
    notes_skipped = [
        (v, s) for v, s, _, _ in ALL_NOTES
        if (s or "").strip() and not needs_note(done_map.get(v))
    ]
    if notes_blank:
        print(f"⚠ 跳过拼写为空的助记 {len(notes_blank)} 条（不提交）：{[v for v, _ in notes_blank]}")

    phrases_to_submit = [
        (v, s, en, zh) for v, s, en, zh in ALL_PHRASES
        if needs_phrase(done_map.get(v))
    ]
    phrases_skipped = [(v, s) for v, s, _, _ in ALL_PHRASES if not needs_phrase(done_map.get(v))]

    note_words   = {v: s for v, s, _, _ in notes_to_submit}
    phrase_words = {v: s for v, s, _, _ in phrases_to_submit}

    print(f"待提交助记：{len(notes_to_submit)} 条（{len(note_words)} 词）  |  跳过：{len(notes_skipped)} 词")
    print(f"待提交例句：{len(phrases_to_submit)} 条（{len(phrase_words)} 词）  |  跳过：{len(phrases_skipped)} 词\n")

    note_success, note_fail = 0, []
    phrase_success, phrase_fail = 0, []
    submitted_notes, submitted_phrases = set(), set()

    # ── 第一批：提交助记 ────────────────────────────────────────────────
    for i, (voc_id, spelling, note_type, note_text) in enumerate(notes_to_submit, 1):
        print(f"[助记 {i}/{len(notes_to_submit)}] {spelling} | {note_type}")
        ok, result = api_post("/notes", {
            "note": {"voc_id": voc_id, "note_type": note_type, "note": note_text}
        }, token)
        if ok:
            print("  ✓")
            note_success += 1
            submitted_notes.add(voc_id)
            entry = done_map.get(voc_id) or {"spelling": spelling, "note_date": None, "phrase_date": None}
            entry["spelling"] = spelling
            entry["note_date"] = date
            done_map[voc_id] = entry
        else:
            print(f"  ✗ {result}")
            note_fail.append((spelling, note_type, str(result)))
        if i < len(notes_to_submit):
            time.sleep(SLEEP_BETWEEN)

    # ── 第二批：提交例句 ────────────────────────────────────────────────
    if notes_to_submit and phrases_to_submit:
        time.sleep(SLEEP_BETWEEN)

    # 同一 voc_id 可能在 ALL_PHRASES 出现多次；只要至少一条成功就标记 phrase_date
    phrase_ok_voc = set()
    for i, (voc_id, spelling, phrase_en, phrase_zh) in enumerate(phrases_to_submit, 1):
        preview = phrase_en.replace("\n", " ")[:40]
        print(f"[例句 {i}/{len(phrases_to_submit)}] {spelling} | {preview}")
        ok, result = api_post("/phrases", {
            "phrase": {
                "voc_id": voc_id,
                "phrase": phrase_en,
                "interpretation": phrase_zh,
                "tags": [],
            }
        }, token)
        if ok:
            print("  ✓")
            phrase_success += 1
            submitted_phrases.add(voc_id)
            phrase_ok_voc.add(voc_id)
        else:
            print(f"  ✗ {result}")
            phrase_fail.append((spelling, preview, str(result)))
        if i < len(phrases_to_submit):
            time.sleep(SLEEP_BETWEEN)

    for voc_id in phrase_ok_voc:
        spelling = phrase_words.get(voc_id, done_map.get(voc_id, {}).get("spelling", ""))
        entry = done_map.get(voc_id) or {"spelling": spelling, "note_date": None, "phrase_date": None}
        entry["spelling"] = spelling or entry.get("spelling", "")
        entry["phrase_date"] = date
        done_map[voc_id] = entry

    save_processed(done_map)
    print(f"\nprocessed.json 已更新，共 {len(done_map)} 词")

    clear_filled_areas_in_script()

    push_ok = _git_push(gh_token, len(note_words), len(phrase_words), date)

    print("\n" + "=" * 50)
    print(f"新增助记：{len(note_words)} 词，{note_success} 条成功，{len(note_fail)} 条失败")
    print(f"新增例句：{len(phrase_words)} 词，{phrase_success} 条成功，{len(phrase_fail)} 条失败")
    if note_fail:
        print("助记失败：")
        for sp, nt, reason in note_fail:
            print(f"  - {sp} | {nt}: {reason[:80]}")
    if phrase_fail:
        print("例句失败：")
        for sp, pv, reason in phrase_fail:
            print(f"  - {sp} | {pv}: {reason[:80]}")
    print(f"Git push：{'✓ 成功' if push_ok else '✗ 失败（processed.json 内容已打印备份）'}")

    if submitted_notes:
        print("\n助记样本（前 5 条）：")
        count = 0
        for voc_id, spelling, note_type, note_text in notes_to_submit:
            if voc_id in submitted_notes:
                preview = note_text.replace("\n", " / ")[:50]
                print(f"  {spelling} | {note_type} | {preview}")
                count += 1
                if count >= 5:
                    break
    if submitted_phrases:
        print("\n例句样本（前 5 条）：")
        count = 0
        for voc_id, spelling, phrase_en, phrase_zh in phrases_to_submit:
            if voc_id in submitted_phrases:
                preview_en = phrase_en.replace("\n", " ")[:40]
                preview_zh = phrase_zh.replace("\n", " ")[:30]
                print(f"  {spelling} | {preview_en} | {preview_zh}")
                count += 1
                if count >= 5:
                    break


def _git_push(gh_token, note_count, phrase_count, date_str):
    parts = []
    if note_count:
        parts.append(f"{note_count} notes")
    if phrase_count:
        parts.append(f"{phrase_count} phrases")
    summary = " + ".join(parts) if parts else "no changes"

    # 不再覆盖 user.email / user.name：保留环境自带的签名身份
    # （commit.gpgsign + noreply@anthropic.com 的签名 key），这样 GitHub 显示
    # Verified。以前强行设成 routine@claude.ai 会让签名和邮箱对不上 → Unverified。
    cmds = []
    if gh_token:
        cmds.append(["git", "-C", REPO_DIR, "remote", "set-url", "origin",
                     f"https://x-access-token:{gh_token}@github.com/Kemou2333/momo-auto-mnemonic.git"])
    cmds += [
        ["git", "-C", REPO_DIR, "add", "processed.json"],
        ["git", "-C", REPO_DIR, "commit", "-m", f"chore: {summary} {date_str}"],
        ["git", "-C", REPO_DIR, "push", "origin", "HEAD:main"],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" not in r.stdout + r.stderr:
            print(f"Git 失败：{' '.join(cmd[-3:])}\n{r.stderr.strip()}")
            if "push" in cmd:
                print("\n=== processed.json 备份 ===")
                with open(PROCESSED_PATH, encoding="utf-8") as f:
                    print(f.read())
                return False
    return True


if __name__ == "__main__":
    if "--backfill" in sys.argv:
        cmd_backfill()
    elif "--wordbook" in sys.argv:
        cmd_wordbook()
    elif "--fetch" in sys.argv:
        cmd_fetch()
    else:
        cmd_submit()
