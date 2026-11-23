import os
import platform
import sys
import argparse

# 針對 macOS Apple Silicon (MPS)：若遇到不支援的算子自動回退到 CPU，避免程式崩潰
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

import cv2
import torch


def parse_arguments():
    """解析命令列參數"""
    parser = argparse.ArgumentParser(description="YOLOv5 Multi-Platform Video/Webcam Live Detection")
    parser.add_argument(
        '-m', '--weights',
        type=str,
        default='yolov5s',
        help='指定 YOLOv5 權重檔路徑 (例如: yolov5s 或 best.pt)'
    )
    parser.add_argument(
        '-f', '--file',
        type=str,
        default=None,
        help='指定輸入的影片檔案路徑 (例如: test.mp4)，若不指定則預設使用攝影機'
    )
    parser.add_argument(
        '-w', '--width',
        type=int,
        default=None,
        help='指定顯示畫面的寬度 (像素)，高度將自動等比例縮放 (例如: 800)'
    )
    return parser.parse_args()


def load_yolo_model(weights_path, device):
    """載入 YOLOv5 模型並移動至指定裝置"""
    print(f"正在載入模型，來源: {weights_path} ...")
    try:
        if weights_path.endswith('.pt'):
            model = torch.hub.load('ultralytics/yolov5', 'custom', path=weights_path, force_reload=False)
        else:
            model = torch.hub.load('ultralytics/yolov5', weights_path, pretrained=True)

        model.to(device)
        model.eval()       # 評估模式
        model.conf = 0.4   # 信心水準閾值
        return model
    except Exception as e:
        print(f"載入模型失敗: {e}")
        sys.exit(1)


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

    # 2. 自動判斷最佳硬體加速裝置 (支援 NVIDIA CUDA、Apple Silicon MPS、或 CPU)
    if torch.cuda.is_available():
        device = torch.device('cuda')
        print("使用中裝置: NVIDIA CUDA (GPU)")
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        device = torch.device('mps')
        print("使用中裝置: Apple Silicon MPS (Mac GPU)")
    else:
        device = torch.device('cpu')
        print("警告：未偵測到硬體加速，將會使用 CPU 執行（速度會比較慢）。")

    # 3. 載入模型
    model = load_yolo_model(args.weights, device)

    # 4. 開啟輸入來源 (若有指定 -f 則讀取影片檔案，否則開啟內建攝影機 0)
    is_mac = platform.system() == 'Darwin'

    if args.file:
        if not os.path.exists(args.file):
            print(f"錯誤：找不到指定的影片檔案 '{args.file}'")
            sys.exit(1)
        cap = cv2.VideoCapture(args.file)
        window_title = f"YOLOv5 Detection - {os.path.basename(args.file)}"
        source_desc = f"影片檔案 ({args.file})"
    else:
        # macOS 指定 AVFoundation 後端可避免攝影機開啟失敗
        if is_mac:
            cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
        else:
            cap = cv2.VideoCapture(0)
        window_title = "YOLOv5 Multi-Platform Detection"
        source_desc = "攝影機"

    if not cap.isOpened():
        print(f"錯誤：無法開啟{source_desc}。")
        if is_mac and not args.file:
            print("提示：請確認已在 macOS「系統設定 > 隱私權與安全性 > 相機」中允許終端機或 IDE 存取相機。")
        sys.exit(1)

    print(f"已成功開啟{source_desc}，按 'q' 鍵即可退出程式。")

    # 5. 即時串流/影片偵測主迴圈
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                if args.file:
                    print("影片播放完畢。")
                else:
                    print("無法讀取視訊畫面。")
                break

            # 進行推論
            results = model(frame)

            # 取得繪製好偵測框的畫面
            rendered_frame = results.render()[0]

            # 若有指定 -w，則依寬度等比例縮放顯示畫面
            if args.width:
                rendered_frame = resize_by_width(rendered_frame, args.width)

            # 顯示即時畫面
            cv2.imshow(window_title, rendered_frame)

            # 影片檔案播放時加入適當的延遲，即時攝影機 1ms 即可
            wait_time = 1 if args.file is None else 25
            if cv2.waitKey(wait_time) & 0xFF == ord('q'):
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