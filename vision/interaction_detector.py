# -*- coding: utf-8 -*-
"""
星伴AI 第三阶段 模块二：人与物品交互识别（规则判断，非深度学习）

输出状态：approaching / touching_candidate / picking_candidate /
          placing_candidate / uncertain

核心原则：手靠近物品不等于拿起物品。"拿起"必须同时满足
疑似接触 + 物品中心位移超过阈值。条件不足时如实输出 uncertain。

运行方式（在项目根目录）：python vision/interaction_detector.py
按 q 键退出。
"""

import csv
import os
import time
from collections import deque

import cv2

from object_detector import load_model, detect_objects, draw_detections
from pose_utils import (hand_center, hand_center_21, point_reliable,
                        HAND_POINTS_L, HAND_POINTS_R)

LOG_PATH = "data/interaction_logs/interaction_log.csv"

L_SHOULDER, R_SHOULDER = 11, 12
HAND_POINTS_L = (15, 17, 19, 21)   # 手腕+小指根+食指根+拇指
HAND_POINTS_R = (16, 18, 20, 22)

# 可调参数（实验阶段按数据标定）
VOTE_WINDOW = 8        # 投票窗口帧数
VOTE_MIN = 5           # 窗口内至少几帧成立
TOUCH_EXPAND = 1.35    # 接触判定时边界框放大倍数
PICK_DISP_RATIO = 0.4  # 拿起判定：位移 > 0.4 倍肩宽
PLACE_STILL_SEC = 0.6  # 放下判定：物品静止时长


def dist_to_bbox(px, py, bbox):
    """点到边界框的距离（框内为0）。bbox 为归一化坐标。"""
    x1, y1, x2, y2 = bbox
    dx = max(x1 - px, 0, px - x2)
    dy = max(y1 - py, 0, py - y2)
    return (dx * dx + dy * dy) ** 0.5


def point_in_box(px, py, bbox, expand=1.0):
    """点是否在放大 expand 倍的边界框内。"""
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    return (abs(px - cx) <= (x2 - x1) * expand / 2 and
            abs(py - cy) <= (y2 - y1) * expand / 2)


class InteractionDetector:
    """规则式交互判断器：跟踪目标物品，多帧投票输出交互状态。"""

    def __init__(self, target_name, frame_w, frame_h, preferred_hand="unknown"):
        self.target_name = target_name
        self.frame_w, self.frame_h = frame_w, frame_h
        # 个体化：惯用手。left/right 时优先追踪该手（可见即用，忽略另一手干扰）；
        # unknown/both 时保持"取离物品最近的手"。
        self.preferred_hand = (preferred_hand or "unknown").lower()
        self.prev_center = None      # 物品上一帧中心
        self.touched_center = None   # 首次接触时的物品中心
        self.near_votes = deque(maxlen=VOTE_WINDOW)
        self.dist_history = deque(maxlen=5)
        self.state = "uncertain"
        self.picked = False
        self.still_since = None      # 物品开始静止的时刻
        self.evidence = {}
        self.last_bbox = None        # 最后一次检测到的目标框（宽限期用）
        self.last_seen = 0.0         # 最后检测到目标的时刻
        self.target_track_id = None  # 当前锁定目标的跟踪 ID（防同类物品串台）
        self.confidence = 0.0        # 最近一帧交互判定的连续置信度
        self.GRACE_SEC = 0.5         # 目标丢失宽限期

    def _hand_order(self):
        """返回手部遍历顺序：指定惯用手时该手优先。"""
        if self.preferred_hand == "left":
            return ((HAND_POINTS_L, "left"), (HAND_POINTS_R, "right"))
        if self.preferred_hand == "right":
            return ((HAND_POINTS_R, "right"), (HAND_POINTS_L, "left"))
        return ((HAND_POINTS_L, "left"), (HAND_POINTS_R, "right"))

    def _switch(self, new_state):
        changed = new_state != self.state
        self.state = new_state
        return changed

    def _hand_centers(self, lms, hands):
        """返回 [(掌心坐标, 'left'/'right')]，优先 21 点，缺失时回退 Pose。"""
        out = []
        for idx_pts, hname in self._hand_order():
            hx, hy = None, None
            if hands:
                side = "L" if idx_pts == HAND_POINTS_L else "R"
                c = hand_center_21(hands.get(side))
                if c is not None:
                    hx, hy = c
            if (hx is None and len(lms) > max(idx_pts) and
                    all(point_reliable(lms[i]) for i in idx_pts)):
                hx, hy = hand_center(lms, idx_pts)
            if hx is not None:
                out.append(((hx, hy), hname))
        return out

    def update(self, lms, detections, now, hands=None):
        """输入姿态关键点/手部 21 点和物品检测，返回 (state, evidence, changed)。"""
        # 1. 找目标物品：优先沿用已锁定的 track_id；同类物品多实例时防止串台
        candidates = [d for d in detections if d["name"] == self.target_name]
        target = None
        if self.target_track_id is not None:
            target = next(
                (d for d in candidates
                 if d.get("track_id") == self.target_track_id), None)
        if target is None and candidates:
            # 首次锁定：优先离手最近的候选；手不可见时才退化为置信度最高者
            centers = self._hand_centers(lms, hands)
            if centers:
                def hand_dist(d):
                    bx1, by1, bx2, by2 = d["bbox"]
                    return min(dist_to_bbox(h[0] * self.frame_w,
                                            h[1] * self.frame_h,
                                            (bx1, by1, bx2, by2))
                               for h, _ in centers)
                target = min(candidates, key=hand_dist)
            else:
                target = max(candidates, key=lambda d: d["confidence"])
            self.target_track_id = target.get("track_id")
        if target is None:
            # 宽限期：检测偶尔丢帧时沿用最后已知位置，避免状态闪烁
            if self.last_bbox is not None and now - self.last_seen < self.GRACE_SEC:
                target = {"bbox": self.last_bbox, "confidence": 0.0,
                          "name": self.target_name}
            else:
                self.near_votes.clear()
                self.evidence = {"reason": "no target object in view"}
                return self.state, self.evidence, self._switch("uncertain")
        else:
            self.last_bbox = target["bbox"]
            self.last_seen = now

        # 2. 物品框（像素转归一化）与中心位移（肩宽为单位）
        x1, y1, x2, y2 = [v / self.frame_w if i % 2 == 0 else v / self.frame_h
                          for i, v in enumerate(target["bbox"])]
        ocenter = ((x1 + x2) / 2, (y1 + y2) / 2)
        shoulder_w = abs(lms[L_SHOULDER].x - lms[R_SHOULDER].x) or 0.15
        disp = 0.0
        if self.prev_center is not None:
            disp = ((ocenter[0] - self.prev_center[0]) ** 2 +
                    (ocenter[1] - self.prev_center[1]) ** 2) ** 0.5 / shoulder_w
        self.prev_center = ocenter

        # 3. 手部中心选择（个体化：指定惯用手时优先该手，忽略另一手干扰）
        hand, hand_name = None, None
        prefer = self.preferred_hand in ("left", "right")
        for (hx, hy), hname in self._hand_centers(lms, hands):
            if prefer:
                # 惯用手模式：_hand_order 把惯用手排第一，可见即采用
                hand, hand_name = (hx, hy), hname
                break
            d = dist_to_bbox(hx, hy, (x1, y1, x2, y2))
            if hand is None or d < dist_to_bbox(hand[0], hand[1],
                                                (x1, y1, x2, y2)):
                hand, hand_name = (hx, hy), hname

        if hand is None:
            self.near_votes.clear()
            self.evidence = {"reason": "hand not detected"}
            return self.state, self.evidence, self._switch("uncertain")

        # 4. 手-物关系多帧投票
        inside = point_in_box(hand[0], hand[1], (x1, y1, x2, y2), TOUCH_EXPAND)
        self.near_votes.append(inside)
        near = (len(self.near_votes) >= 3 and sum(self.near_votes) >= VOTE_MIN)
        dist = dist_to_bbox(hand[0], hand[1], (x1, y1, x2, y2)) / shoulder_w

        # 5. 状态推进
        changed = False
        if near:
            self.still_since = None
            if self.touched_center is None:
                self.touched_center = ocenter
            displacement = ((ocenter[0] - self.touched_center[0]) ** 2 +
                            (ocenter[1] - self.touched_center[1]) ** 2) ** 0.5 \
                / shoulder_w
            if displacement >= PICK_DISP_RATIO:
                self.picked = True
                changed = self._switch("picking_candidate")
            else:
                self.dist_history.append(dist)
                shrinking = (len(self.dist_history) >= 3 and
                             self.dist_history[-1] < self.dist_history[0])
                new = "approaching" if (shrinking and not inside) \
                    else "touching_candidate"
                changed = self._switch(new)
        else:
            if self.picked and disp < 0.02:
                # 曾拿起、现在物品静止 -> 疑似放下
                if self.still_since is None:
                    self.still_since = now
                elif now - self.still_since >= PLACE_STILL_SEC:
                    self.picked = False
                    self.touched_center = None
                    changed = self._switch("placing_candidate")
            else:
                self.still_since = None
            if self.state != "placing_candidate":
                changed = self._switch("uncertain")

        vote_ratio = (sum(self.near_votes) / len(self.near_votes)
                      if self.near_votes else 0.0)
        # 连续置信度：投票越一致、手离物品越近、目标跟踪越稳定，分数越高
        proximity = max(0.0, min(1.0, 1.0 - dist / 2.0))
        tracking_bonus = 0.1 if self.target_track_id else 0.0
        self.confidence = round(
            min(1.0, 0.55 * vote_ratio + 0.35 * proximity + tracking_bonus), 3)
        self.evidence = {
            "hand": hand_name,
            "dist": round(dist, 3),
            "frame_disp": round(disp, 3),
            "votes": f"{sum(self.near_votes)}/{len(self.near_votes)}",
            "track_id": self.target_track_id,
            "confidence": self.confidence,
        }
        return self.state, self.evidence, changed


class InteractionLogger:
    """交互状态变化写入 CSV。"""

    def __init__(self, path=LOG_PATH):
        self.path = path
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerow(["时间", "目标物品", "状态", "证据"])

    def log(self, obj, state, evidence):
        with open(self.path, "a", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow([time.strftime("%H:%M:%S"),
                                    obj, state, str(evidence)])
        print(f"[记录] {obj} -> {state}")


def main():
    """演示：姿态 + 物品检测 + 交互状态判断，同屏显示。"""
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python import vision

    POSE_MODEL = "vision/models/pose_landmarker_full.task"
    # 演示目标：按你现有的道具修改类名（如 "bottle" / "teddy bear" / "cup"）
    TARGET_NAME = "bottle"

    latest = {"result": None}

    def on_result(result, _img, _ts):
        latest["result"] = result

    load_model()
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

    detector = None
    logger = InteractionLogger()
    print(f"目标物品: {TARGET_NAME}（改 main() 里的 TARGET_NAME 可换道具）")
    print("把手伸向物品：接近->触碰->拿起->放下，观察状态变化；按 q 退出")

    fps, t_last = 0.0, time.time()

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
        detections = detect_objects(frame_raw, conf=0.35)  # 降低门槛减少漏检

        state, evidence = "uncertain", {}
        pr = latest["result"]
        if pr and pr.pose_landmarks:
            if detector is None:
                detector = InteractionDetector(TARGET_NAME, fw, fh)
            state, evidence, changed = detector.update(
                pr.pose_landmarks[0], detections, now)
            if changed:
                logger.log(TARGET_NAME, state, evidence)
            # 画两个手掌中心（红色大点）
            for idx_pts in (HAND_POINTS_L, HAND_POINTS_R):
                try:
                    hx, hy = hand_center(pr.pose_landmarks[0], idx_pts)
                    cv2.circle(frame_raw, (int(hx * fw), int(hy * fh)),
                               8, (0, 0, 255), -1)
                except IndexError:
                    pass

        draw_detections(frame_raw, detections)
        frame = cv2.flip(frame_raw, 1)

        color = {"approaching": (255, 200, 0),
                 "touching_candidate": (0, 200, 255),
                 "picking_candidate": (0, 255, 0),
                 "placing_candidate": (255, 0, 255),
                 "uncertain": (160, 160, 160)}.get(state, (255, 255, 255))
        cv2.putText(frame, f"STATE: {state}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.putText(frame, str(evidence), (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.putText(frame, f"FPS: {fps:.1f} | reach - touch - lift - place",
                    (10, fh - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (180, 180, 180), 1)

        cv2.imshow("XingBanAI Interaction", frame)
        key = cv2.waitKey(1)
        if (key in (ord("q"), 27) or
                cv2.getWindowProperty("XingBanAI Interaction",
                                      cv2.WND_PROP_VISIBLE) < 1):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"已退出。状态变化记录: {LOG_PATH}")


if __name__ == "__main__":
    main()
