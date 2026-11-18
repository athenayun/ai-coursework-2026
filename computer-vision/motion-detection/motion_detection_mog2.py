import cv2
import numpy as np

def main():
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("錯誤：無法開啟攝影機。")
        return

    # varThreshold 設為 100 降低光線敏感度
    backSub = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=100, detectShadows=False)

    print("開始移動偵測。請按「任意鍵」離開視窗...")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("無法讀取畫面。")
            break

        # 1. 影像前處理 (高斯模糊抗噪)
        blurred_frame = cv2.GaussianBlur(frame, (21, 21), 0)

        # 2. 取得前景遮罩並二值化
        fg_mask = backSub.apply(blurred_frame)
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        # 3. 形態學運算 (開運算去雜訊，膨脹連通區塊)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        fg_mask = cv2.dilate(fg_mask, kernel, iterations=5)

        # 4. 尋找輪廓
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 初始化全局邊界框的極值
        min_x, min_y = frame.shape[1], frame.shape[0]
        max_x, max_y = 0, 0
        motion_found = False

        for contour in contours:
            # 面積過濾：忽略小於 2000 的微小晃動
            if cv2.contourArea(contour) < 2000:
                continue

            # 只要有符合條件的輪廓，就更新全局邊界框
            motion_found = True
            x, y, w, h = cv2.boundingRect(contour)
            
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x + w)
            max_y = max(max_y, y + h)

        # 5. 如果有偵測到有效移動，畫出一個統一的大框
        if motion_found:
            cv2.rectangle(frame, (min_x, min_y), (max_x, max_y), (0, 0, 255), 2)
            cv2.putText(
                frame, 
                "Motion Detected", 
                (min_x, min_y - 10), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.8, 
                (0, 0, 255), 
                2
            )

        # 顯示畫面
        cv2.imshow('Motion Detection', frame)
        cv2.imshow('Clean Mask', fg_mask)

        # ==========================================
        # 只要 cv2.waitKey 回傳不是 -1，就代表按下了任意鍵
        # ==========================================
        if cv2.waitKey(30) != -1:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()