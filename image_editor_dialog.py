import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QMessageBox, QSlider
)
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtCore import Qt, QRect

from image_utils import numpy_bgr_to_qimage, numpy_gray_to_qimage, numpy_bgra_to_qimage


class SelectableLabel(QLabel):

    """
    마우스로 드래그해서 영역(사각형)을 선택할 수 있는 라벨
    - selection_rect: 라벨 좌표계 기준 선택된 QRect
    - 이미지가 축소되어 들어오기 때문에
      실제 이미지 좌표로 매핑하기 위한 변수
    """
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setMouseTracking(True)
        self.selecting = False
        self.start_pos = None
        self.end_pos = None
        self.selection_rect = None

        # 이미지 표시 관련 정보
        self.img_scale = 1.0
        self.img_offset_x = 0
        self.img_offset_y = 0
        self.img_width = 0
        self.img_height = 0

    def set_image_transform(self, scale, offset_x, offset_y, img_w, img_h):
        self.img_scale = scale
        self.img_offset_x = offset_x
        self.img_offset_y = offset_y
        self.img_width = img_w
        self.img_height = img_h

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selecting = True
            self.start_pos = event.pos()
            self.end_pos = event.pos()
            self.selection_rect = QRect(self.start_pos, self.end_pos)
            self.update()

    def mouseMoveEvent(self, event):
        if self.selecting:
            self.end_pos = event.pos()
            self.selection_rect = QRect(self.start_pos, self.end_pos).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.selecting:
            self.selecting = False
            self.end_pos = event.pos()
            self.selection_rect = QRect(self.start_pos, self.end_pos).normalized()
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.selection_rect is not None:
            painter = QPainter(self)
            painter.setPen(QColor(0, 255, 0))
            painter.drawRect(self.selection_rect)
            painter.end()


class ImageEditorDialog(QDialog):

    """
    이미지 편집 윈도우
    - 이미지 파일 불러오기
    - canny 외곽선
    - 외곽선 색상 선택 - 슬라이더 사용
    - 드래그로 선택한 영역만 잘라서 메인 캔버스로 보내기
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("이미지 실루엣 추출")
        self.resize(800, 600)

        self.original_img = None   # BGR (numpy)
        self.edges = None          # GRAY (numpy)
        self.colored_edge_rgba = None  # BGRA (numpy)
        self.result_qimage = None  # 메인 윈도우로 넘길 최종 QImage

        main_layout = QVBoxLayout()

        # 이미지 표시 라벨 - 드래그
        self.image_label = SelectableLabel("이미지를 불러오세요.")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(
            "background-color: #333; color: #fff; font-size: 14px;"
        )
        main_layout.addWidget(self.image_label, stretch=1)

        # 버튼 영역
        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("이미지 열기")
        self.btn_extract = QPushButton("외곽선 추출 (Canny)")
        self.btn_send = QPushButton("메인 캔버스로 보내기")
        self.btn_close = QPushButton("닫기")

        self.btn_extract.setEnabled(False)
        self.btn_send.setEnabled(False)

        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_extract)
        btn_layout.addWidget(self.btn_send)
        btn_layout.addWidget(self.btn_close)

        main_layout.addLayout(btn_layout)

        # 색상 슬라이더 (R, G, B)
        slider_layout = QHBoxLayout()
        self.slider_r = QSlider(Qt.Horizontal)
        self.slider_g = QSlider(Qt.Horizontal)
        self.slider_b = QSlider(Qt.Horizontal)

        for s in (self.slider_r, self.slider_g, self.slider_b):
            s.setRange(0, 255)
            s.setEnabled(False)

        # 기본값은 흰색 외곽선
        self.slider_r.setValue(255)
        self.slider_g.setValue(255)
        self.slider_b.setValue(255)

        slider_layout.addWidget(QLabel("R"))
        slider_layout.addWidget(self.slider_r)
        slider_layout.addWidget(QLabel("G"))
        slider_layout.addWidget(self.slider_g)
        slider_layout.addWidget(QLabel("B"))
        slider_layout.addWidget(self.slider_b)

        main_layout.addLayout(slider_layout)

        self.setLayout(main_layout)

        # 연결
        self.btn_load.clicked.connect(self.on_load_image)
        self.btn_extract.clicked.connect(self.on_extract_edges)
        self.btn_send.clicked.connect(self.on_send_to_main)
        self.btn_close.clicked.connect(self.reject)

        self.slider_r.valueChanged.connect(self.on_color_changed)
        self.slider_g.valueChanged.connect(self.on_color_changed)
        self.slider_b.valueChanged.connect(self.on_color_changed)

    # 이미지 표시 관련

    def set_image_to_label(self, qimg):
        """
        QImage를 QPixmap으로 변환, 라벨 크기에 맞게 출력
        """
        label_w = self.image_label.width()
        label_h = self.image_label.height()
        img_w = qimg.width()
        img_h = qimg.height()

        if img_w == 0 or img_h == 0:
            return

        scale = min(label_w / img_w, label_h / img_h)
        disp_w = int(img_w * scale)
        disp_h = int(img_h * scale)

        offset_x = (label_w - disp_w) // 2
        offset_y = (label_h - disp_h) // 2

        pix = QPixmap.fromImage(qimg).scaled(
            disp_w,
            disp_h,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_label.setPixmap(pix)
        self.image_label.setAlignment(Qt.AlignCenter)

        # 라벨에 이미지 변환 정보 저장
        self.image_label.set_image_transform(
            scale, offset_x, offset_y, img_w, img_h
        )
        # 선택 영역 초기화
        self.image_label.selection_rect = None
        self.image_label.update()

    # 이미지 선택

    def on_load_image(self):
        """
        이미지 선택 후 표시
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "이미지 선택",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path:
            return

        img = cv2.imread(file_path)
        if img is None:
            QMessageBox.warning(self, "오류", "이미지를 불러올 수 없습니다.")
            return

        self.original_img = img
        self.edges = None
        self.colored_edge_rgba = None
        self.result_qimage = None

        qimg = numpy_bgr_to_qimage(img)
        self.set_image_to_label(qimg)

        self.btn_extract.setEnabled(True)
        self.btn_send.setEnabled(False)

        for s in (self.slider_r, self.slider_g, self.slider_b):
            s.setEnabled(False)

    # canny 외곽선 추출

    def on_extract_edges(self):
        """
        canny 외곽선 추출 후 결과를 그레이스케일 기반으로 표시 / 색상 슬라이더 활성화
        """
        if self.original_img is None:
            QMessageBox.information(self, "알림", "먼저 이미지를 불러오세요.")
            return

        gray = cv2.cvtColor(self.original_img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        # canny 외곽선 검출하기
        self.edges = cv2.Canny(gray, 100, 200)

        # 초기 색상(슬라이더 값)에 맞춰 한 번 칠해서 표시
        self.apply_color_to_edges()

        self.btn_send.setEnabled(True)
        for s in (self.slider_r, self.slider_g, self.slider_b):
            s.setEnabled(True)

    def apply_color_to_edges(self):
        """
        self.edges(0/255)와 슬라이더의 R,G,B 값으로
        BGRA 이미지 생성 후 라벨에 표시
        """
        if self.edges is None:
            return

        h, w = self.edges.shape
        bgra = np.zeros((h, w, 4), dtype=np.uint8)

        mask = self.edges != 0
        r = self.slider_r.value()
        g = self.slider_g.value()
        b = self.slider_b.value()

        bgra[mask, 0] = b
        bgra[mask, 1] = g
        bgra[mask, 2] = r
        bgra[mask, 3] = 255

        self.colored_edge_rgba = bgra
        qimg = numpy_bgra_to_qimage(bgra)
        self.set_image_to_label(qimg)

        # 메인으로 보낼 기본 결과(선택 안 했을 때 대비)
        self.result_qimage = qimg

    def on_color_changed(self, value):
        """
        색상 슬라이더 변경 시 외곽선을 다시 칠함
        """
        if self.edges is None:
            return
        self.apply_color_to_edges()

    # 선택 영역 잘라내기

    def crop_edges_by_selection(self):
        """
        드래그로 선택한 영역을 self.edges 기준으로 잘라서 반환
        - 선택 영역이 없으면 전체 edges 사용
        """
        if self.edges is None:
            return None

        h, w = self.edges.shape

        sel = self.image_label.selection_rect
        if sel is None:
            # 드래그 안 했으면 전체 사용
            return self.edges.copy()

        scale = self.image_label.img_scale
        off_x = self.image_label.img_offset_x
        off_y = self.image_label.img_offset_y

        # 라벨 기준 좌표 → 이미지 기준 좌표
        x1 = sel.left() - off_x
        y1 = sel.top() - off_y
        x2 = sel.right() - off_x
        y2 = sel.bottom() - off_y

        x1_img = int(x1 / scale)
        y1_img = int(y1 / scale)
        x2_img = int(x2 / scale)
        y2_img = int(y2 / scale)

        # 이미지 범위 안으로 클램핑
        x1_img = max(0, min(w - 1, x1_img))
        y1_img = max(0, min(h - 1, y1_img))
        x2_img = max(0, min(w, x2_img))
        y2_img = max(0, min(h, y2_img))

        if x2_img <= x1_img or y2_img <= y1_img:
            # 영역이 너무 작거나 잘못된 경우는 그냥 전체를 사용
            return self.edges.copy()

        cropped = self.edges[y1_img:y2_img, x1_img:x2_img]
        return cropped

    # 메인 캔버스로 보내기

    def on_send_to_main(self):
        """
        드래그로 선택한 영역만 잘라서 (없으면 전체)
        색상 슬라이더 기준의 R,G,B로 칠한
        투명 배경 RGBA QImage를 만들어 result_qimage에 담아 accept()
        """
        if self.edges is None:
            QMessageBox.information(self, "알림", "먼저 외곽선을 추출해주세요.")
            return

        cropped_edges = self.crop_edges_by_selection()
        if cropped_edges is None:
            QMessageBox.warning(self, "오류", "잘라낼 수 있는 영역이 없습니다.")
            return

        h, w = cropped_edges.shape
        bgra = np.zeros((h, w, 4), dtype=np.uint8)

        mask = cropped_edges != 0
        r = self.slider_r.value()
        g = self.slider_g.value()
        b = self.slider_b.value()

        bgra[mask, 0] = b
        bgra[mask, 1] = g
        bgra[mask, 2] = r
        bgra[mask, 3] = 255

        self.result_qimage = numpy_bgra_to_qimage(bgra)
        self.accept()