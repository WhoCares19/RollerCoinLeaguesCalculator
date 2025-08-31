import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon

# Get the absolute path of the current script's directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Import the custom widgets from their respective files
from Analyzer import ImageAnalyzerWidget
from CryptoDisplayWidget import CryptoDisplayWidget

class MainWindow(QWidget):
    """
    The main application window for the Rollercoin Calculator.
    It integrates the ImageAnalyzerWidget and CryptoDisplayWidget
    into a structured layout.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rollercoin Calculator")
        self.setFocusPolicy(Qt.NoFocus)

        # --- IMPORTANT: Critical Order for Window Properties ---
        # 1. Set window flags FIRST to define the window's type and controls.
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowCloseButtonHint |
            Qt.WindowMinimizeButtonHint
        )

        # 2. Then set the geometry and fixed size.
        initial_width = 1200
        initial_height = 520
        self.setGeometry(100, 100, initial_width, initial_height)
        self.setFixedSize(initial_width, initial_height)

        # 3. Set the icon, but with a slight delay
        self.icon_path_main_window = os.path.join(SCRIPT_DIR, "CryptoIcon", "RCICON.ico")
        QTimer.singleShot(10, self._set_main_window_icon_delayed)

        self.init_ui()

    def _set_main_window_icon_delayed(self):
        """Helper function to set the main window icon after a short delay."""
        if os.path.exists(self.icon_path_main_window):
            try:
                self.setWindowIcon(QIcon(self.icon_path_main_window))
                self.update()
            except Exception as e:
                pass # Suppress print, consider logging to a file in a real application
        else:
            pass # Suppress print, consider logging to a file in a real application


    def init_ui(self):
        """
        Initializes the main user interface of the application.
        Sets up the overall layout and integrates all sub-widgets.
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        main_layout.setSizeConstraint(QVBoxLayout.SetFixedSize)


        top_section_layout = QHBoxLayout()
        top_section_layout.setSpacing(15)

        self.image_analyzer_widget = ImageAnalyzerWidget()
        self.image_analyzer_widget.setFixedHeight(549) # ADDED: Set fixed height for the ImageAnalyzerWidget
        top_section_layout.addWidget(self.image_analyzer_widget)


        self.crypto_display_widget = CryptoDisplayWidget(
            pil_to_pixmap_func=self.image_analyzer_widget.pil_to_pixmap,
            image_analyzer_widget_instance=self.image_analyzer_widget
        )
        top_section_layout.addWidget(self.crypto_display_widget)

        self.image_analyzer_widget.analysis_completed.connect(self.crypto_display_widget.update_crypto_list)
        self.image_analyzer_widget.value_data_parsed.connect(self.crypto_display_widget.update_from_pasted_data)
        self.image_analyzer_widget.value_data_cleared.connect(self.crypto_display_widget.clear_pasted_data)


        main_layout.addLayout(top_section_layout)

        self.setStyleSheet("""
            QWidget {
                background-color: #202225;
                color: white;
                font-family: "Inter";
            }
            QLineEdit, QComboBox {
                border: 1px solid #40444b;
                border-radius: 3px;
                padding: 3px;
                background-color: #2f3136;
                color: white;
            }
            QLabel {
                color: white;
            }
        """)

# Helper function to explicitly clear focus from all potential input widgets
def _clear_all_input_focus(main_window_instance: MainWindow):
    # Clear focus from the user power input box
    if main_window_instance.image_analyzer_widget.power_input_box.hasFocus():
        main_window_instance.image_analyzer_widget.power_input_box.clearFocus()

    # Clear focus from the ValuePasteWidget's text input area
    if main_window_instance.image_analyzer_widget.value_paste_widget.text_input.hasFocus():
        main_window_instance.image_analyzer_widget.value_paste_widget.text_input.clearFocus()

    # As a final, robust measure, clear focus from the active window itself
    active_window = QApplication.instance().activeWindow()
    if active_window and active_window.hasFocus():
        active_window.clearFocus()

# A debug function to check current focus if needed.
def debug_focus_check():
    focused_widget = QApplication.instance().focusWidget()
    active_window = QApplication.instance().activeWindow()
    # Uncomment the following line if you need to re-enable focus debugging temporarily
    # print(f"DEBUG: Focus Check: Focused widget: {focused_widget.__class__.__name__ if focused_widget else 'None'}, Active window: {active_window.windowTitle() if active_window else 'None'}")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Set Application-Wide Icon
    app_icon_path = os.path.join(SCRIPT_DIR, "CryptoIcon", "RCICON.ico")
    if os.path.exists(app_icon_path):
        try:
            app.setWindowIcon(QIcon(app_icon_path))
        except Exception as e:
            pass # Suppress print, consider logging to a file in a real application
    else:
        pass # Suppress print, consider logging to a file in a real application

    window = MainWindow()
    window.show()

    # Schedule initial display mode
    QTimer.singleShot(0, lambda: window.image_analyzer_widget._show_data_input())

    # Ensure no widget has focus after startup
    QTimer.singleShot(200, lambda: QApplication.instance().focusWidget().clearFocus()
                      if QApplication.instance().focusWidget() else None)


    sys.exit(app.exec_())
