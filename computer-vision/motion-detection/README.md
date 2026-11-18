# Motion Detection with OpenCV MOG2

A Python computer vision exercise demonstrating real-time motion detection using a webcam and OpenCV.

## Overview

This application uses OpenCV's MOG2 background subtraction algorithm to distinguish moving foreground objects from the background.

## Demo

The following screenshot demonstrates the motion detection process.

![OpenCV MOG2 Motion Detection Demo](assets/motion_detection_demo.png)

## Techniques

- Webcam capture using `cv2.VideoCapture()`
- Gaussian blur for noise reduction
- Background subtraction using `cv2.createBackgroundSubtractorMOG2()`
- Binary thresholding for foreground mask processing
- Real-time video frame processing

## Requirements

- Python
- OpenCV
- NumPy
- A working webcam

## Run

```bash
pip install opencv-python numpy
python motion_detection_mog2.py
```

## Notes

This project was developed as part of computer vision coursework and is intended for educational purposes.