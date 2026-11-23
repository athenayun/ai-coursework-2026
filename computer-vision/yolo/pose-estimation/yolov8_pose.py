import os
import platform
import sys
import argparse

# 針對 macOS Apple Silicon (MPS)：若遇到不支援的算子自動回退到 CPU，避免程式崩潰
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

import cv2
import torch
from ultralytics import YOLO


def parse_arguments():
    """解析命令列參數"""
    parser = argparse.ArgumentParser(description="YOLOv8 Pose Estimation (Webcam / Video)")
    parser.add_argument(
        '-m', '--weights',
        type=str,
        default='yolov8n-pose.pt',
        help='指定 Pose 模型權重檔路徑 (例如: yolov8n-pose.pt 或 yolov8s-pose.pt)'
    )
    parser.add_argument(
        '-f', '--file',
        type=str,
        default=None,
        help='指定輸入的影片檔路徑 (例如: test.mp4)。若未指定則預設開啟攝影機。'
    )
    parser.add_argument(
        '-w', '--width',
        type=int,
        default=None,
        help='指定顯示畫面的寬度 (像素)，高度將自動等比例縮放 (例如: 800)'
    )
    return parser.parse_args()


def get_device():
    """自動判斷最佳硬體加速裝置"""
    if torch.cuda.is_available():
        device = 'cuda'
        print("使用中裝置: NVIDIA CUDA (GPU)")
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        device = 'mps'
        print("使用中裝置: Apple Silicon MPS (Mac GPU)")
    else:
        device = 'cpu'
        print("警告：未偵測到硬體加速，將會使用 CPU 執行（速度會比較慢）。")
    return device


def resize_by_width(frame, target_width):
    """依據指定寬度進行等比例縮放"""
    h, w = frame.shape[:2]
    if w == target_width:
        return frame
    scale = target_width / float(w)
    target_height = int(h * scale)
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    return cv2.resize(frame, (target_width, target_height), interpolation=interpolation)


def main():
    # 1. 取得命令列參數
    args = parse_arguments()

    if args.width is not None and args.width <= 0:
        print("錯誤：-w / --width 必須為大於 0 的整數。")
        sys.exit(1)

    # 2. 取得硬體裝置
    device = get_device()

    # 3. 載入 YOLOv8 Pose 模型（若本地沒有，會自動從網路下載）
    print(f"正在載入肢體偵測模型: {args.weights} ...")
    try:
        model = YOLO(args.weights)
    except Exception as e:
        print(f"載入模型失敗: {e}")
        sys.exit(1)

    # 4. 決定視訊來源（MP4 檔案 或 攝影機）
    is_mac = platform.system() == 'Darwin'

    if args.file:
        if not os.path.exists(args.file):
            print(f"錯誤：找不到指定的影片檔案 '{args.file}'")
            sys.exit(1)
        cap = cv2.VideoCapture(args.file)
        window_title = f"YOLOv8 Pose - {os.path.basename(args.file)}"
        source_desc = f"影片檔案 ({args.file})"
    else:
        # macOS 指定 AVFoundation 後端可避免攝影機開啟失敗
        if is_mac:
            cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
        else:
            cap = cv2.VideoCapture(0)
        window_title = "YOLOv8 Pose Live Detection"
        source_desc = "攝影機"

    if not cap.isOpened():
        print(f"錯誤：無法開啟{source_desc}。")
        if is_mac and not args.file:
            print("提示：請確認已在 macOS「系統設定 > 隱私權與安全性 > 相機」中允許終端機或 IDE 存取相機。")
        sys.exit(1)

    print(f"已成功開啟{source_desc}，進行肢體關鍵點偵測中，按 'q' 鍵即可退出程式。")

    # 5. 偵測主迴圈
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                if args.file:
                    print("影片播放完畢。")
                else:
                    print("無法讀取視訊畫面。")
                break

            # 進行肢體姿態推論 (指定 device)
            results = model(frame, device=device, verbose=False)

            # ultralytics 的 .plot() 會自動把骨架和關鍵點畫在畫面上
            rendered_frame = results[0].plot()

            # 若有指定 -w，則依寬度等比例縮放
            if args.width:
                rendered_frame = resize_by_width(rendered_frame, args.width)

            # 顯示畫面
            cv2.imshow(window_title, rendered_frame)

            # 按 'q' 鍵退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        # 6. 釋放資源
        cap.release()
        cv2.destroyAllWindows()
        # macOS 上額外呼叫一次 waitKey，避免視窗關閉時殘留或卡住
        if is_mac:
            cv2.waitKey(1)
        print("程式已正常關閉，資源已釋放。")


if __name__ == '__main__':
    main()