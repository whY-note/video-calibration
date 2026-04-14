# Video Placement Calibration Tool

This project provides a real-time calibration utility for object placement.

- Bottom layer: live camera video.
- Top layer: reference image from `./correct` with 50% transparency.
- Video frame is resized to the same width/height as the reference image so both layers start with identical size.
- Goal: move the real object until it aligns with the expected position in the overlay image.

## 1. Install

```bash
python3 -m pip install -r requirements.txt
```

## 2. Run

Default camera and default image:

```bash
python3 calibration_overlay.py
```

Startup camera handling is automatic:

- If only one camera is detected, the app opens it directly.
- If multiple cameras are detected, the app shows a camera list window and you press a number key to choose.

Choose external camera directly (optional, skip startup selection):

```bash
python3 calibration_overlay.py --camera-index 1
```

Save calibration result to JSON when quit:

```bash
python3 calibration_overlay.py --save-config --output-json calibration.json
```

Capture photos into `./correct`:

```bash
python3 take_photos.py
```

## 3. Controls

- Mouse: drag the overlay image.
- Keyboard: Arrow keys or WASD to move overlay.
- `-` / `=`: decrease/increase keyboard move step.
- `[` / `]`: scale overlay down/up during runtime.
- `Q`: quit.

## 4. Key Parameters

- `--camera-index`: optional camera device index. If omitted, startup uses camera list and key selection.
- `--scan-max-index`: max index used by startup camera scan (default `2`).
- `--image-path`: reference image path (default `./correct/correct.jpg`).
- `--opacity`: overlay opacity in range `[0.0, 1.0]` (default `0.5`).
- `--move-step`: initial keyboard move step in pixels (default `2`).
- `--save-config`: enable writing result JSON on exit.
- `--output-json`: output JSON path (default `calibration_config.json`).

## 5. JSON Output Fields

When `--save-config` is enabled, output JSON includes:

- `timestamp`
- `camera_index`
- `image_path`
- `opacity`
- `frame_size.width`
- `frame_size.height`
- `overlay_size.width`
- `overlay_size.height`
- `overlay_position.x`
- `overlay_position.y`

## 6. Troubleshooting

- Camera cannot open:
  - Check macOS camera permission for your terminal/IDE.
  - Try another camera index (`--camera-index 1`, `--camera-index 2`).
  - If your camera index is larger, increase startup scan range (`--scan-max-index 5`).
- Image cannot load:
  - Confirm `--image-path` exists and points to a valid image file.