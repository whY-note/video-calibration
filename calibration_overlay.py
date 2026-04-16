import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


WINDOW_NAME = "Placement Calibration"
CAMERA_SELECT_WINDOW = "Select Camera"


@dataclass
class OverlayState:
    x: int
    y: int
    width: int
    height: int
    dragging: bool = False
    drag_offset_x: int = 0
    drag_offset_y: int = 0


def clamp_opacity(opacity: float) -> float:
    return max(0.0, min(1.0, opacity))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Real-time calibration tool with transparent image overlay on live video"
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=None,
        help="Optional camera index. If omitted, startup will show camera list for key selection.",
    )
    parser.add_argument(
        "--image-path",
        type=str,
        # default="./correct/correct.jpg",
        # default="./correct/blank.jpg",
        default="./correct/three_blocks.jpg",
        help="Path to reference image",
    )
    parser.add_argument(
        "--opacity",
        type=float,
        default=0.5,
        help="Overlay opacity between 0.0 and 1.0 (default: 0.5)",
    )
    parser.add_argument(
        "--save-config",
        action="store_true",
        help="Save calibration parameters to JSON when quitting",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="calibration_config.json",
        help="Output JSON path when --save-config is enabled",
    )
    parser.add_argument(
        "--move-step",
        type=int,
        default=2,
        help="Keyboard move step in pixels (default: 2)",
    )
    parser.add_argument(
        "--scan-max-index",
        type=int,
        default=2,
        help="Max camera index to probe for startup selection (default: 2)",
    )
    return parser.parse_args()


def scale_to_frame(image: np.ndarray, frame_w: int, frame_h: int) -> np.ndarray:
    image_h, image_w = image.shape[:2]
    scale = min(frame_w / image_w, frame_h / image_h)
    new_w = max(1, int(image_w * scale))
    new_h = max(1, int(image_h * scale))
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def resize_overlay(base_overlay: np.ndarray, scale: float) -> np.ndarray:
    base_h, base_w = base_overlay.shape[:2]
    new_w = max(1, int(base_w * scale))
    new_h = max(1, int(base_h * scale))
    return cv2.resize(base_overlay, (new_w, new_h), interpolation=cv2.INTER_LINEAR)


def detect_cameras(max_index: int = 2) -> list[tuple[int, int, int]]:
    cameras: list[tuple[int, int, int]] = []
    for idx in range(max_index + 1):
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            cap.release()
            continue

        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            continue

        h, w = frame.shape[:2]
        cameras.append((idx, w, h))
    return cameras


def select_camera_interactively(cameras: list[tuple[int, int, int]]) -> int:
    if not cameras:
        raise RuntimeError("No available camera detected. Check camera permission or device connection.")

    if len(cameras) == 1:
        return cameras[0][0]

    board_h = 420
    board_w = 880
    board = np.zeros((board_h, board_w, 3), dtype=np.uint8)
    board[:] = (24, 24, 24)

    cv2.namedWindow(CAMERA_SELECT_WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(CAMERA_SELECT_WINDOW, board_w, board_h)

    while True:
        canvas = board.copy()
        cv2.putText(
            canvas,
            "Select camera by key (available indexes)",
            (24, 48),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (235, 235, 235),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            "Press Q to quit",
            (24, 84),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (170, 170, 170),
            1,
            cv2.LINE_AA,
        )

        y = 132
        for idx, w, h in cameras:
            cv2.putText(
                canvas,
                f"[{idx}] Camera {idx} - {w}x{h}",
                (36, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.72,
                (122, 220, 255),
                2,
                cv2.LINE_AA,
            )
            y += 42

        cv2.imshow(CAMERA_SELECT_WINDOW, canvas)
        key = cv2.waitKeyEx(20)

        if key in (ord("q"), ord("Q"), 27):
            cv2.destroyWindow(CAMERA_SELECT_WINDOW)
            raise KeyboardInterrupt("Camera selection cancelled by user")

        if ord("0") <= key <= ord("9"):
            selected = key - ord("0")
            for idx, _w, _h in cameras:
                if idx == selected:
                    cv2.destroyWindow(CAMERA_SELECT_WINDOW)
                    return idx


def blend_overlay(frame: np.ndarray, overlay: np.ndarray, state: OverlayState, opacity: float) -> np.ndarray:
    out = frame.copy()

    frame_h, frame_w = frame.shape[:2]
    x1 = state.x
    y1 = state.y
    x2 = state.x + state.width
    y2 = state.y + state.height

    vis_x1 = max(0, x1)
    vis_y1 = max(0, y1)
    vis_x2 = min(frame_w, x2)
    vis_y2 = min(frame_h, y2)

    if vis_x1 >= vis_x2 or vis_y1 >= vis_y2:
        return out

    ov_x1 = vis_x1 - x1
    ov_y1 = vis_y1 - y1
    ov_x2 = ov_x1 + (vis_x2 - vis_x1)
    ov_y2 = ov_y1 + (vis_y2 - vis_y1)

    roi_frame = out[vis_y1:vis_y2, vis_x1:vis_x2]
    roi_overlay = overlay[ov_y1:ov_y2, ov_x1:ov_x2]
    blended = cv2.addWeighted(roi_frame, 1.0 - opacity, roi_overlay, opacity, 0.0)
    out[vis_y1:vis_y2, vis_x1:vis_x2] = blended
    return out


def draw_help_text(frame: np.ndarray, move_step: int) -> None:
    lines = [
        "Mouse: drag overlay image",
        f"Keyboard: arrows/WASD move ({move_step}px)",
        "[-]/[=]: decrease/increase step",
        "[/]: scale down/up overlay",
        "Q: quit",
    ]
    y = 24
    for text in lines:
        cv2.putText(
            frame,
            text,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            text,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (30, 30, 30),
            1,
            cv2.LINE_AA,
        )
        y += 24


def is_inside_overlay(mouse_x: int, mouse_y: int, state: OverlayState) -> bool:
    return (
        state.x <= mouse_x < state.x + state.width
        and state.y <= mouse_y < state.y + state.height
    )


def write_config(
    output_path: Path,
    args: argparse.Namespace,
    camera_index: int,
    frame_w: int,
    frame_h: int,
    state: OverlayState,
    opacity: float,
) -> None:
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "camera_index": camera_index,
        "image_path": str(Path(args.image_path).resolve()),
        "opacity": opacity,
        "frame_size": {"width": frame_w, "height": frame_h},
        "overlay_size": {"width": state.width, "height": state.height},
        "overlay_position": {"x": state.x, "y": state.y},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    opacity = clamp_opacity(args.opacity)
    move_step = max(1, int(args.move_step))
    overlay_scale = 1.0

    image_path = Path(args.image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Reference image not found: {image_path}")

    reference_image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if reference_image is None:
        raise ValueError(f"Failed to read reference image: {image_path}")
    # reference_image = cv2.flip(reference_image, 1)

    if args.camera_index is None:
        scan_max_index = max(0, int(args.scan_max_index))
        available_cameras = detect_cameras(max_index=scan_max_index)
        camera_index = select_camera_interactively(available_cameras)
    else:
        camera_index = args.camera_index

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(
            f"Failed to open camera index {camera_index}. "
            "Check camera permission or choose another index."
        )

    ok, frame = cap.read()
    if not ok or frame is None:
        cap.release()
        raise RuntimeError("Failed to read initial frame from camera")

    ref_h, ref_w = reference_image.shape[:2]
    frame_w = ref_w
    frame_h = ref_h
    base_overlay = reference_image.copy()
    overlay = base_overlay.copy()
    ov_h, ov_w = overlay.shape[:2]
    state = OverlayState(
        x=0,
        y=0,
        width=ov_w,
        height=ov_h,
    )

    def on_mouse(event: int, x: int, y: int, _flags: int, user_state: OverlayState) -> None:
        if event == cv2.EVENT_LBUTTONDOWN and is_inside_overlay(x, y, user_state):
            user_state.dragging = True
            user_state.drag_offset_x = x - user_state.x
            user_state.drag_offset_y = y - user_state.y
        elif event == cv2.EVENT_MOUSEMOVE and user_state.dragging:
            user_state.x = x - user_state.drag_offset_x
            user_state.y = y - user_state.drag_offset_y
        elif event == cv2.EVENT_LBUTTONUP:
            user_state.dragging = False

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WINDOW_NAME, on_mouse, state)

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break

            frame = cv2.resize(frame, (frame_w, frame_h), interpolation=cv2.INTER_AREA)

            combined = blend_overlay(frame, overlay, state, opacity)
            draw_help_text(combined, move_step)
            cv2.imshow(WINDOW_NAME, combined)

            key = cv2.waitKeyEx(1)
            if key in (ord("q"), ord("Q")):
                break

            if key in (81, 2424832, ord("a"), ord("A")):
                state.x -= move_step
            elif key in (82, 2490368, ord("w"), ord("W")):
                state.y -= move_step
            elif key in (83, 2555904, ord("d"), ord("D")):
                state.x += move_step
            elif key in (84, 2621440, ord("s"), ord("S")):
                state.y += move_step
            elif key == ord("-"):
                move_step = max(1, move_step - 1)
            elif key in (ord("="), ord("+")):
                move_step = move_step + 1
            elif key == ord("["):
                old_center_x = state.x + state.width // 2
                old_center_y = state.y + state.height // 2
                overlay_scale = max(0.1, round(overlay_scale * 0.98, 4))
                overlay = resize_overlay(base_overlay, overlay_scale)
                state.height, state.width = overlay.shape[:2]
                state.x = old_center_x - state.width // 2
                state.y = old_center_y - state.height // 2
            elif key == ord("]"):
                old_center_x = state.x + state.width // 2
                old_center_y = state.y + state.height // 2
                overlay_scale = min(3.0, round(overlay_scale * 1.02, 4))
                overlay = resize_overlay(base_overlay, overlay_scale)
                state.height, state.width = overlay.shape[:2]
                state.x = old_center_x - state.width // 2
                state.y = old_center_y - state.height // 2
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if args.save_config:
        output_path = Path(args.output_json)
        write_config(output_path, args, camera_index, frame_w, frame_h, state, opacity)
        print(f"Calibration config saved: {output_path.resolve()}")


if __name__ == "__main__":
    main()