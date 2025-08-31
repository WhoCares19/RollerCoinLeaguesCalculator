import sys
import re
import numpy as np
import traceback
import gc
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit,
    QPushButton, QHBoxLayout, QVBoxLayout, QMessageBox, QComboBox, QSizePolicy, QGridLayout, QStackedLayout
)
from PyQt5.QtGui import QPixmap, QImage, QDragEnterEvent, QDropEvent, QStandardItemModel, QStandardItem, QMovie
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QMimeData, QThread

from PIL import Image, ImageOps, ImageEnhance, ImageFilter

import os
# Set PADDLEX_HOME globally as per your provided context
os.environ['PADDLEX_HOME'] = r"C:\Users\VvV\Desktop\python code\Rollercoin Calculator"

from paddleocr import PaddleOCR

# Removed the global 'ocr' instance and 'OCR loaded successfully!' print,
# as the reader will now be initialized within ImageAnalyzerWidget.

try:
    from Leagues_Info import (
        TIER_CRYPTO_MAPPING,
        UNIT_MULTIPLIERS,
        TIER_POWER_RANGES,
        convert_power_to_ghs,
        determine_tier_from_power
    )
except ImportError:
    TIER_CRYPTO_MAPPING = {"Bronze I": ["RLT", "RST", "BTC", "LTC"]}
    UNIT_MULTIPLIERS = {"Gh/s": 1, "Th/s": 1e3, "Ph/s": 1e6, "Eh/s": 1e9, "Zh/s": 1e12}
    TIER_POWER_RANGES = {
        "Bronze I": (0, 1e9),
        "Silver I": (1e9, 10e9)
    }
    def convert_power_to_ghs(value_str, unit, multipliers):
        try:
            value = float(value_str.replace(',', ''))
            return value * multipliers.get(unit, 1)
        except ValueError:
            return 0.0
    def determine_tier_from_power(power_ghs, power_ranges):
        for tier, (min_power, max_power) in TIER_POWER_RANGES.items():
            if min_power <= power_ghs < max_power:
                return tier
        return list(power_ranges.keys())[0] if power_ranges else "Bronze I"

from Value_Paste import ValuePasteWidget

class ClickToFocusLineEdit(QLineEdit):
    """
    A QLineEdit subclass that selects all text when it gains focus via a mouse click.
    It uses Qt.ClickFocus so it can be interacted with only by clicking (not tabbed to automatically).
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.ClickFocus) # MODIFIED: Set to ClickFocus

    def mousePressEvent(self, event):
        self.selectAll()
        super().mousePressEvent(event)

class PasteBoxContainer(QWidget):
    """
    A QWidget subclass that acts as a visual container for the image placeholder.
    It should not have focus by default or pass it, as it's primarily a display container.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet("border: 1px solid #40444b; background-color: #2f3136;")

    def focusInEvent(self, event):
        self.setStyleSheet("border: 2px solid #7289da; background-color: #2f3136;")
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.setStyleSheet("border: 1px solid #40444b; background-color: #2f3136;")
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() and any(url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')) for url in event.mimeData().urls()):
            event.acceptProposedAction()
            self.setStyleSheet("border: 2px solid #a0c4ff; background-color: #2f3136;")
        else:
            event.ignore()
        super().dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("border: 1px solid #40444b; background-color: #2f3136;")
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("border: 1px solid #40444b; background-color: #2f3136;")
        self.parent()._handle_drop_event_for_image_placeholder(event)
        super().dropEvent(event)

class AnalysisWorker(QThread):
    analysis_finished = pyqtSignal(dict, str, str)
    loading_status_changed = pyqtSignal(str)

    def __init__(self, pil_image, user_power_str, known_tickers, selected_tier, ocr_reader, apply_preprocessing=True):
        super().__init__()
        self.pil_image = pil_image
        self.user_power_str = user_power_str
        self.known_tickers = known_tickers
        self.selected_tier = selected_tier
        self.reader = ocr_reader
        self.apply_preprocessing = apply_preprocessing

    def run(self):
        self.loading_status_changed.emit("Performing OCR...")

        detected_values = {}
        try:
            # The reader is now passed in and should already be initialized
            if self.reader is None:
                # This fallback should ideally not be hit if initialized correctly in ImageAnalyzerWidget
                self.reader = PaddleOCR(use_angle_cls=True, lang='en')

            processed_pil_image = self.pil_image.copy()

            if self.apply_preprocessing:
                processed_pil_image = processed_pil_image.convert("L")
                enhancer = ImageEnhance.Contrast(processed_pil_image)
                processed_pil_image = enhancer.enhance(1.5)
                MIN_OCR_WIDTH = 1000
                if processed_pil_image.width < MIN_OCR_WIDTH:
                    upscale_factor = MIN_OCR_WIDTH / processed_pil_image.width
                    processed_pil_image = processed_pil_image.resize(
                        (int(processed_pil_image.width * upscale_factor), int(processed_pil_image.height * upscale_factor)),
                        Image.LANCZOS
                    )
                processed_pil_image = processed_pil_image.filter(ImageFilter.MedianFilter(3))
                processed_pil_image = processed_pil_image.convert("RGB")
            else:
                processed_pil_image = self.pil_image.convert("RGB")

            img_np_array = np.array(processed_pil_image)
            del processed_pil_image
            gc.collect()

            ocr_results = self.reader.ocr(img_np_array)
            del img_np_array
            gc.collect()

            self.loading_status_changed.emit("Processing OCR results...")
            processed_ocr_data = self._process_ocr_raw_results(ocr_results)
            del ocr_results
            gc.collect()

            numbers_with_units = self._extract_numbers_with_units(processed_ocr_data)
            detected_values = self._associate_tickers_with_rates(processed_ocr_data, numbers_with_units)

            self.analysis_finished.emit(detected_values, self.user_power_str, self.selected_tier)

        except Exception as e:
            traceback.print_exc()
            self.analysis_finished.emit({}, self.user_power_str, self.selected_tier)
        finally:
            pass

    def _process_ocr_raw_results(self, ocr_results):
        processed_data = []
        if ocr_results and ocr_results[0] is not None:
            if isinstance(ocr_results[0], dict):
                rec_texts = ocr_results[0].get('rec_texts', [])
                rec_scores = ocr_results[0].get('rec_scores', [])
                dt_polys = ocr_results[0].get('dt_polys', [])
            else:
                return []

            min_len = min(len(rec_texts), len(rec_scores), len(dt_polys))
            for i in range(min_len):
                text = rec_texts[i].strip()
                prob = rec_scores[i]
                bbox = dt_polys[i]

                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]

                x_min = int(min(x_coords))
                y_min = int(min(y_coords))
                x_max = int(max(x_coords))
                y_max = int(max(y_coords))

                width = x_max - x_min
                height = y_max - y_min

                if text:
                    processed_data.append({
                        'text': text,
                        'left': x_min,
                        'top': y_min,
                        'width': width,
                        'height': height,
                        'conf': prob * 100
                    })
        return processed_data

    def _extract_numbers_with_units(self, processed_ocr_data):
        numbers_with_units = []
        known_units_pattern_regex = r"(GH/S|TH/S|PH/S|EH/S|ZH/S|GHS|THS|PHS|EHS|ZHS|T|P|B|E|ES|PVS)"
        for item in processed_ocr_data:
            text = item['text'].strip()
            if not text:
                continue

            number_unit_match = re.search(r'(\d[\d,]*\.?\d*)\s*(' + known_units_pattern_regex + r')?', text, re.IGNORECASE)
            value_str = None
            unit_str = None

            if number_unit_match:
                value_str = number_unit_match.group(1).replace(',', '')
                unit_part_from_regex = number_unit_match.group(2)

                if unit_part_from_regex:
                    unit_str = unit_part_from_regex.upper()
                    if unit_str == 'T' or unit_str == 'THS': unit_str = 'Th/s'
                    elif unit_str == 'P' or unit_str == 'PVS' or unit_str == 'PHS': unit_str = 'Ph/s'
                    elif unit_str == 'E' or unit_str == 'ES' or unit_str == 'EHS': unit_str = 'Eh/s'
                    elif unit_str == 'B' or unit_str == 'ZHS': unit_str = 'Zh/s'
                    elif unit_str == 'GHS': unit_str = 'Gh/s'
                else:
                    unit_str = "Gh/s"

            if value_str:
                numbers_with_units.append({
                    'value': value_str,
                    'unit': unit_str,
                    'x_scaled': item['left'],
                    'y_scaled': item['top'],
                    'width_scaled': item['width'],
                    'height_scaled': item['height']
                })
        return numbers_with_units

    def _associate_tickers_with_rates(self, processed_ocr_data, numbers_with_units):
        detected_values = {}
        known_tickers = self.known_tickers

        def _is_similar_ticker_internal(detected_text):
            if detected_text in known_tickers:
                return detected_text

            error_mappings = {
                "RRIUT": "RLT", "RRU": "RLT", "R.RU": "RLT", "RLJ": "RLT", "RLY": "RLT",
                "RSTT": "RST", "RSTU": "RST",
                "TRXY": "TRX", "YTRX": "TRX", "TX": "TRX",
                "LIC": "LTC", "LTCC": "LTC",
                "GC": "DOGE", "DOGE.": "DOGE",
                "CC": "BTC", "BTCC": "BTC",
                "EH": "ETH", "ETTH": "ETH",
                "BNBV": "BNB", "BNN": "BNB",
                "SOLL": "SOL", "5OL": "SOL",
                "POOL": "POL", "PQOL": "POL",
                "xrp": "XRP"
            }

            if detected_text in error_mappings:
                return error_mappings[detected_text]

            for known_ticker in known_tickers:
                if len(detected_text) == len(known_ticker):
                    diff_count = sum(1 for a, b in zip(detected_text, known_ticker) if a != b)
                    if diff_count <= 1:
                        return known_ticker
                if known_ticker in detected_text and abs(len(detected_text) - len(known_ticker)) <= 2:
                    return known_ticker
                if detected_text.startswith(known_ticker) and abs(len(detected_text) - len(known_ticker)) <= 1:
                    return known_ticker
                if known_ticker.startswith(detected_text) and abs(len(known_ticker) - len(detected_text)) <= 1:
                    return known_ticker
                if detected_text.endswith(known_ticker) and abs(len(detected_text) - len(known_ticker)) <= 1:
                    return known_ticker
            return None

        for item in processed_ocr_data:
            text = item['text'].strip()
            if not text:
                continue

            processed_text = text.upper()
            matched_ticker = _is_similar_ticker_internal(processed_text)

            if matched_ticker:
                ticker_x_scaled = item['left']
                ticker_y_scaled = item['top']
                ticker_width_scaled = item['width']
                ticker_height_scaled = item['height']

                closest_rate_unit_info = None
                min_distance = float('inf')

                for num_unit_info in numbers_with_units:
                    x_distance = abs(num_unit_info['x_scaled'] - ticker_x_scaled)
                    y_distance = abs(num_unit_info['y_scaled'] - ticker_y_scaled)

                    VERTICAL_ALIGNMENT_TOLERANCE = 50
                    if y_distance > VERTICAL_ALIGNMENT_TOLERANCE:
                        continue

                    MAX_HORIZONTAL_DISTANCE = 900

                    if num_unit_info['x_scaled'] > ticker_x_scaled and x_distance < MAX_HORIZONTAL_DISTANCE:
                        current_distance = x_distance + y_distance * 5

                        if current_distance < min_distance:
                            min_distance = current_distance
                            closest_rate_unit_info = num_unit_info

                if closest_rate_unit_info:
                    if matched_ticker not in detected_values:
                        detected_values[matched_ticker] = {
                            'rate': float(closest_rate_unit_info['value']),
                            'unit': closest_rate_unit_info['unit'],
                            'icon_box': None,
                            'ticker_x': int(ticker_x_scaled / 1),
                            'ticker_y': int(ticker_y_scaled / 1),
                            'ticker_height': int(ticker_height_scaled / 1)
                        }
        return detected_values

class ImageAnalyzerWidget(QWidget):
    analysis_completed = pyqtSignal(dict, str, str)

    value_data_parsed = pyqtSignal(dict)
    value_data_cleared = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.NoFocus)
        # Initialize PaddleOCR reader once here with explicit model paths
        self.reader = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            det_model_dir=os.path.join(os.environ['PADDLEX_HOME'], "official_models", "PP-OCRv5_server_det"),
            rec_model_dir=os.path.join(os.environ['PADDLEX_HOME'], "official_models", "en_PP-OCRv5_mobile_rec"),
            cls_model_dir=os.path.join(os.environ['PADDLEX_HOME'], "official_models", "PP-LCNet_x1_0_textline_ori")
        )

        self.pasted_image = None
        self._cached_ocr_results = {}
        self.clipboard = QApplication.clipboard()
        self.setAcceptDrops(True)
        self.upscale_factor = 2

        self.known_tickers = [
            "RLT", "RST", "XRP", "TRX", "DOGE",
            "BTC", "ETH", "BNB", "POL", "SOL", "LTC"
        ]

        self.analysis_worker = None

        self._is_tier_manual_override = False
        self._setting_tier_programmatically = False

        self.analysis_debounce_timer = QTimer(self)
        self.analysis_debounce_timer.setSingleShot(True)
        self.analysis_debounce_timer.setInterval(200)
        self.analysis_debounce_timer.timeout.connect(self.analyze_image)

        self.value_paste_widget = ValuePasteWidget(known_tickers=self.known_tickers)
        self.value_paste_widget.pasted_data_parsed.connect(self.value_data_parsed.emit)
        self.value_paste_widget.data_cleared.connect(self.value_data_cleared.emit)


        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        top_input_layout = QHBoxLayout()
        self.power_input_box = ClickToFocusLineEdit()
        self.power_input_box.setPlaceholderText("Type your power (e.g., 1.807 Eh/s)")
        self.power_input_box.setFixedWidth(180)
        self.power_input_box.setAlignment(Qt.AlignCenter)
        self.power_input_box.setStyleSheet("""
            QLineEdit { background-color: #2f3136; border: 1px solid #40444b; border-radius: 3px; padding: 5px; color: white; }
        """)
        self.power_input_box.textChanged.connect(self._on_power_input_changed)

        self.global_tier_combo = QComboBox()
        self.global_tier_combo.setFocusPolicy(Qt.NoFocus)
        self.tier_options = list(TIER_CRYPTO_MAPPING.keys())
        model = QStandardItemModel()
        for option in self.tier_options:
            item = QStandardItem(option)
            item.setTextAlignment(Qt.AlignLeft)
            model.appendRow(item)
        self.global_tier_combo.setModel(model)
        self.global_tier_combo.setFixedSize(80, 25)
        self.global_tier_combo.setStyleSheet("""
            QComboBox { background-color: #2f3136; border: 1px solid #40444b; border-radius: 3px; color: white; }
            QComboBox::drop-down { border: 0px; }
            QComboBox QAbstractItemView { background-color: #2f3136; border: 1px solid #40444b; color: white; selection-background-color: #7289da; text-align: left; }
            QComboBox QLineEdit { text-align: center; padding: 0px; padding-right: 20px; }
        """)
        self.global_tier_combo.view().setTextElideMode(Qt.ElideNone)
        self.global_tier_combo.view().setFixedWidth(self.global_tier_combo.width())
        self.global_tier_combo.view().setFixedHeight(200)
        self.global_tier_combo.currentIndexChanged.connect(self._on_global_tier_combo_changed)

        top_input_layout.addStretch()
        top_input_layout.addWidget(self.power_input_box)
        top_input_layout.addWidget(self.global_tier_combo)
        top_input_layout.addStretch()
        main_layout.addLayout(top_input_layout)

        toggle_button_layout = QHBoxLayout()
        self.btn_paste_data = QPushButton("Paste Network Data")
        self.btn_paste_data.clicked.connect(self._show_data_input)
        self.btn_paste_data.setFocusPolicy(Qt.NoFocus)
        self.btn_screenshot = QPushButton("Paste Network Screenshot")
        self.btn_screenshot.clicked.connect(self._show_screenshot_input)
        self.btn_screenshot.setFocusPolicy(Qt.NoFocus)

        toggle_button_layout.addStretch()
        toggle_button_layout.addWidget(self.btn_paste_data)
        toggle_button_layout.addWidget(self.btn_screenshot)
        toggle_button_layout.addStretch()
        main_layout.addLayout(toggle_button_layout)

        # Start of new dedicated layout for title and content stack
        title_and_content_section_layout = QVBoxLayout()
        title_and_content_section_layout.setSpacing(0)
        title_and_content_section_layout.setContentsMargins(0, 0, 0, 0) # ADDED: Set content margins to 0 for this specific layout

        self.main_content_title_label = QLabel("Paste Network Screenshot")
        self.main_content_title_label.setAlignment(Qt.AlignCenter)
        self.main_content_title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: white; margin-bottom: 5px;")
        title_and_content_section_layout.addWidget(self.main_content_title_label)


        self.main_content_stack = QStackedLayout()
        self.main_content_stack.setContentsMargins(0,0,0,0)
        self.main_content_stack.setSpacing(0)

        self.image_placeholder_container = PasteBoxContainer(self)
        self.image_placeholder_container.setMinimumSize(345, 330)

        image_container_layout = QGridLayout(self.image_placeholder_container)
        image_container_layout.setContentsMargins(0, 0, 0, 0)
        image_container_layout.setSpacing(0)
        image_container_layout.setAlignment(Qt.AlignCenter)

        self.gif_label = QLabel()
        self.gif_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.gif_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        image_container_layout.addWidget(self.gif_label, 0, 0)

        self.instructions_label = QLabel("Paste an image (Ctrl+V)\nOr drag & drop an image here\nPress Delete or Clear button to remove image")
        self.instructions_label.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        self.instructions_label.setStyleSheet("color: white; padding-bottom: 5px; background-color: transparent;")
        self.instructions_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        image_container_layout.addWidget(self.instructions_label, 0, 0)

        self.loading_label = QLabel("Analyzing image...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("color: #7289da; font-weight: bold; background-color: rgba(0,0,0,150); padding: 10px; border-radius: 5px;")
        self.loading_label.hide()
        image_container_layout.addWidget(self.loading_label, 0, 0)

        gif_path = os.path.join(os.path.dirname(__file__), "CryptoIcon", "analyzeboxplaceholder.gif")
        self.gif_movie = QMovie(gif_path)
        if not self.gif_movie.isValid():
            self.gif_movie = None
        else:
            self.gif_movie.setCacheMode(QMovie.CacheAll)
            self.gif_movie.setSpeed(100)
            self.gif_label.setMovie(self.gif_movie)
            self.gif_movie.start()

        self.main_content_stack.addWidget(self.image_placeholder_container)

        self.main_content_stack.addWidget(self.value_paste_widget)

        title_and_content_section_layout.addLayout(self.main_content_stack)
        main_layout.addLayout(title_and_content_section_layout)
        # End of new dedicated layout


        self.screenshot_buttons_widget = QWidget()
        # self.screenshot_buttons_widget.setFixedHeight(45) # REMOVED: This line is no longer present
        self.screenshot_action_buttons_layout = QHBoxLayout(self.screenshot_buttons_widget)

        self.screenshot_action_buttons_layout.addStretch()

        self.analyze_btn = QPushButton("Analyze")
        self.analyze_btn.clicked.connect(self.analyze_image)
        self.analyze_btn.setFocusPolicy(Qt.NoFocus)
        self.screenshot_action_buttons_layout.addWidget(self.analyze_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_image)
        self.clear_btn.setEnabled(False)
        self.clear_btn.setFocusPolicy(Qt.NoFocus)
        self.screenshot_action_buttons_layout.addWidget(self.clear_btn)

        self.screenshot_action_buttons_layout.addStretch()
        main_layout.addWidget(self.screenshot_buttons_widget)


        self.setStyleSheet("""
            QPushButton { background-color: #7289da; border: none; border-radius: 3px; padding: 8px; margin: 0; color: white; }
            QPushButton:hover { background-color: #677bc4; }
            QPushButton:disabled { background-color: #4a4d52; color: #72767d; }
            QPushButton.toggle_active { background-color: #5b6eac; border: 1px solid #7289da; }
        """)

    def _show_data_input(self):
        self.main_content_title_label.setText("Paste Network Data")
        self.main_content_stack.setCurrentWidget(self.value_paste_widget)
        self._update_toggle_button_style(self.btn_paste_data)

        self.screenshot_buttons_widget.hide() # Keep hidden as ValuePasteWidget has its own buttons

        self.clear_image()

    def _show_screenshot_input(self):
        self.main_content_title_label.setText("Paste Network Screenshot")
        self.main_content_stack.setCurrentWidget(self.image_placeholder_container)
        self._update_toggle_button_style(self.btn_screenshot)

        self.screenshot_buttons_widget.show() # Show for screenshot mode
        self.clear_btn.setEnabled(self.pasted_image is not None)

        self.value_paste_widget._clear_text_and_emit_signal()
        self.analyze_image()

    def _update_toggle_button_style(self, active_button):
        self.btn_paste_data.setProperty("toggle_active", False)
        self.btn_screenshot.setProperty("toggle_active", False)

        active_button.setProperty("toggle_active", True)

        self.btn_paste_data.style().polish(self.btn_paste_data)
        self.btn_screenshot.style().polish(self.btn_screenshot)

    def _on_power_input_changed(self):
        self._is_tier_manual_override = False
        self.analysis_debounce_timer.start()

    def _on_global_tier_combo_changed(self, index):
        if not self._setting_tier_programmatically:
            self._is_tier_manual_override = True
        self.analysis_debounce_timer.start()

    def keyPressEvent(self, event):
        if self.main_content_stack.currentWidget() == self.image_placeholder_container:
            if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_V:
                self.paste_image()
            elif event.key() == Qt.Key_Delete:
                self.clear_image()
        super().keyPressEvent(event)

    def _handle_drop_event_for_image_placeholder(self, event: QDropEvent):
        try:
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        self._display_image_and_analyze(file_path)
                        event.acceptProposedAction()
                        return
            event.ignore()
        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(self, "Drop Error", f"Failed to drop image: {e}")
            event.ignore()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self.main_content_stack.currentWidget() == self.image_placeholder_container:
            self.image_placeholder_container.dragEnterEvent(event)
        else:
            event.ignore()
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent):
        if self.main_content_stack.currentWidget() == self.image_placeholder_container:
            self.image_placeholder_container.dropEvent(event)
        else:
            event.ignore()
        super().dropEvent(event)

    def clear_image(self):
        """Clears the image data and resets image-related UI."""
        if self.pasted_image:
            self.pasted_image = None
            self._cached_ocr_results = {}
            self.gif_label.setPixmap(QPixmap())
            self.clear_btn.setEnabled(False)

        if self.analysis_worker and self.analysis_worker.isRunning():
            self.analysis_worker.quit()
            self.analysis_worker.wait()
            self.analysis_worker = None

        self.loading_label.hide()

        if self.gif_movie and self.gif_movie.isValid():
            self.gif_label.setMovie(self.gif_movie)
            self.gif_movie.start()
        else:
            self.gif_label.setText("GIF not available")

        self.instructions_label.setText("Paste an image (Ctrl+V)\nOr drag & drop an image here\nPress Delete or Clear button to remove image")
        self.analysis_debounce_timer.start()

    def paste_image(self):
        try:
            mime = self.clipboard.mimeData()
            if mime.hasImage():
                qt_img = self.clipboard.image()
                self._display_image_and_analyze(qt_img)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(self, "Paste Error", f"Failed to paste image: {e}")

    def _display_image_and_analyze(self, source):
        if self.gif_movie and self.gif_movie.isValid() and self.gif_movie.state() == QMovie.Running:
            self.gif_movie.stop()
            self.gif_label.setMovie(None)

        pixmap = None
        if isinstance(source, str):
            pixmap = QPixmap(source)
            self.pasted_image = Image.open(source).convert("RGB")
        elif isinstance(source, QImage):
            pixmap = QPixmap.fromImage(source)
            self.pasted_image = self._qimage_to_pil(source)
        else:
            return

        if not pixmap.isNull():
            preview = pixmap.scaled(
                self.gif_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.gif_label.setPixmap(preview)

            self.instructions_label.setText("")
            self.clear_btn.setEnabled(True)

            self._set_ui_enabled(False)
            self._update_loading_status("Performing OCR...")

            if self.analysis_worker and self.analysis_worker.isRunning():
                self.analysis_worker.quit()
                self.analysis_worker.wait()
                self.analysis_worker = None

            user_power_str = self.power_input_box.text()
            selected_tier_val = self.global_tier_combo.currentText()

            self.analysis_worker = AnalysisWorker(
                self.pasted_image,
                user_power_str,
                self.known_tickers,
                selected_tier_val,
                self.reader,
                apply_preprocessing=True
            )
            self.analysis_worker.analysis_finished.connect(self._on_ocr_analysis_finished)
            self.analysis_worker.loading_status_changed.connect(self._update_loading_status)
            self.analysis_worker.finished.connect(self._on_analysis_thread_cleanup)
            self.analysis_worker.start()

        else:
            QMessageBox.warning(self, "Image Load Error", "Could not load image for display.")

    def _qimage_to_pil(self, qimage):
        if qimage.format() != QImage.Format_RGBA8888:
            qimage = qimage.convertToFormat(QImage.Format_RGBA8888)

        width = qimage.width()
        height = qimage.height()
        ptr = qimage.bits()
        ptr.setsize(qimage.byteCount())
        pil_image = Image.frombuffer("RGBA", (width, height), bytes(ptr), "raw", "RGBA", 0, 1)
        return pil_image.convert("RGB")

    @staticmethod
    def pil_to_pixmap(pil_img):
        if pil_img.mode != "RGBA":
            pil_img = pil_img.convert("RGBA")

        data = pil_img.tobytes("raw", "RGBA")
        qimage = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qimage)

    def find_icon_box(self, original_pil_image, text_x_orig, text_y_orig, text_height_orig):
        return None

    def _set_ui_enabled(self, enabled):
        self.power_input_box.setEnabled(enabled)
        self.global_tier_combo.setEnabled(enabled)
        self.btn_paste_data.setEnabled(enabled)
        self.btn_screenshot.setEnabled(enabled)

        if self.main_content_stack.currentWidget() == self.image_placeholder_container:
            self.analyze_btn.setEnabled(enabled)
            self.clear_btn.setEnabled(enabled and (self.pasted_image is not None))


    def _update_loading_status(self, message):
        self.loading_label.setText(message)
        self.loading_label.show()
        self.instructions_label.hide()

    def analyze_image(self):
        user_power_str = self.power_input_box.text()
        selected_tier_val = self.global_tier_combo.currentText()

        try:
            if not self._is_tier_manual_override:
                user_power_ghs = convert_power_to_ghs(user_power_str, "Gh/s", UNIT_MULTIPLIERS)
                determined_tier = determine_tier_from_power(user_power_ghs, TIER_POWER_RANGES)
                if determined_tier and self.global_tier_combo.currentText() != determined_tier:
                    self._setting_tier_programmatically = True
                    index = self.global_tier_combo.findText(determined_tier)
                    if index != -1:
                        self.global_tier_combo.setCurrentIndex(index)
                    self._setting_tier_programmatically = False
                    selected_tier_val = determined_tier
                elif not determined_tier and user_power_ghs == 0 and self.global_tier_combo.currentText() != self.tier_options[0]:
                    self._setting_tier_programmatically = True
                    self.global_tier_combo.setCurrentIndex(0)
                    self._setting_tier_programmatically = False
                    selected_tier_val = self.tier_options[0]

            if self.main_content_stack.currentWidget() == self.image_placeholder_container and self.pasted_image:
                self.analysis_completed.emit(self._cached_ocr_results, user_power_str, selected_tier_val)
            else:
                self.analysis_completed.emit({}, user_power_str, selected_tier_val)

        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(self, "Analysis Error", f"An error occurred during analysis update:\n{e}")
            self.analysis_completed.emit({}, user_power_str, selected_tier_val)
            self._set_ui_enabled(True)

    def _on_ocr_analysis_finished(self, detected_values, user_power_str, selected_tier):
        self.loading_label.hide()
        self.instructions_label.show()

        self._cached_ocr_results = detected_values

        self.analysis_completed.emit(detected_values, user_power_str, selected_tier)
        self._set_ui_enabled(True)

    def _on_analysis_thread_cleanup(self):
        if self.analysis_worker:
            self.analysis_worker.deleteLater()
            self.analysis_worker = None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = QWidget()
    main_window.setWindowTitle("Image Analyzer Test")
    main_window.setGeometry(100, 100, 600, 700)

    analyzer_widget = ImageAnalyzerWidget()

    def on_analysis_completed(data, user_power_str, selected_tier):
        if data:
            for crypto, info in data.items():
                pass
        # print(f"User Power: {user_power_str}")
        # print(f"Selected Tier: {selected_tier}")
        # print("------------------------------------------")

    def on_value_data_parsed(data):
        QMessageBox.information(None, "Data Parsed (re-emitted)!", f"Data:\n{data}")

    def on_data_cleared():
        QMessageBox.information(None, "Data Cleared (re-emitted)!", "Value Paste data was cleared.")


    analyzer_widget.analysis_completed.connect(on_analysis_completed)
    analyzer_widget.value_data_parsed.connect(on_value_data_parsed)
    analyzer_widget.value_data_cleared.connect(on_data_cleared)


    layout = QVBoxLayout()
    layout.addWidget(analyzer_widget)
    main_window.setLayout(layout)

    main_window.show()
    QTimer.singleShot(0, lambda: analyzer_widget._show_data_input())
    QTimer.singleShot(150, lambda: QApplication.instance().activeWindow().clearFocus() if QApplication.instance().activeWindow() else None)
    sys.exit(app.exec_())
