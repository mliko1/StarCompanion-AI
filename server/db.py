# -*- coding: utf-8 -*-
"""星伴AI 后端数据库层：SQLite 建表、任务库导入、历史训练数据入库。"""

import csv
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "xingban.db")
TASKS_JSON = os.path.join(ROOT, "data", "tasks.json")
PHASE2_CSV = os.path.join(ROOT, "logs", "training_session.csv")
SEQ_CSV = os.path.join(ROOT, "data", "sequence_logs", "sequence_summary.csv")
SESSIONS_CSV = os.path.join(ROOT, "data", "sequence_logs", "sessions.csv")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            name TEXT, type TEXT, params TEXT,
            difficulty INTEGER, category TEXT
        );
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT, task_name TEXT,
            start_time TEXT, end_time TEXT,
            elapsed_sec REAL, status TEXT,
            detail TEXT, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT, task_name TEXT, scene TEXT,
            prompt_level INTEGER, completed INTEGER,
            valid INTEGER, uncertainty INTEGER,
            elapsed_sec REAL, created_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()
    # 迁移：老库的 sessions 若无 task_id 列则补上（用独立连接，不影响上面）
    try:
        c = get_conn()
        c.execute("ALTER TABLE sessions ADD COLUMN task_id TEXT")
        c.commit()
        c.close()
    except Exception:
        pass


def seed_tasks():
    if not os.path.exists(TASKS_JSON):
        return 0
    with open(TASKS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    conn = get_conn()
    conn.execute("DELETE FROM tasks")  # 任务库以 tasks.json 为准，先清空
    for t in data["tasks"]:
        conn.execute(
            "INSERT OR REPLACE INTO tasks VALUES (?,?,?,?,?,?)",
            (t["task_id"], t["name"], t["type"],
             json.dumps(t.get("params", {}), ensure_ascii=False),
             t.get("difficulty", 1), t.get("category", "")))
    conn.commit()
    conn.close()
    return len(data["tasks"])


def import_history():
    """把第二阶段举手/拍手记录、第三阶段技能任务记录导入数据库。"""
    n = 0
    if os.path.exists(PHASE2_CSV):
        conn = get_conn()
        with open(PHASE2_CSV, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                name, start = row.get("任务", ""), row.get("开始", "")
                # 幂等：同名同开始时间的记录已存在则跳过
                dup = conn.execute(
                    "SELECT COUNT(*) c FROM records "
                    "WHERE task_name=? AND start_time=?", (name, start)).fetchone()["c"]
                if dup:
                    continue
                conn.execute(
                    "INSERT INTO records (task_name,start_time,end_time,"
                    "elapsed_sec,status,detail,created_at) VALUES (?,?,?,?,?,?,?)",
                    (name, start, row.get("结束", ""),
                     float(row.get("用时秒", 0) or 0),
                     row.get("结果", "") or "完成",
                     json.dumps({"备注": row.get("备注", "")}, ensure_ascii=False),
                     start))
                n += 1
        conn.commit()
        conn.close()
    if os.path.exists(SEQ_CSV):
        conn = get_conn()
        with open(SEQ_CSV, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                tid = row.get("task_id", "")
                dup = conn.execute(
                    "SELECT COUNT(*) c FROM records WHERE task_id=?",
                    (tid,)).fetchone()["c"]
                if dup:
                    continue
                conn.execute(
                    "INSERT INTO records (task_id,task_name,start_time,end_time,"
                    "elapsed_sec,status,detail,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (tid, row.get("任务", ""), "", "",
                     float(row.get("总用时秒", 0) or 0),
                     row.get("状态", "") or "完成",
                     json.dumps({"完成步骤": row.get("完成步骤/总步骤", ""),
                                 "不确定事件": row.get("不确定事件数", 0)},
                                ensure_ascii=False),
                     tid))
                n += 1
        conn.commit()
        conn.close()
    return n


def import_sessions():
    """把技能任务产出的 sessions.csv 增量导入 sessions 表（幂等，按 task_id 去重）。"""
    if not os.path.exists(SESSIONS_CSV):
        return 0
    n = 0
    conn = get_conn()
    with open(SESSIONS_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            tid = row.get("task_id", "")
            dup = conn.execute(
                "SELECT COUNT(*) c FROM sessions WHERE task_id=?",
                (tid,)).fetchone()["c"]
            if dup:
                continue
            conn.execute(
                "INSERT INTO sessions (task_id,task_name,scene,prompt_level,"
                "completed,valid,uncertainty,elapsed_sec,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (tid, row.get("task_name", ""), row.get("scene", ""),
                 int(row.get("prompt_level", 0) or 0),
                 int(row.get("completed", 0) or 0),
                 int(row.get("valid", 1) if row.get("valid") != "" else 1),
                 int(row.get("uncertainty", 0) or 0),
                 float(row.get("elapsed_sec", 0) or 0),
                 row.get("task_id", "")))
            n += 1
    conn.commit()
    conn.close()
    return n


def sync():
    """同步：把 CSV/JSON 里的新训练记录增量导入数据库（幂等）。"""
    r = import_history()
    s = import_sessions()
    return r + s


def seed_sessions():
    """灌入提示依赖评估用的模拟数据（构想报告 7.3 允许模拟数据验证算法）。

    数据为 3 个家庭场景 × 不同提示等级，用于演示 PDI/独立完成率/决策引擎。
    代码注释与文档均如实标注为模拟数据，不冒充真实儿童记录。
    """
    conn = get_conn()
    has = conn.execute("SELECT COUNT(*) c FROM sessions").fetchone()["c"]
    if has:
        conn.close()
        return 0
    # (任务, 场景, 提示等级, 完成, 有效, 不确定, 用时)
    sim = [
        ("举手", "客厅", 0, 1, 1, 0, 4.2),
        ("举手", "客厅", 1, 1, 1, 0, 5.1),
        ("拍手", "客厅", 0, 1, 1, 0, 8.0),
        ("拍手", "客厅", 2, 1, 1, 0, 9.3),
        ("拍手", "客厅", 3, 0, 1, 1, 12.0),
        ("整理玩具", "客厅", 2, 1, 1, 0, 45.0),
        ("整理玩具", "客厅", 4, 1, 1, 0, 60.0),
        ("整理玩具", "客厅", 4, 0, 1, 1, 70.0),
        ("举手", "卧室", 0, 1, 1, 0, 4.0),
        ("举手", "卧室", 0, 1, 1, 0, 4.5),
        ("拍手", "卧室", 1, 1, 1, 0, 8.5),
        ("拍手", "卧室", 2, 0, 1, 0, 11.0),
        ("整理玩具", "卧室", 3, 1, 1, 0, 55.0),
        ("整理玩具", "卧室", 2, 1, 1, 0, 48.0),
        ("整理玩具", "卧室", 4, 0, 1, 1, 75.0),
        ("举手", "餐桌", 0, 1, 1, 0, 4.8),
        ("举手", "餐桌", 1, 1, 1, 0, 5.5),
        ("拍手", "餐桌", 0, 1, 1, 0, 9.0),
        ("拍手", "餐桌", 2, 1, 1, 0, 10.0),
        ("拍手", "餐桌", 3, 0, 1, 0, 13.0),
        ("整理玩具", "餐桌", 2, 1, 1, 0, 52.0),
        ("整理玩具", "餐桌", 3, 1, 1, 0, 58.0),
        ("整理玩具", "餐桌", 4, 0, 1, 1, 80.0),
        ("整理玩具", "餐桌", 1, 1, 1, 0, 44.0),
    ]
    for s in sim:
        conn.execute(
            "INSERT INTO sessions (task_name,scene,prompt_level,completed,"
            "valid,uncertainty,elapsed_sec,created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (s[0], s[1], s[2], s[3], s[4], s[5], s[6],
             "2026-11-10"))
    conn.commit()
    conn.close()
    return len(sim)


def bootstrap():
    init_db()
    t = seed_tasks()
    # 历史导入只做一次（幂等），避免每次启动重复入库
    conn = get_conn()
    has = conn.execute("SELECT COUNT(*) c FROM records").fetchone()["c"]
    conn.close()
    r = 0 if has else import_history()
    seed_sessions()
    return t, r
