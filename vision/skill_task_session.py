# -*- coding: utf-8 -*-
"""
星伴AI 第三阶段 模块四：技能训练任务集成
链路：摄像头 → 姿态识别 + YOLO物品检测 → 人-物交互判断 → 行为步骤FSM
任务：找到玩具 → 接近玩具 → 拿起玩具 → 移动玩具 → 放入收纳盒

道具约定（按你现有实物改常量）：
    TARGET_NAME     玩具（被拿取的物品）
    CONTAINER_NAMES 收纳盒替代物（COCO 无"盒子"类，用碗/书替代，如实标注）

记录：data/sequence_logs/ 每次运行生成 JSON 明细 + 汇总 CSV。
运行方式（项目根目录）：python vision/skill_task_session.py
"""

import argparse
import csv
import json
import os
import time

import cv2

from object_detector import (load_model, detect_objects, draw_detections,
                             has_custom_model, load_custom_model)
from interaction_detector import (InteractionDetector, hand_center,
                                  HAND_POINTS_L, HAND_POINTS_R)
from behavior_sequence import BehaviorFSM

# 命令行可配置道具（任务配置化的第一步）：
#   python vision/skill_task_session.py --target cup --containers book remote
_parser = argparse.ArgumentParser(description="星伴AI 技能训练任务")
_parser.add_argument("--target", default="bottle",
                     help="玩具的COCO类名（被拿取物品）")
_parser.add_argument("--containers", nargs="+",
                     default=["book", "cup", "remote", "bowl",
                              "clock", "cell phone", "keyboard", "mouse"],
                     help="放置目标候选类名列表")
_parser.add_argument("--scene", default="客厅",
                     help="家庭场景（客厅/卧室/餐桌等，供跨场景分析）")
_parser.add_argument("--prompt", type=int, default=0, choices=[0, 1, 2, 3, 4],
                     help="提示等级 0独立/1视觉/2语音/3示范/4家长协助（供PDI计算）")
_args, _ = _parser.parse_known_args()

TARGET_NAME = _args.target
# 收纳目标：COCO 无"盒子"类（铁盒/纸盒均不可识别，须自训练解决），
# 因此用候选列表，程序取画面中检测到的第一个目标物作为放置点
CONTAINER_NAMES = _args.containers
SCENE = _args.scene
PROMPT_LEVEL = _args.prompt
LOG_DIR = "data/sequence_logs"

STEP_NAMES_EN = {
    "find_toy": "find the toy",
    "approach_toy": "reach toward the toy",
    "pick_toy": "pick up the toy",
    "move_toy": "move the toy",
    "place_toy": "put it in the box",
}


def norm_det(det, w, h):
    """像素坐标检测结果 -> 归一化坐标。"""
    x1, y1, x2, y2 = det["bbox"]
    return {"name": det["name"],
            "bbox": (x1 / w, y1 / h, x2 / w, y2 / h),
            "center": (det["center"][0] / w, det["center"][1] / h),
            "confidence": det["confidence"]}


def save_records(fsm, t_start, t_end, finished):
    """任务结束（完成或中途退出）时写入 JSON 明细和 CSV 汇总。"""
    os.makedirs(LOG_DIR, exist_ok=True)
    st = fsm.summary()
    task_id = time.strftime("%Y%m%d_%H%M%S")
    fmt = "%H:%M:%S"
    record = {
        "task_id": task_id,
        "task_name": "pick and place (5 steps)",
        "target_object": TARGET_NAME,
        "container_object": CONTAINER_NAMES,
        "start_time": time.strftime(fmt, time.localtime(t_start)),
        "end_time": time.strftime(fmt, time.localtime(t_end)),
        "total_elapsed_sec": st["total_elapsed"],
        "completed_steps": st["completed_steps"],
        "total_steps": st["total_steps"],
        "step_durations": st["step_durations"],
        "completion_status": "完成" if finished else "未完成(中途退出)",
        "uncertainty_events": [
            {"time": time.strftime(fmt, time.localtime(t)),
             "type": e, "detail": d}
            for t, e, d in st["uncertain_events"]],
        "all_events": [
            {"time": time.strftime(fmt, time.localtime(t)),
             "type": e, "detail": d}
            for t, e, d in st["events"]],
    }
    json_path = os.path.join(LOG_DIR, f"sequence_{task_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    csv_path = os.path.join(LOG_DIR, "sequence_summary.csv")
    if not os.path.exists(csv_path):
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(
                ["task_id", "任务", "目标物", "完成步骤/总步骤",
                 "总用时秒", "状态", "不确定事件数"])
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerow([
            task_id, "拿起并放入收纳盒", TARGET_NAME,
            f"{len(st['completed_steps'])}/{st['total_steps']}",
            st["total_elapsed"], record["completion_status"],
            len(st["uncertain_events"])])

    # 追加训练会话（提示等级+场景），供 PDI/独立完成率/跨场景分析使用
    sess_path = os.path.join(LOG_DIR, "sessions.csv")
    if not os.path.exists(sess_path):
        with open(sess_path, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(
                ["task_id", "task_name", "scene", "prompt_level",
                 "completed", "valid", "uncertainty", "elapsed_sec"])
    finished_flag = 1 if record["completion_status"] == "完成" else 0
    unc = 1 if st["uncertain_events"] else 0
    with open(sess_path, "a", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerow([
            task_id, "整理玩具", SCENE, PROMPT_LEVEL,
            finished_flag, 1, unc, st["total_elapsed"]])
    print(f"记录已写入: {json_path}")
    return json_path


def main():
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python import vision

    POSE_MODEL = "vision/models/pose_landmarker_full.task"
    latest = {"result": None}

    def on_result(result, _img, _ts):
        latest["result"] = result

    load_model()
    # 家庭个性化：加载目标物/放置目标对应的自定义模型（可多个并存）
    for _cname in list(CONTAINER_NAMES) + [TARGET_NAME]:
        if has_custom_model(_cname):
            if load_custom_model(_cname):
                print(f"已加载家庭自定义模型: {_cname}")
    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=POSE_MODEL,
                                 delegate=BaseOptions.Delegate.CPU),
        running_mode=vision.RunningMode.LIVE_STREAM,
        min_pose_detection_confidence=0.6,
        min_tracking_confidence=0.7,
        result_callback=on_result,
    )
    landmarker = vision.PoseLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("DirectShow 接口打开失败，尝试 MSMF 接口...")
        cap = cv2.VideoCapture(0, cv2.CAP_MSMF)
    if not cap.isOpened():
        print("错误：无法打开摄像头")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    fsm = BehaviorFSM()
    inter = None
    t_start = t_end = None
    saved = False
    print(f"任务道具: 玩具={TARGET_NAME}, 收纳盒替代={CONTAINER_NAMES}")
    print("摆好道具后开始: 找到 -> 接近 -> 拿起 -> 移动 -> 放入；按 q 退出")

    # ---- 主循环：世界组装与显示 ----
    fps, t_last, diag_t = 0.0, time.time(), 0.0
    win = "XingBanAI Skill Task"
    while True:
        ok, frame_raw = cap.read()
        if not ok:
            print("错误：摄像头画面读取失败")
            break
        fh, fw = frame_raw.shape[:2]
        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - t_last, 1e-6))
        t_last = now

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_raw)
        landmarker.detect_async(mp_image, int(now * 1000))
        detections = detect_objects(frame_raw, conf=0.35)

        # 组装 World：玩具 / 收纳盒 / 交互状态
        toy = cont = None
        for det in detections:
            if det["name"] == TARGET_NAME and toy is None:
                toy = norm_det(det, fw, fh)
            elif det["name"] in CONTAINER_NAMES and cont is None:
                cont = norm_det(det, fw, fh)
        interaction = "uncertain"
        pr = latest["result"]
        if pr and pr.pose_landmarks:
            if inter is None:
                inter = InteractionDetector(TARGET_NAME, fw, fh)
            interaction, ev, ch = inter.update(pr.pose_landmarks[0],
                                               detections, now)
        if t_start is None:
            t_start = now
            fsm.start(now)

        st = fsm.update({"now": now, "interaction": interaction,
                         "toy": toy, "container": cont}, now)
        # 诊断输出（每2秒）：观察玩具位置与拿起点的距离，用于标定阈值
        if now - diag_t > 2.0 and toy is not None:
            diag_t = now
            pc = fsm._pickup_center
            d = (0.0 if pc is None else
                 ((toy["center"][0] - pc[0]) ** 2 +
                  (toy["center"][1] - pc[1]) ** 2) ** 0.5)
            print(f"[诊断] step={st['current_step']} state={interaction} "
                  f"toy=({toy['center'][0]:.2f},{toy['center'][1]:.2f}) "
                  f"距拿起点={d:.2f} container={'有' if cont else '无'}")
        if st["status"] == "done" and not saved:
            saved = True
            t_end = now
            save_records(fsm, t_start, t_end, finished=True)

        draw_detections(frame_raw, detections)
        frame = cv2.flip(frame_raw, 1)

        # 显示：步骤清单（对勾=完成，箭头=当前）+ 交互状态
        y0 = 30
        for i, step in enumerate(fsm.steps):
            mark = ("[x]" if step.name in st["completed_steps"]
                    else ("[>]" if i == fsm.idx else "[ ]"))
            color = ((0, 255, 0) if mark == "[x]" else
                     (0, 255, 255) if mark == "[>]" else (160, 160, 160))
            cv2.putText(frame, f"{mark} {STEP_NAMES_EN[step.name]}",
                        (10, y0 + i * 28), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, color, 2)
        y_info = y0 + len(fsm.steps) * 28 + 5
        cv2.putText(frame, f"STATE: {interaction}", (10, y_info),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 160, 0), 2)
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, y_info + 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
        if st["status"] == "done":
            cv2.putText(frame, "TASK COMPLETE!", (10, y_info + 52),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        elif st["current_step"] == "place_toy" and cont is None:
            cv2.putText(frame, "No target seen: put a book/cup/remote here!",
                        (10, y_info + 52), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0, 100, 255), 2)
        elif st["uncertain_events"]:
            cv2.putText(frame, "timeout, keep trying...",
                        (10, y_info + 52),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 1)

        cv2.imshow(win, frame)
        key = cv2.waitKey(1)
        if key in (ord("q"), 27) or cv2.getWindowProperty(
                win, cv2.WND_PROP_VISIBLE) < 1:
            break

    t_end = time.time()
    if not saved:
        save_records(fsm, t_start or t_end, t_end, finished=False)
    cap.release()
    cv2.destroyAllWindows()
    print("已退出")


if __name__ == "__main__":
    main()
