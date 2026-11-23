# YOLOv5 Object Detection

Run pretrained YOLOv5 object detection on a webcam stream or a local video using Python, PyTorch, and OpenCV. The script displays bounding boxes, class labels, and confidence scores in an OpenCV window.

## Features

- Webcam input by default, or a video file via `--file`
- Pretrained YOLOv5 weights (`yolov5s` by default) or a custom `.pt` checkpoint
- Automatic device selection: CUDA, Apple Silicon MPS, or CPU
- Configurable display width while preserving aspect ratio
- Confidence threshold set to `0.4` in the script

## Requirements

- Python 3
- `torch`
- `opencv-python`
- Internet access on first use to fetch YOLOv5 through PyTorch Hub (unless cached)

Install the Python dependencies in a virtual environment:

```bash
pip install torch opencv-python
```

> PyTorch Hub may require additional YOLOv5 repository dependencies on first use. Check any installation messages from the downloaded repository.

## Usage

Run these commands from this folder (or adjust the script and video paths accordingly).

**Webcam:**

```bash
python yolov5_detection.py
```

**Video file:**

```bash
python yolov5_detection.py --file assets/sample.mp4
```

**Select weights and display width:**

```bash
python yolov5_detection.py --weights yolov5s --width 800 --file assets/sample.mp4
```

**Custom weights:**

```bash
python yolov5_detection.py --weights path/to/best.pt --file assets/sample.mp4
```

Press **Q** in the OpenCV window to quit.

## How it works

1. Parse optional model, video, and display-width arguments.
2. Select CUDA, MPS, or CPU when available.
3. Load YOLOv5 using `torch.hub.load('ultralytics/yolov5', ...)`.
4. Read frames from a webcam or video file and run model inference.
5. Render predictions and display them with OpenCV.

## Demo

Add an image you have permission to share at `assets/detection_demo.png`, then uncomment:

<!-- ![YOLOv5 detection result](assets/detection_demo.png) -->

## Notes

- This exercise performs **inference with pretrained weights**, not model training.
- The input video is optional and is not included in this repository.
- Avoid committing large model checkpoints or copyrighted video clips without permission.
