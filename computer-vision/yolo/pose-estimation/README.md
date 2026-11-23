# YOLOv8 Human Pose Estimation

Estimate human body keypoints in a webcam stream or local video using a pretrained YOLOv8 pose model, Ultralytics, PyTorch, and OpenCV. The script displays person detections and pose skeletons in an OpenCV window.

## Features

- Webcam input by default, or a video file via `--file`
- YOLOv8 pose weights (`yolov8n-pose.pt` by default), with an option to specify another checkpoint
- Automatic device selection: CUDA, Apple Silicon MPS, or CPU
- Configurable display width while preserving aspect ratio
- Visualization of detected people, body keypoints, and skeleton connections

## Requirements

- Python 3
- `ultralytics`
- `torch`
- `opencv-python`
- Internet access on first use to download default model weights (unless cached)

Install dependencies in a virtual environment:

```bash
pip install ultralytics torch opencv-python
```

## Usage

Run these commands from this folder (or adjust the script and video paths accordingly).

**Webcam:**

```bash
python yolov8_pose.py
```

**Video file:**

```bash
python yolov8_pose.py --file assets/sample.mp4
```

**Select pose weights and display width:**

```bash
python yolov8_pose.py --weights yolov8s-pose.pt --width 800 --file assets/sample.mp4
```

Press **Q** in the OpenCV window to quit.

## How it works

1. Parse optional model, video, and display-width arguments.
2. Select CUDA, MPS, or CPU when available.
3. Load the pretrained pose model using `ultralytics.YOLO`.
4. Read frames from a webcam or video file and run pose inference.
5. Use Ultralytics' `results[0].plot()` to draw detections and keypoints, then display them with OpenCV.

## Demo

Add an image you have permission to share at `assets/pose_demo.png`, then uncomment:

<!-- ![YOLOv8 pose estimation result](assets/pose_demo.png) -->

## Notes

- Despite the original classroom filename `yolov5pose.py`, the script uses **YOLOv8** pose weights and the Ultralytics API.
- This exercise performs **inference with pretrained weights**, not model training.
- The input video is optional and is not included in this repository.
- Avoid committing large model checkpoints or copyrighted video clips without permission.
