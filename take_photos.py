import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np


WINDOW_NAME = "Take Photos"
CAMERA_SELECT_WINDOW = "Select Camera"


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Preview camera frames and save photos into ./correct"
	)
	parser.add_argument(
		"--camera-index",
		type=int,
		default=None,
		help="Optional camera index. If omitted, the script scans and lets you choose.",
	)
	parser.add_argument(
		"--scan-max-index",
		type=int,
		default=2,
		help="Max camera index to probe when searching for available cameras.",
	)
	parser.add_argument(
		"--output-dir",
		type=str,
		default="./correct",
		help="Directory where captured images are saved.",
	)
	parser.add_argument(
		"--prefix",
		type=str,
		default="photo",
		help="Filename prefix for saved images.",
	)
	return parser.parse_args()


def detect_cameras(max_index: int = 2) -> List[Tuple[int, int, int]]:
	cameras: List[Tuple[int, int, int]] = []
	for idx in range(max_index + 1):
		cap = cv2.VideoCapture(idx)
		if not cap.isOpened():
			cap.release()
			continue

		ok, frame = cap.read()
		cap.release()
		if not ok or frame is None:
			continue

		height, width = frame.shape[:2]
		cameras.append((idx, width, height))
	return cameras


def select_camera_interactively(cameras: List[Tuple[int, int, int]]) -> int:
	if not cameras:
		raise RuntimeError("No available camera detected. Check camera permission or device connection.")

	if len(cameras) == 1:
		return cameras[0][0]

	board_height = 420
	board_width = 880
	board = np.zeros((board_height, board_width, 3), dtype=np.uint8)
	board[:] = (24, 24, 24)

	cv2.namedWindow(CAMERA_SELECT_WINDOW, cv2.WINDOW_NORMAL)
	cv2.resizeWindow(CAMERA_SELECT_WINDOW, board_width, board_height)

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
		for idx, width, height in cameras:
			cv2.putText(
				canvas,
				f"[{idx}] Camera {idx} - {width}x{height}",
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
			for idx, _width, _height in cameras:
				if idx == selected:
					cv2.destroyWindow(CAMERA_SELECT_WINDOW)
					return idx


def save_frame(frame: np.ndarray, output_dir: Path, prefix: str) -> Path:
	output_dir.mkdir(parents=True, exist_ok=True)
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	output_path = output_dir / f"{prefix}_{timestamp}.jpg"
	if not cv2.imwrite(str(output_path), frame):
		raise RuntimeError(f"Failed to save image to {output_path}")
	return output_path


def main() -> None:
	args = parse_args()
	output_dir = Path(args.output_dir)

	if args.camera_index is None:
		scan_max_index = max(0, int(args.scan_max_index))
		available_cameras = detect_cameras(max_index=scan_max_index)
		camera_index = select_camera_interactively(available_cameras)
	else:
		camera_index = args.camera_index

	cap = cv2.VideoCapture(camera_index)
	if not cap.isOpened():
		raise RuntimeError(
			f"Failed to open camera index {camera_index}. Check camera permission or choose another index."
		)

	ok, frame = cap.read()
	if not ok or frame is None:
		cap.release()
		raise RuntimeError("Failed to read initial frame from camera")

	cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

	last_saved_path = None

	try:
		while True:
			ok, frame = cap.read()
			if not ok or frame is None:
				break

			preview = frame.copy()
			cv2.putText(
				preview,
				"Press S or Space to save, Q to quit",
				(12, 30),
				cv2.FONT_HERSHEY_SIMPLEX,
				0.75,
				(255, 255, 255),
				2,
				cv2.LINE_AA,
			)
			if last_saved_path is not None:
				cv2.putText(
					preview,
					f"Saved: {last_saved_path.name}",
					(12, 60),
					cv2.FONT_HERSHEY_SIMPLEX,
					0.65,
					(80, 255, 120),
					2,
					cv2.LINE_AA,
				)

			cv2.imshow(WINDOW_NAME, preview)
			key = cv2.waitKeyEx(1)

			if key in (ord("q"), ord("Q")):
				break

			if key in (ord("s"), ord("S"), 32, 13):
				last_saved_path = save_frame(frame, output_dir, args.prefix)
				print(f"Saved: {last_saved_path.resolve()}")
	finally:
		cap.release()
		cv2.destroyAllWindows()


if __name__ == "__main__":
	main()
