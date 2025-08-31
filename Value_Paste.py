import sys
import re
from PyQt5.QtWidgets import (
    QWidget, QLabel, QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal

# Import necessary functions from Leagues_Info.py for power conversion
try:
    from Leagues_Info import UNIT_MULTIPLIERS, convert_power_to_ghs
except ImportError:
    UNIT_MULTIPLIERS = {"Gh/s": 1, "Th/s": 1e3, "Ph/s": 1e6, "Eh/s": 1e9, "Zh/s": 1e12}
    def convert_power_to_ghs(value_str, unit, multipliers):
        try:
            value = float(value_str.replace(',', ''))
            return value * multipliers.get(unit, 1)
        except ValueError:
            return 0.0

class ValuePasteWidget(QWidget):
    """
    A widget allowing users to paste text data containing cryptocurrency network
    power and block reward information. It parses this data and emits a signal
    for other widgets to update.
    """
    # Signal emitted when parsed data is ready: {ticker: {'rate': float, 'unit': str, 'block_reward': float}}
    pasted_data_parsed = pyqtSignal(dict)
    # Signal emitted when the text input is cleared
    data_cleared = pyqtSignal()

    def __init__(self, known_tickers=None):
        super().__init__()
        self.setFocusPolicy(Qt.NoFocus)
        self.known_tickers = known_tickers if known_tickers is not None else [
            "RLT", "RST", "XRP", "TRX", "DOGE",
            "BTC", "ETH", "BNB", "POL", "SOL", "LTC"
        ]
        self.clipboard = QApplication.clipboard()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5) # MODIFIED: Reduced vertical spacing between items in the layout

        # The title_label was removed previously and will be managed by the parent ImageAnalyzerWidget.

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Paste your data here (Ctrl+V)...")
        self.text_input.setMinimumHeight(60) # MODIFIED: Reduced minimum height of the paste box
        self.text_input.setStyleSheet("""
            QTextEdit {
                background-color: #2f3136;
                border: 1px solid #40444b;
                border-radius: 3px;
                padding: 5px;
                color: white;
            }
        """)
        self.text_input.setFocusPolicy(Qt.StrongFocus)
        main_layout.addWidget(self.text_input)

        button_layout = QHBoxLayout()

        self.parse_button = QPushButton("Parse & Update")
        self.parse_button.clicked.connect(self._parse_and_emit_data)
        self.parse_button.setStyleSheet("""
            QPushButton {
                background-color: #7289da;
                border: none;
                border-radius: 3px;
                padding: 8px;
                margin: 0;
                color: white;
            }
            QPushButton:hover {
                background-color: #677bc4;
            }
            QPushButton:disabled {
                background-color: #4a4d52;
                color: #72767d;
            }
        """)
        self.parse_button.setFocusPolicy(Qt.NoFocus)
        button_layout.addWidget(self.parse_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._clear_text_and_emit_signal)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545; /* Red for clear */
                border: none;
                border-radius: 3px;
                padding: 8px;
                margin: 0;
                color: white;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #4a4d52;
                color: #72767d;
            }
        """)
        self.clear_button.setFocusPolicy(Qt.NoFocus)
        button_layout.addWidget(self.clear_button)

        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def _clear_text_and_emit_signal(self):
        self.text_input.clear()
        self.data_cleared.emit()

    def keyPressEvent(self, event):
        if self.text_input.hasFocus() and event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_V:
            self.text_input.paste()
            event.accept()
        elif self.text_input.hasFocus() and event.key() == Qt.Key_Delete:
            self._clear_text_and_emit_signal()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _is_similar_ticker_internal(self, detected_text):
        if detected_text in self.known_tickers:
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
            "XRP": "XRP",
            "MATIC": "POL",
        }

        if detected_text in error_mappings:
            return error_mappings[detected_text]

        for known_ticker in self.known_tickers:
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

    def _parse_text_data(self):
        raw_text = self.text_input.toPlainText()
        lines = raw_text.strip().split('\n')
        parsed_data = {}
        current_ticker_context = None

        power_unit_pattern = re.compile(r'(\d[\d,]*\.?\d*)\s*([a-zA-Z/]+)?', re.IGNORECASE)

        known_unit_symbols = {k.upper(): k for k in UNIT_MULTIPLIERS.keys()}

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                current_ticker_context = None
                continue

            possible_ticker = self._is_similar_ticker_internal(line_stripped.upper())
            if possible_ticker:
                current_ticker_context = possible_ticker
                if current_ticker_context not in parsed_data:
                    parsed_data[current_ticker_context] = {'rate': "", 'unit': "", 'block_reward': ""}
                continue

            if current_ticker_context:
                power_match = power_unit_pattern.match(line_stripped)
                if power_match:
                    power_value_str = power_match.group(1).replace(',', '')
                    power_unit_str_raw = power_match.group(2) if power_match.group(2) else ""

                    effective_unit = power_unit_str_raw
                    if effective_unit:
                        effective_unit = known_unit_symbols.get(effective_unit.upper(), effective_unit)
                        if effective_unit not in UNIT_MULTIPLIERS:
                            effective_unit = ""
                    
                    temp_power_str_for_conversion = power_value_str + (" " + effective_unit if effective_unit else "")
                    power_in_ghs = convert_power_to_ghs(temp_power_str_for_conversion, effective_unit, UNIT_MULTIPLIERS)

                    if power_in_ghs >= 0 and power_value_str:
                        parsed_data[current_ticker_context]['rate'] = power_value_str
                        parsed_data[current_ticker_context]['unit'] = effective_unit if effective_unit else "Gh/s"
        return parsed_data

    def _parse_and_emit_data(self):
        parsed_data = self._parse_text_data()
        if parsed_data:
            self.pasted_data_parsed.emit(parsed_data)
        else:
            QMessageBox.information(self, "No Data Parsed", "No valid cryptocurrency data was found in the pasted text.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = ValuePasteWidget()
    widget.setWindowTitle("Value Paste Test")
    widget.setGeometry(200, 200, 400, 300)

    def on_parsed_data(data):
        QMessageBox.information(None, "Data Parsed!", f"Data:\n{data}")

    def on_data_cleared():
        QMessageBox.information(None, "Data Cleared!", "Value Paste data was cleared.")

    widget.pasted_data_parsed.connect(on_parsed_data)
    widget.data_cleared.connect(on_data_cleared)

    test_data = """
rlt
RLT
485.544 Eh/s

rst
RST
215.061 Eh/s

Crypto Currencies

xrp
XRP
234.557 Eh/s

trx
TRX
385.958 Eh/s

doge
DOGE
549.234 Eh/s

btc
BTC
707.933 Eh/s

eth
ETH
252.110 Eh/s

bnb
BNB
310.752 Eh/s

matic
POL
636.577 Eh/s

ltc
LTC
195.149 Eh/s
"""
    widget.text_input.setText(test_data)

    widget.show()
    QTimer.singleShot(100, lambda: QApplication.instance().activeWindow().clearFocus() if QApplication.instance().activeWindow() else None)
    sys.exit(app.exec_())
