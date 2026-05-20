#!/usr/bin/env python3
"""
墨墨助记自动提交脚本

用法：
  python3 run_mnemonics.py          # 正式提交（ALL_NOTES 已填好时）
  python3 run_mnemonics.py --fetch  # 仅拉取今日待处理单词并打印，不提交

Claude 每次运行流程：
  1. python3 run_mnemonics.py --fetch  → 查看待处理词
  2. 按 MNEMONIC_RULES.md 生成助记，填入下方 ALL_NOTES
  3. python3 run_mnemonics.py         → 提交并 push
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import subprocess
from datetime import datetime, timezone, timedelta

# ── 配置 ──────────────────────────────────────────────────────────────────────

BASE_URL       = "https://open.maimemo.com/open/api/v1"
PROCESSED_PATH = os.path.join(os.path.dirname(__file__), "processed.json")
REPO_DIR       = os.path.dirname(__file__)
SLEEP_BETWEEN  = 1.6   # 秒，API 限速 60s/40次，1.6s 间隔留有余量
RETRY_WAIT     = 60    # 429 时等待秒数
MAX_RETRIES    = 3

TZ_SHANGHAI = timezone(timedelta(hours=8))

# ── ▼▼▼ Claude 每次填写这里 ▼▼▼ ──────────────────────────────────────────────
#
# 格式：每条 note 是一个 tuple：
#   (voc_id, spelling, note_type, note_text)
#
# note_type 可选值：
#   词根词缀 / 词源 / 合成 / 派生 / 辨析 / 固定搭配 / 近反义词 / 串记 / 扩展 / 语法 / 其他
#
# note_text 用 \n 换行，不超过 80 字，纯文本不加 markdown
#
# 一个词可以有多条 note（不同 note_type），每条单独列一行即可
#
# 运行 `python3 run_mnemonics.py --fetch` 可获取待处理词的 voc_id 和 spelling

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


def load_processed():
    try:
        with open(PROCESSED_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {item["voc_id"]: item["spelling"] for item in data}
        return data
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


def fetch_pending(token, done_set):
    """拉取今日单词，过滤已处理，返回待处理列表。"""
    ok, result = api_post("/study/get_today_items", {"limit": 1000}, token)
    if not ok:
        print(f"获取今日单词失败：{result}", file=sys.stderr)
        sys.exit(1)
    items = result["data"]["today_items"]
    pending = [i for i in items if i["voc_id"] not in done_set]
    return items, pending


def cmd_fetch():
    """--fetch 模式：打印今日待处理词，供 Claude 生成助记用。"""
    token = get_token()
    done_map = load_processed()
    done_set = set(done_map.keys())
    all_items, pending = fetch_pending(token, done_set)

    already_done = len(all_items) - len(pending)
    print(f"今日单词：{len(all_items)} 词  |  已处理：{already_done} 词  |  待处理：{len(pending)} 词\n")
    if not pending:
        print("本次无新增，所有今日单词均已处理。")
        return
    print("待处理词（复制 voc_id 填入 ALL_NOTES）：\n")
    for item in pending:
        print(f'    # {item["voc_spelling"]}')
        print(f'    ("{item["voc_id"]}", "{item["voc_spelling"]}", "note_type", "note_text"),')
        print()


def cmd_submit():
    """正式提交模式：提交 ALL_NOTES 中的助记并 push。"""
    if not ALL_NOTES:
        print("ALL_NOTES 为空，请先填写助记再运行。")
        sys.exit(0)

    token   = get_token()
    gh_token = os.environ.get("GH_TOKEN", "")
    done_map = load_processed()
    done_set = set(done_map.keys())

    # 过滤已处理
    skipped = {spelling for voc_id, spelling, _, _ in ALL_NOTES if voc_id in done_set}
    to_submit = [(v, s, t, n) for v, s, t, n in ALL_NOTES if v not in done_set]
    new_words  = {v: s for v, s, _, _ in to_submit}

    print(f"待提交：{len(to_submit)} 条 note（{len(new_words)} 词）  |  跳过已处理：{len(skipped)} 词\n")

    success, fail_list, submitted = 0, [], set()

    for i, (voc_id, spelling, note_type, note_text) in enumerate(to_submit, 1):
        print(f"[{i}/{len(to_submit)}] {spelling} | {note_type}")
        ok, result = api_post("/notes", {"note": {"voc_id": voc_id, "note_type": note_type, "note": note_text}}, token)
        if ok:
            print("  ✓")
            success += 1
            submitted.add(voc_id)
            done_map[voc_id] = spelling
        else:
            print(f"  ✗ {result}")
            fail_list.append((spelling, note_type, str(result)))
        if i < len(to_submit):
            time.sleep(SLEEP_BETWEEN)

    # 写回 processed.json
    save_processed(done_map)
    print(f"\nprocessed.json 已更新，共 {len(done_map)} 词")

    # Git push
    date_str = datetime.now(TZ_SHANGHAI).strftime("%Y-%m-%d")
    push_ok = _git_push(gh_token, len(new_words), date_str)

    # 汇报
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
        ["git", "-C", REPO_DIR, "push", "origin", "main"],
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
    if "--fetch" in sys.argv:
        cmd_fetch()
    else:
        cmd_submit()
