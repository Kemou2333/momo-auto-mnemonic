#!/usr/bin/env python3
"""
墨墨助记自动提交脚本

三种用法：
  python3 run_mnemonics.py --fetch          # 拉取今日+明日待处理词（日常）
  python3 run_mnemonics.py --backfill 100   # 拉取 N 个老词（批量回填用）
  python3 run_mnemonics.py                  # 正式提交（ALL_NOTES 已填好时）

设计：晚上 9 点跑一次，拉取明天的词单 + 今天还没处理的剩余词，
查重后批量生成助记，第二天早晨打开 App 就已经全部就绪。

批量回填：如果想给以前学过但没助记的老词补上助记，用 --backfill N。
建议每次 50-100 个，避免单次 Routine 跑太久。
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import subprocess
from datetime import datetime, timezone, timedelta

# ── 配置 ──────────────────────────────────────────────────────────────────────

BASE_URL       = "https://open.maimemo.com/open/api/v1"
SCRIPT_PATH    = os.path.abspath(__file__)
PROCESSED_PATH = os.path.join(os.path.dirname(SCRIPT_PATH), "processed.json")
REPO_DIR       = os.path.dirname(SCRIPT_PATH)
SLEEP_BETWEEN  = 1.6
RETRY_WAIT     = 60
MAX_RETRIES    = 3

TZ_SHANGHAI = timezone(timedelta(hours=8))
MAIMEMO_DAY_START_HOUR = 4

# ── ▼▼▼ Claude 每次填写这里 ▼▼▼ ──────────────────────────────────────────────
#
# 格式：(voc_id, spelling, note_type, note_text)
#
# 【重要】note_text 必须使用 Python 三引号字符串 """..."""
# 这样内容里有任何符号（包括英文双引号、单引号、反斜杠）都不会和 Python 语法冲突。
#
# 换行直接在源码里换行（不要写 \n）。示例：
#
#     ("voc-xxx", "nowadays", "合成", """now + a + days（如今这些日子）
# 强调"和过去对比的此刻"，常和时间状语连用"""),
#
# note_type 可选：词根词缀 / 词源 / 合成 / 派生 / 辨析 / 固定搭配 /
#                近反义词 / 串记 / 扩展 / 语法 / 其他

ALL_NOTES = [
    # (voc_id, spelling, note_type, note_text),
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


def load_processed():
    try:
        with open(PROCESSED_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {item["voc_id"]: {"spelling": item["spelling"], "date": "unknown"}
                    for item in data}
        result = {}
        for voc_id, val in data.items():
            if isinstance(val, str):
                result[voc_id] = {"spelling": val, "date": "unknown"}
            else:
                result[voc_id] = val
        return result
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


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
            if e.code == 429:
                print(f"    ⏳ 限速 429，等待 {RETRY_WAIT}s（第 {attempt+1}/{MAX_RETRIES} 次）...")
                time.sleep(RETRY_WAIT)
            else:
                return False, f"HTTP {e.code}: {err[:200]}"
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
    """拉取学习计划中所有词（用于 backfill）。
    单次 limit=1000，如果还有就用 offset 继续。"""
    all_records = []
    offset = 0
    while True:
        ok, result = api_post("/study/query_study_records",
                              {"limit": 1000, "offset": offset}, token)
        if not ok:
            return [], f"拉取学习计划失败：{result}"
        records = result["data"]["records"]
        if not records:
            break
        all_records.extend(records)
        if len(records) < 1000:
            break
        offset += len(records)
    return [{"voc_id": r["voc_id"], "voc_spelling": r["voc_spelling"]} for r in all_records], None


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
    done_set = set(done_map.keys())

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

    pending = [i for i in combined if i["voc_id"] not in done_set]
    already_done = len(combined) - len(pending)

    print(f"今日剩余：{len(today_items)} 词")
    print(f"明日安排：{len(tomorrow_items)} 词")
    print(f"合并去重：{len(combined)} 词  |  已处理：{already_done}  |  待处理：{len(pending)}\n")

    if not pending:
        print("本次无新增，所有词均已处理。")
        return

    print('待处理词（复制填入 ALL_NOTES，note_text 必须用三引号 """..."""）：\n')
    for item in pending:
        print(f'    # {item["voc_spelling"]}')
        print(f'    ("{item["voc_id"]}", "{item["voc_spelling"]}", "note_type", """note_text"""),')
        print()


def cmd_backfill():
    n = parse_n_argument("--backfill", 100)
    token = get_token()
    done_map = load_processed()
    done_set = set(done_map.keys())

    print(f"批量回填模式：本次拉取最多 {n} 个老词\n")

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

    pending_all = [w for w in unique if w["voc_id"] not in done_set]
    pending = pending_all[:n]

    print(f"学习计划共 {len(unique)} 词")
    print(f"已处理 {len(done_set)} 词")
    print(f"剩余待回填 {len(pending_all)} 词，本次取 {len(pending)} 词\n")

    if not pending:
        print("没有更多老词需要回填，全部已处理完毕。")
        return

    print('待处理词（复制填入 ALL_NOTES，note_text 必须用三引号 """..."""）：\n')
    for item in pending:
        print(f'    # {item["voc_spelling"]}')
        print(f'    ("{item["voc_id"]}", "{item["voc_spelling"]}", "note_type", """note_text"""),')
        print()


def clear_all_notes_in_script():
    try:
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        new_content, n = re.subn(
            r"ALL_NOTES = \[.*?\n\]",
            "ALL_NOTES = [\n    # (voc_id, spelling, note_type, note_text),\n]",
            content,
            count=1,
            flags=re.DOTALL
        )
        if n == 1:
            with open(SCRIPT_PATH, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("  ✓ ALL_NOTES 已清空（脚本已还原）")
            return True
        return False
    except Exception as e:
        print(f"  ⚠ 清空 ALL_NOTES 失败：{e}")
        return False


def cmd_submit():
    if not ALL_NOTES:
        print("ALL_NOTES 为空，请先填写助记再运行。")
        sys.exit(0)

    token    = get_token()
    gh_token = os.environ.get("GH_TOKEN", "")
    done_map = load_processed()
    done_set = set(done_map.keys())
    date     = maimemo_today().strftime("%Y-%m-%d")

    skipped   = {s for v, s, _, _ in ALL_NOTES if v in done_set}
    to_submit = [(v, s, t, n) for v, s, t, n in ALL_NOTES if v not in done_set]
    new_words = {v: s for v, s, _, _ in to_submit}

    print(f"待提交：{len(to_submit)} 条 note（{len(new_words)} 词）  |  跳过已处理：{len(skipped)} 词\n")

    success, fail_list, submitted = 0, [], set()

    for i, (voc_id, spelling, note_type, note_text) in enumerate(to_submit, 1):
        print(f"[{i}/{len(to_submit)}] {spelling} | {note_type}")
        ok, result = api_post("/notes", {
            "note": {"voc_id": voc_id, "note_type": note_type, "note": note_text}
        }, token)
        if ok:
            print("  ✓")
            success += 1
            submitted.add(voc_id)
            done_map[voc_id] = {"spelling": spelling, "date": date}
        else:
            print(f"  ✗ {result}")
            fail_list.append((spelling, note_type, str(result)))
        if i < len(to_submit):
            time.sleep(SLEEP_BETWEEN)

    save_processed(done_map)
    print(f"\nprocessed.json 已更新，共 {len(done_map)} 词")

    clear_all_notes_in_script()

    push_ok = _git_push(gh_token, len(new_words), date)

    print("\n" + "=" * 50)
    print(f"新增：{len(new_words)} 词，{success} 条 note 成功")
    print(f"跳过（已处理）：{len(skipped)} 词")
    if fail_list:
        print(f"失败：{len(fail_list)} 条")
        for sp, nt, reason in fail_list:
            print(f"  - {sp} | {nt}: {reason[:80]}")
    else:
        print("失败：0 条")
    print(f"Git push：{'✓ 成功' if push_ok else '✗ 失败（processed.json 内容已打印备份）'}")

    print("\n样本（前 8 条）：")
    count = 0
    for voc_id, spelling, note_type, note_text in to_submit:
        if voc_id in submitted:
            preview = note_text.replace("\n", " / ")[:50]
            print(f"  {spelling} | {note_type} | {preview}")
            count += 1
            if count >= 8:
                break


def _git_push(gh_token, new_count, date_str):
    cmds = [
        ["git", "-C", REPO_DIR, "config", "user.email", "routine@claude.ai"],
        ["git", "-C", REPO_DIR, "config", "user.name", "Claude Routine"],
    ]
    if gh_token:
        cmds.append(["git", "-C", REPO_DIR, "remote", "set-url", "origin",
                     f"https://x-access-token:{gh_token}@github.com/Kemou2333/maimemo-mnemonic-bot.git"])
    cmds += [
        ["git", "-C", REPO_DIR, "add", "processed.json"],
        ["git", "-C", REPO_DIR, "commit", "-m", f"chore: {new_count} new mnemonics {date_str}"],
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
    elif "--fetch" in sys.argv:
        cmd_fetch()
    else:
        cmd_submit()
