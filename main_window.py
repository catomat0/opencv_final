from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QMessageBox, QSlider, QFileDialog
)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QColor
from PyQt5.QtCore import Qt, QPoint

from image_editor_dialog import ImageEditorDialog


class DraggableCanvasLabel(QLabel):
    """
    메인 캔버스 미리보기
    - 마우스 이벤트를 받아서 main window 에 넘겨줌
    - 실제 드래그 로직은 main window가 처리
    """
    def __init__(self, parent=None):

        super().__init__(parent)
        self.main_window = None
        self.setMouseTracking(True)

    def set_main_window(self, main_window):

        self.main_window = main_window

    def mousePressEvent(self, event):

        if self.main_window is not None:
            self.main_window.on_canvas_mouse_press(event)

    def mouseMoveEvent(self, event):

        if self.main_window is not None:
            self.main_window.on_canvas_mouse_move(event)

    def mouseReleaseEvent(self, event):

        if self.main_window is not None:
            self.main_window.on_canvas_mouse_release(event)


class MainWindow(QMainWindow):

    """
    메인 화면:
    - 배경화면 사이즈 선택
    - 이미지 QImage 받아오기
    - 받은 외곽선 이미지들을 캔버스에 배치
    - 배경 색 슬라이더로 배경 조절
    - 마우스로 이미지를 드래그해서 위치 수정
    - 최종 결과물을 이미지 파일로 저장
    """
    def __init__(self):

        super().__init__()

        self.setWindowTitle("외곽선 콜라주 배경화면 생성")
        self.resize(1000, 700)

        # 캔버스
        self.canvas_width = 0
        self.canvas_height = 0
        self.current_canvas_qimage = None  # 실제로 비춰지는 해상도 캔버스
        self.image_placement_locked = False

        # 배치
        # placed_images: (QImage, x, y, w, h)
        self.placed_images = []
        self.next_x = 0
        self.next_y = 0
        self.current_row_height = 0

        # 미리보기에서 캔버스 좌표로 변환하기 위한 정보
        self.preview_scale = 1.0
        self.preview_offset_x = 0
        self.preview_offset_y = 0

        # 드래그 중 선택된 이미지의 정보
        self.dragging_index = None
        self.drag_offset_in_image = QPoint(0, 0)  # 이미지 내부에서의 클릭 위치

        # UI
        central_widget = QWidget()
        main_layout = QVBoxLayout()

        # 상단 - 배경화면 사이즈 선택
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("배경화면 사이즈 선택:"))

        sizes = [
            ("Desktop 1920x1080", 1920, 1080),
            ("Desktop 2560x1440", 2560, 1440),
            ("Desktop 3840x2160", 3840, 2160),
            ("Mobile 1080x1920", 1080, 1920),
            ("Mobile 1170x2532", 1170, 2532),
            ("Mobile 1440x3040", 1440, 3040),
        ]

        for label, w, h in sizes:
            btn = QPushButton(label)
            btn.clicked.connect(
                lambda checked, w=w, h=h: self.set_canvas_size(w, h)
            )
            size_layout.addWidget(btn)

        main_layout.addLayout(size_layout)

        # 메인 캔버스
        self.canvas_label = DraggableCanvasLabel()
        self.canvas_label.set_main_window(self)
        self.canvas_label.setText("배경화면 사이즈를 선택하세요!")
        self.canvas_label.setAlignment(Qt.AlignCenter)
        self.canvas_label.setStyleSheet(
            "background-color: #222; color: #fff; font-size: 16px;"
        )
        main_layout.addWidget(self.canvas_label, stretch=1)

        # 하단 버튼 - 이미지 추가 / 완료 / 저장
        bottom_layout = QHBoxLayout()
        self.btn_add_image = QPushButton("이미지 추가하기")
        self.btn_finish_or_bg = QPushButton("이미지 추가 완료 -> 배경색 설정 모드로")
        self.btn_save = QPushButton("이미지 저장하기")

        self.btn_add_image.setEnabled(False)
        self.btn_finish_or_bg.setEnabled(False)
        self.btn_save.setEnabled(False)

        bottom_layout.addWidget(self.btn_add_image)
        bottom_layout.addWidget(self.btn_finish_or_bg)
        bottom_layout.addWidget(self.btn_save)

        main_layout.addLayout(bottom_layout)

        # 배경색 조절 슬라이더
        bg_slider_layout = QHBoxLayout()
        self.bg_slider_r = QSlider(Qt.Horizontal)
        self.bg_slider_g = QSlider(Qt.Horizontal)
        self.bg_slider_b = QSlider(Qt.Horizontal)

        for s in (self.bg_slider_r, self.bg_slider_g, self.bg_slider_b):
            s.setRange(0, 255)
            s.setValue(0)
            s.setEnabled(False)

        bg_slider_layout.addWidget(QLabel("배경 R"))
        bg_slider_layout.addWidget(self.bg_slider_r)
        bg_slider_layout.addWidget(QLabel("G"))
        bg_slider_layout.addWidget(self.bg_slider_g)
        bg_slider_layout.addWidget(QLabel("B"))
        bg_slider_layout.addWidget(self.bg_slider_b)

        main_layout.addLayout(bg_slider_layout)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.btn_add_image.clicked.connect(self.on_add_image)
        self.btn_finish_or_bg.clicked.connect(self.on_finish_or_bg_clicked)
        self.btn_save.clicked.connect(self.on_save)

        self.bg_slider_r.valueChanged.connect(self.on_bg_color_changed)
        self.bg_slider_g.valueChanged.connect(self.on_bg_color_changed)
        self.bg_slider_b.valueChanged.connect(self.on_bg_color_changed)

    # 캔버스

    def set_canvas_size(self, w, h):
        """
        스타트 캔버스(배경화면) 사이즈 설정
        """
        self.canvas_width = w
        self.canvas_height = h
        self.reset_canvas_state()

        self.canvas_label.setText(
            f"선택된 배경화면 사이즈: {w} x {h}\n"
            f"이미지를 추가하여 콜라주를 만들 수 있습니다."
        )
        self.btn_add_image.setEnabled(True)
        self.btn_finish_or_bg.setEnabled(True)
        self.btn_save.setEnabled(True)

        self.update_canvas_preview()

    def reset_canvas_state(self):
        """
        캔버스를 초기 상태로 리셋
        """
        self.placed_images.clear()
        self.next_x = 0
        self.next_y = 0
        self.current_row_height = 0
        self.image_placement_locked = False
        self.current_canvas_qimage = None

        self.preview_scale = 1.0
        self.preview_offset_x = 0
        self.preview_offset_y = 0
        self.dragging_index = None

        self.btn_finish_or_bg.setText("이미지 추가 완료 -> 배경색 설정 모드로")
        self.btn_add_image.setEnabled(False)

        for s in (self.bg_slider_r, self.bg_slider_g, self.bg_slider_b):
            s.setValue(0)
            s.setEnabled(False)

    def update_canvas_preview(self):
        """
        현재 배경색 + 배치된 외곽선 이미지를 올린 캔버스를 생성하고 중앙에서 축소해서 미리보기로 보여줌
        + 축소 비율 / 오프셋을 저장해서 마우스 좌표를 캔버스 좌표로 변환할 수 있게 함
        """
        if self.canvas_width <= 0 or self.canvas_height <= 0:
            return

        # 실제 캔버스(QImage) 생성
        canvas_qimage = QImage(
            self.canvas_width,
            self.canvas_height,
            QImage.Format_RGB888
        )

        r = self.bg_slider_r.value()
        g = self.bg_slider_g.value()
        b = self.bg_slider_b.value()
        canvas_qimage.fill(QColor(r, g, b))

        painter = QPainter(canvas_qimage)
        for img, x, y, w, h in self.placed_images:
            pix = QPixmap.fromImage(img).scaled(
                w, h,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            painter.drawPixmap(x, y, pix)

        painter.end()

        self.current_canvas_qimage = canvas_qimage

        # 미리보기용 사이즈 계산
        label_w = self.canvas_label.width()
        label_h = self.canvas_label.height()
        if label_w <= 0 or label_h <= 0:
            return

        scale = min(label_w / self.canvas_width, label_h / self.canvas_height)
        disp_w = int(self.canvas_width * scale)
        disp_h = int(self.canvas_height * scale)
        offset_x = (label_w - disp_w) // 2
        offset_y = (label_h - disp_h) // 2

        self.preview_scale = scale
        self.preview_offset_x = offset_x
        self.preview_offset_y = offset_y

        display_pix = QPixmap.fromImage(canvas_qimage).scaled(
            disp_w,
            disp_h,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # 배경은 그대로 두고 offset 위치에만 그림을 그릴 수는 없으니, 여기서는 그냥 scaled pixmap만 설정
        self.canvas_label.setPixmap(display_pix)
        self.canvas_label.setAlignment(Qt.AlignCenter)

    # 좌표 변환

    def label_pos_to_canvas_pos(self, pos: QPoint):
        """
        라벨 좌표(pos)를 실제 캔버스 좌표로 변환
        (preview_scale, preview_offset_x/y 사용)
        """
        x = (pos.x() - self.preview_offset_x) / self.preview_scale
        y = (pos.y() - self.preview_offset_y) / self.preview_scale
        return int(x), int(y)

    # 이미지 추가

    def on_add_image(self):
        """
        외곽선 이미지 QImage(RGBA)를 메인 캔버스에 배치
        """
        if self.image_placement_locked:
            QMessageBox.information(
                self, "알림", "이미지 추가 완료 후에는 더 이상 이미지를 추가할 수 없습니다."
            )
            return

        if self.canvas_width == 0 or self.canvas_height == 0:
            QMessageBox.information(
                self, "알림", "먼저 배경화면 사이즈를 선택해주세요."
            )
            return

        dialog = ImageEditorDialog(self)

        from PyQt5.QtWidgets import QDialog  # 여기서 import 해줘도 됨

        if dialog.exec_() == QDialog.Accepted:
            result_qimage = dialog.result_qimage
            if result_qimage is None:
                return
            self.place_image_on_canvas(result_qimage)
            self.update_canvas_preview()

    def place_image_on_canvas(self, qimage_rgba: QImage):
        """
        QImage를 캔버스에 배치
        """
        img_w = qimage_rgba.width()
        img_h = qimage_rgba.height()

        if img_w <= 0 or img_h <= 0:
            return

        # 너무 크면 캔버스 가로 1/3 정도로 축소
        max_tile_width = max(1, self.canvas_width // 3)
        scale_factor = 1.0
        if img_w > max_tile_width:
            scale_factor = max_tile_width / img_w
            img_w = int(img_w * scale_factor)
            img_h = int(img_h * scale_factor)

        # 가로 초과 시 줄바꿈
        if self.next_x + img_w > self.canvas_width:
            self.next_x = 0
            self.next_y += self.current_row_height
            self.current_row_height = 0

        # 세로 초과 시 배치 불가
        if self.next_y + img_h > self.canvas_height:
            QMessageBox.warning(
                self, "경고", "캔버스에 이미지를 배치할 공간이 부족합니다."
            )
            return

        self.placed_images.append((qimage_rgba, self.next_x, self.next_y, img_w, img_h))
        self.next_x += img_w
        self.current_row_height = max(self.current_row_height, img_h)

    # 이미지 추가 완료 / 배경색 모드

    def on_finish_or_bg_clicked(self):
        """
        처음 클릭: 이미지 추가를 마치고 배경색 조절 모드로 전환
        """
        if not self.image_placement_locked:
            self.image_placement_locked = True
            self.btn_add_image.setEnabled(False)

            for s in (self.bg_slider_r, self.bg_slider_g, self.bg_slider_b):
                s.setEnabled(True)

            self.btn_finish_or_bg.setText("배경색을 슬라이더로 조절할 수 있습니다.")
            QMessageBox.information(
                self, "알림",
                "이제 배경색 슬라이더를 이용해 배경색을 변경할 수 있습니다.\n"
                "이미지 추가는 더 이상 할 수 없습니다."
            )
        else:
            QMessageBox.information(
                self, "알림", "이미 배경색 설정 모드입니다. 슬라이더를 조절하세요."
            )

    def on_bg_color_changed(self, value):
        """
        배경색 슬라이더 값 변경 - 캔버스 갱신
        """
        if self.canvas_width > 0 and self.canvas_height > 0:
            self.update_canvas_preview()

    # 마우스 드래그로 이미지 이동

    def find_image_at_canvas_pos(self, x, y):
        """
        캔버스 좌표 (x, y)에서 가장 위에 있는 이미지를 찾음
        - placed_images 리스트의 마지막 항목이 위에 있다고 가정
        """
        for i in range(len(self.placed_images) - 1, -1, -1):
            img, ix, iy, iw, ih = self.placed_images[i]
            if ix <= x <= ix + iw and iy <= y <= iy + ih:
                return i
        return None

    def on_canvas_mouse_press(self, event):
        """
        드래그 시작: 클릭한 위치에 이미지가 있으면 그 이미지를 선택
        """
        if event.button() != Qt.LeftButton:
            return

        if self.canvas_width <= 0 or self.canvas_height <= 0:
            return

        # 라벨 좌표 → 캔버스 좌표
        canvas_x, canvas_y = self.label_pos_to_canvas_pos(event.pos())

        idx = self.find_image_at_canvas_pos(canvas_x, canvas_y)
        if idx is None:
            self.dragging_index = None
            return

        self.dragging_index = idx
        img, ix, iy, iw, ih = self.placed_images[idx]
        # 클릭한 지점이 이미지 내부에서 얼마만큼 떨어져 있는지 저장 (드래그 시 유지)
        self.drag_offset_in_image = QPoint(canvas_x - ix, canvas_y - iy)

    def on_canvas_mouse_move(self, event):
        """
        드래그 중 - 선택된 이미지가 있으면 마우스 위치에 따라 이미지 이동
        """
        if self.dragging_index is None:
            return

        # 라벨 좌표 → 캔버스 좌표
        canvas_x, canvas_y = self.label_pos_to_canvas_pos(event.pos())

        # 이미지의 좌상단 좌표 = 현재 마우스 좌표 - 처음에 저장해 둔 offset
        new_x = canvas_x - self.drag_offset_in_image.x()
        new_y = canvas_y - self.drag_offset_in_image.y()

        # 캔버스 범위 내로 제한
        img, _, _, iw, ih = self.placed_images[self.dragging_index]
        new_x = max(0, min(self.canvas_width - iw, new_x))
        new_y = max(0, min(self.canvas_height - ih, new_y))

        # 튜플 갱신
        self.placed_images[self.dragging_index] = (img, new_x, new_y, iw, ih)
        self.update_canvas_preview()

    def on_canvas_mouse_release(self, event):
        """
        드래그 종료
        """
        if event.button() == Qt.LeftButton:
            self.dragging_index = None

    # 최종 결과 저장

    def on_save(self):
        """
        현재 캔버스를 이미지 파일로 저장
        """
        if self.current_canvas_qimage is None:
            QMessageBox.information(self, "알림", "저장할 이미지가 없습니다.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "저장할 파일 이름",
            "",
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg)"
        )
        if not file_path:
            return

        if self.current_canvas_qimage.save(file_path):
            QMessageBox.information(self, "완료", "이미지가 성공적으로 저장되었습니다.")
        else:
            QMessageBox.warning(self, "오류", "이미지 저장에 실패했습니다.")
