import cv2
import numpy as np
from PyQt5.QtGui import QImage

"""
OpenCV BGR -> Qt RGB 변환
"""
def numpy_bgr_to_qimage(img_bgr: np.ndarray) -> QImage:

    h, w, ch = img_bgr.shape
    bytes_per_line = ch * w
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    return QImage(
        img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888
    ).copy()


"""
단일 채널 그레이스케일 이미지를 QImage로 변환
PyQt에서의 표시를 위해 RGB로 확장
"""
def numpy_gray_to_qimage(img_gray: np.ndarray) -> QImage:

    h, w = img_gray.shape
    # GRAY -> RGB 변환
    img_rgb = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2RGB)
    bytes_per_line = 3 * w
    return QImage(
        img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888
    ).copy()


"""
BGRA(OpenCV) -> Qt RGBA 변환
"""
def numpy_bgra_to_qimage(img_bgra: np.ndarray) -> QImage:

    h, w, ch = img_bgra.shape
    assert ch == 4
    bytes_per_line = ch * w

    img_rgba = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2RGBA)

    return QImage(
        img_rgba.data, w, h, bytes_per_line, QImage.Format_RGBA8888
    ).copy()
