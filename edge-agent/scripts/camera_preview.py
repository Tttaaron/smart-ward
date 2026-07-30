"""摄像头实时预览（第一步验证）

用途：确认宿主机摄像头能正常打开并取到画面。
运行：python scripts/camera_preview.py
按 q 退出。
"""

import sys
import cv2


def main():
    # 尝试打开摄像头（0=默认摄像头，可通过 --camera 1 指定）
    camera_index = int(sys.argv[sys.argv.index("--camera") + 1]) if "--camera" in sys.argv else 0
    print(f"[预览] 正在打开摄像头 index={camera_index} ...")

    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"[错误] 无法打开摄像头 index={camera_index}，请检查设备或尝试其他索引")
        sys.exit(1)

    # 打印摄像头实际分辨率
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[预览] 摄像头已打开，分辨率 {width}x{height}")

    print("[预览] 预览窗口已启动，按 q 退出")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[错误] 读取画面失败")
            break

        # 在画面左上角标注状态
        cv2.putText(frame, "LIVE PREVIEW  (press q to quit)", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        cv2.imshow("Smart Ward - Camera Preview", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("[预览] 已退出")


if __name__ == "__main__":
    main()
