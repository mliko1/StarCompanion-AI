# -*- coding: utf-8 -*-
"""完整演示流程自检（P0-7）：连续跑 10 轮「推荐计划 → 开始 → 状态 → 结束 → 报告」，
逐轮记录结果和异常到 logs/demo_run_log.csv。

说明：这是自动化回归工具，覆盖后端 API 链路与状态机；
识别准确率仍需真人在摄像头前演示验证（见 docs/phase3_test_report.md）。

运行（后端已启动）：
    python tests/demo_flow_check.py
    python tests/demo_flow_check.py --runs 10
"""

import argparse
import csv
import datetime
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "logs", "demo_run_log.csv")
BASE = "http://127.0.0.1:8000"
TOKEN = None


def _ensure_token():
    """本地自动化工具使用桌面端令牌通过鉴权。"""
    global TOKEN
    if not TOKEN:
        r = urllib.request.Request(
            BASE + "/api/auth/desktop-token", data=b"{}",
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(r, timeout=5) as resp:
            TOKEN = json.loads(resp.read().decode("utf-8"))["token"]
    return TOKEN


def req(path, method="GET", payload=None, timeout=15):
    data = None
    headers = {"Cookie": "xb_token=" + _ensure_token()}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=data,
                               headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=10)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    rows = []
    for i in range(1, args.runs + 1):
        row = {"run": i, "time": datetime.datetime.now().isoformat(timespec="seconds"),
               "step": "", "result": "", "exception": ""}
        try:
            plan = req("/api/plan")
            tasks = (plan.get("plan") or [])[:1]
            row["step"] = "读取今日推荐"
            if not tasks:
                row["result"] = "无推荐任务"
                rows.append(row)
                continue
            tid = tasks[0]["task_id"]
            reps = tasks[0].get("reps", 1)

            row["step"] = "启动训练"
            started = req("/api/training/start_plan", "POST",
                          {"task_ids": [tid], "reps": [1], "prompt_level": 0},
                          timeout=30)
            if not started.get("ok"):
                row["result"] = "启动失败：" + started.get("msg", "")
                rows.append(row)
                continue

            time.sleep(2)
            row["step"] = "读取训练状态"
            st = req("/api/training/status")
            row["result"] = f"state={st.get('state')} plan_total={st.get('plan_total')}"

            row["step"] = "结束训练"
            req("/api/training/stop", "POST", {}, timeout=20)
            time.sleep(1)

            row["step"] = "生成/读取报告"
            st2 = req("/api/training/status")
            sid = st2.get("session_id")
            if sid:
                rep = req(f"/api/reports/professional/{sid}")
                row["result"] += f" report_sections={len(rep)} reps_expected={reps}"
            else:
                row["exception"] = "无 session_id，未生成报告"
        except Exception as e:
            row["exception"] = f"{type(e).__name__}: {e}"
        rows.append(row)
        print(f"[{i}/{args.runs}] {row['step']} | {row['result']} | {row['exception']}")

    with open(LOG, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["run", "time", "step", "result", "exception"])
        w.writeheader()
        w.writerows(rows)

    ok = sum(1 for r in rows if not r["exception"] and r["result"])
    print(f"\n完成 {len(rows)} 轮，无异常 {ok} 轮，日志：{LOG}")
    return 0 if ok == args.runs else 1


if __name__ == "__main__":
    sys.exit(main())
