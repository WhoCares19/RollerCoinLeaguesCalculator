import os
import re
import traceback
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QHBoxLayout, QVBoxLayout, QGridLayout, QSizePolicy, QApplication, QComboBox
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem

from reward_calculations import (
    calculate_reward_per_block,
    calculate_blocks_per_day,
    calculate_reward_per_day,
    calculate_reward_per_week,
    calculate_reward_per_month,
    calculate_reward_per_year
)

from Leagues_Info import (
    TIER_CRYPTO_MAPPING,
    UNIT_MULTIPLIERS,
    TIER_POWER_RANGES,
    convert_power_to_ghs,
    determine_tier_from_power
)

from Crypto_Slider import CryptoSlider
from BlockDurationRewardSave import BlockDataPersistenceManager

class ClearOnFocusLineEdit(QLineEdit):
    def focusInEvent(self, event):
        self.selectAll()
        super().focusInEvent(event)

class CryptoDisplayWidget(QWidget):
    def __init__(self, pil_to_pixmap_func, image_analyzer_widget_instance):
        super().__init__()
        self.pil_to_pixmap = pil_to_pixmap_func
        self.image_analyzer_widget = image_analyzer_widget_instance

        self._is_tier_manual_override = False
        self._setting_tier_programmatically = False
        self._is_initializing = True # NEW: Flag to prevent saving during initial setup

        self._last_detected_values = {} # From OCR
        self._last_pasted_values = {}  # From manual text paste
        self._currency_display_mode = "Crypto"

        # Define hardcoded block rewards and durations, now used as universal defaults
        # All will show "--" unless explicitly changed and saved by the user.
        self.block_rewards_defaults = {
            "RLT": "--", "RST": "--", "BTC": "--", "LTC": "--", "BNB": "--",
            "POL": "--", "XRP": "--", "DOGE": "--", "ETH": "--", "TRX": "--", "SOL": "--"
        }
        self.block_durations_defaults = {
            "RLT": "--", "RST": "--", "BTC": "--", "LTC": "--", "BNB": "--",
            "POL": "--", "XRP": "--", "DOGE": "--", "ETH": "--", "TRX": "--", "SOL": "--"
        }

        self.crypto_widgets = {}

        self.crypto_slider = CryptoSlider()

        self.conversion_rates = {
            "USDT": {
                "RLT": 0.5,
                "RST": 0.0001,
                "XRP": 0.0,
                "TRX": 0.0,
                "DOGE": 0.0,
                "BTC": 0.0,
                "ETH": 0.0,
                "BNB": 0.0,
                "POL": 0.0,
                "SOL": 0.0,
                "LTC": 0.0
            },
            "Euro": {
                "RLT": 0.45,
                "RST": 0.00009,
                "XRP": 0.55,
                "TRX": 0.09,
                "DOGE": 0.07,
                "BTC": 55000.0,
                "ETH": 2800.0,
                "BNB": 450.0,
                "POL": 1.3,
                "SOL": 140.0,
                "LTC": 65.0
            }
        }
        self._original_reward_values = {crypto: {
            'reward_per_block': 0.0,
            'daily_reward': 0.0,
            'weekly_reward': 0.0,
            'monthly_reward': 0.0,
            'yearly_reward': 0.0
        } for crypto in [
            "RLT", "RST", "XRP", "TRX", "DOGE",
            "BTC", "ETH", "BNB", "POL", "SOL", "LTC"
        ]}

        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.block_data_manager = BlockDataPersistenceManager(script_dir)
        self._user_overridden_block_data = self.block_data_manager.load_block_data()

        self.init_ui()


    def init_ui(self):
        overall_v_layout = QVBoxLayout(self)
        overall_v_layout.setContentsMargins(10, 10, 10, 10)
        overall_v_layout.setSpacing(10)

        main_grid_layout = QGridLayout()
        main_grid_layout.setContentsMargins(0, 0, 0, 0)
        main_grid_layout.setSpacing(5)

        main_grid_layout.addWidget(QLabel(""), 0, 0)

        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["Crypto", "USDT", "Euro"])
        self.currency_combo.setFixedSize(70, 25)
        self.currency_combo.setStyleSheet("""
            QComboBox {
                background-color: #2f3136;
                border: 1px solid #40444b;
                border-radius: 3px;
                color: white;
            }
            QComboBox::drop-down {
                border: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #2f3136;
                border: 1px solid #40444b;
                color: white;
                selection-background-color: #7289da;
                text-align: center;
            }
            QComboBox QLineEdit {
                text-align: center;
                padding: 0px;
            }
        """)
        self.currency_combo.view().setTextElideMode(Qt.ElideNone)
        self.currency_combo.currentIndexChanged.connect(self._on_currency_combo_changed)
        main_grid_layout.addWidget(self.currency_combo, 0, 1, Qt.AlignCenter)

        network_power_header_label = QLabel("Network\n power")
        network_power_header_label.setAlignment(Qt.AlignCenter)
        network_power_header_label.setStyleSheet("font-weight: bold; padding-bottom: 5px;")
        main_grid_layout.addWidget(network_power_header_label, 0, 2, Qt.AlignCenter)

        header_labels = [
            "Block\n Duration", "Block\n reward",
            "Reward\n Per Block",
            "Daily\n reward", "Weekly\n reward", "Monthly\n reward", "Yearly\n reward"
        ]
        for col_idx, header_text in enumerate(header_labels):
            header_label = QLabel(header_text)
            header_label.setAlignment(Qt.AlignCenter)
            header_label.setStyleSheet("font-weight: bold; padding-bottom: 5px;")
            main_grid_layout.addWidget(header_label, 0, col_idx + 3)


        icon_width = 30
        ticker_column_width = 70
        data_column_width = 120

        rate_unit_spacing = 5
        rate_width = 70
        unit_width = data_column_width - rate_width - rate_unit_spacing

        self.crypto_list = [
            "RLT", "RST", "XRP", "TRX", "DOGE",
            "BTC", "ETH", "BNB", "POL", "SOL", "LTC"
        ]

        for row_idx, crypto in enumerate(self.crypto_list):
            current_grid_row = row_idx + 1
            self.crypto_widgets[crypto] = {}

            logo = QLabel()
            logo.setFixedSize(icon_width, icon_width)
            logo.setStyleSheet("border: none; padding: 2px;")
            logo.setAlignment(Qt.AlignCenter)
            main_grid_layout.addWidget(logo, current_grid_row, 0, Qt.AlignCenter)
            self.crypto_widgets[crypto]['logo'] = logo

            ticker = QLineEdit()
            ticker.setFixedSize(ticker_column_width, 25)
            ticker.setText(crypto)
            ticker.setReadOnly(True)
            ticker.setAlignment(Qt.AlignCenter)
            main_grid_layout.addWidget(ticker, current_grid_row, 1, Qt.AlignCenter)
            self.crypto_widgets[crypto]['ticker'] = ticker

            network_power_h_layout = QHBoxLayout()
            network_power_h_layout.setSpacing(rate_unit_spacing)
            network_power_h_layout.setContentsMargins(0,0,0,0)

            rate = ClearOnFocusLineEdit()
            rate.blockSignals(True)
            rate.setFixedSize(rate_width, 25)
            rate.setPlaceholderText("Rate")
            rate.setReadOnly(False)
            rate.setAlignment(Qt.AlignCenter)
            network_power_h_layout.addWidget(rate)
            self.crypto_widgets[crypto]['rate'] = rate
            rate.blockSignals(False)
            rate.textChanged.connect(lambda text, c=crypto: self._recalculate_row_rewards(c))


            unit = QLineEdit()
            unit.blockSignals(True)
            unit.setFixedSize(unit_width, 25)
            unit.setReadOnly(False)
            unit.setAlignment(Qt.AlignCenter)
            unit.setText("")
            network_power_h_layout.addWidget(unit)
            self.crypto_widgets[crypto]['unit'] = unit
            unit.blockSignals(False)
            unit.textChanged.connect(lambda text, c=crypto: self._recalculate_row_rewards(c))

            network_power_wrapper = QWidget()
            network_power_wrapper.setLayout(network_power_h_layout)
            network_power_wrapper.setFixedSize(data_column_width, 25)
            main_grid_layout.addWidget(network_power_wrapper, current_grid_row, 2, Qt.AlignCenter)
            self.crypto_widgets[crypto]['network_power_wrapper'] = network_power_wrapper


            block_duration_input = ClearOnFocusLineEdit()
            block_duration_input.blockSignals(True)
            block_duration_input.setFixedSize(80, 25)
            block_duration_input.setReadOnly(False)
            block_duration_input.setAlignment(Qt.AlignCenter)
            main_grid_layout.addWidget(block_duration_input, current_grid_row, 3, Qt.AlignCenter)
            self.crypto_widgets[crypto]['block_duration_input'] = block_duration_input
            block_duration_input.blockSignals(False)
            block_duration_input.textChanged.connect(lambda text, c=crypto: self._recalculate_row_rewards(c))


            block_reward_output = ClearOnFocusLineEdit()
            block_reward_output.blockSignals(True)
            block_reward_output.setFixedSize(75, 25)
            block_reward_output.setReadOnly(False)
            block_reward_output.setAlignment(Qt.AlignCenter)
            main_grid_layout.addWidget(block_reward_output, current_grid_row, 4, Qt.AlignCenter)
            self.crypto_widgets[crypto]['block_reward_output'] = block_reward_output
            block_reward_output.blockSignals(False)
            block_reward_output.textChanged.connect(lambda text, c=crypto: self._recalculate_row_rewards(c))


            reward_per_block_output = QLineEdit()
            reward_per_block_output.setFixedSize(100, 25)
            reward_per_block_output.setText("00")
            reward_per_block_output.setReadOnly(True)
            reward_per_block_output.setAlignment(Qt.AlignCenter)
            main_grid_layout.addWidget(reward_per_block_output, current_grid_row, 5, Qt.AlignCenter)
            self.crypto_widgets[crypto]['reward_per_block_output'] = reward_per_block_output


            daily_reward_output = QLineEdit()
            daily_reward_output.setFixedSize(100, 25)
            daily_reward_output.setText("00")
            daily_reward_output.setReadOnly(True)
            daily_reward_output.setAlignment(Qt.AlignCenter)
            main_grid_layout.addWidget(daily_reward_output, current_grid_row, 6, Qt.AlignCenter)
            self.crypto_widgets[crypto]['daily_reward_output'] = daily_reward_output

            weekly_reward_output1 = QLineEdit()
            weekly_reward_output1.setFixedSize(100, 25)
            weekly_reward_output1.setText("00")
            weekly_reward_output1.setReadOnly(True)
            weekly_reward_output1.setAlignment(Qt.AlignCenter)
            main_grid_layout.addWidget(weekly_reward_output1, current_grid_row, 7, Qt.AlignCenter)
            self.crypto_widgets[crypto]['weekly_reward_output1'] = weekly_reward_output1

            monthly_reward_output = QLineEdit()
            monthly_reward_output.setFixedSize(100, 25)
            monthly_reward_output.setText("00")
            monthly_reward_output.setReadOnly(True)
            monthly_reward_output.setAlignment(Qt.AlignCenter)
            main_grid_layout.addWidget(monthly_reward_output, current_grid_row, 8, Qt.AlignCenter)
            self.crypto_widgets[crypto]['monthly_reward_output'] = monthly_reward_output

            yearly_reward_output = QLineEdit()
            yearly_reward_output.setFixedSize(100, 25)
            yearly_reward_output.setText("00")
            yearly_reward_output.setReadOnly(True)
            yearly_reward_output.setAlignment(Qt.AlignCenter)
            main_grid_layout.addWidget(yearly_reward_output, current_grid_row, 9, Qt.AlignCenter)
            self.crypto_widgets[crypto]['yearly_reward_output'] = yearly_reward_output

        main_grid_layout.setRowStretch(len(self.crypto_list) + 1, 1)
        main_grid_layout.setColumnStretch(0, 0)
        main_grid_layout.setColumnStretch(1, 0)
        main_grid_layout.setColumnStretch(2, 0)
        main_grid_layout.setColumnStretch(3, 0)
        main_grid_layout.setColumnStretch(4, 0)
        main_grid_layout.setColumnStretch(9, 1)

        overall_v_layout.addLayout(main_grid_layout)

        self._load_all_crypto_icons()
        self._update_crypto_row_visibility()

        self.setFocusPolicy(Qt.StrongFocus)

    def _load_crypto_icon(self, crypto_symbol):
        base_path = os.path.dirname(__file__)
        icon_path = os.path.join(base_path, "CryptoIcon", f"{crypto_symbol}.png")

        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    self.crypto_widgets[crypto_symbol]['logo'].size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.crypto_widgets[crypto_symbol]['logo'].setPixmap(scaled_pixmap)
            else:
                self.crypto_widgets[crypto_symbol]['logo'].clear()
        else:
            self.crypto_widgets[crypto_symbol]['logo'].clear()

    def _load_all_crypto_icons(self):
        for crypto_symbol in self.crypto_list:
            self._load_crypto_icon(crypto_symbol)

    def _update_crypto_row_visibility(self):
        selected_tier = self.image_analyzer_widget.global_tier_combo.currentText()
        active_cryptos_for_tier = TIER_CRYPTO_MAPPING.get(selected_tier, [])

        for crypto_symbol in self.crypto_list:
            is_active = crypto_symbol in active_cryptos_for_tier

            widgets_to_control = [
                self.crypto_widgets[crypto_symbol]['logo'],
                self.crypto_widgets[crypto_symbol]['ticker'],
                self.crypto_widgets[crypto_symbol]['network_power_wrapper'],
                self.crypto_widgets[crypto_symbol]['block_duration_input'],
                self.crypto_widgets[crypto_symbol]['block_reward_output'],
                self.crypto_widgets[crypto_symbol]['reward_per_block_output'],
                self.crypto_widgets[crypto_symbol]['daily_reward_output'],
                self.crypto_widgets[crypto_symbol]['weekly_reward_output1'],
                self.crypto_widgets[crypto_symbol]['monthly_reward_output'],
                self.crypto_widgets[crypto_symbol]['yearly_reward_output']
            ]

            for widget in widgets_to_control:
                widget.setVisible(is_active)

            widgets = self.crypto_widgets[crypto_symbol]
            widgets['rate'].blockSignals(True)
            widgets['unit'].blockSignals(True)
            widgets['block_duration_input'].blockSignals(True)
            widgets['block_reward_output'].blockSignals(True)
            widgets['reward_per_block_output'].blockSignals(True)
            widgets['daily_reward_output'].blockSignals(True)
            widgets['weekly_reward_output1'].blockSignals(True)
            widgets['monthly_reward_output'].blockSignals(True)
            widgets['yearly_reward_output'].blockSignals(True)

            if not is_active:
                # When a row becomes inactive, ensure all its fields are cleared and set to "--" defaults
                widgets['rate'].setText("")
                widgets['unit'].setText("")
                widgets['block_duration_input'].setText(self.block_durations_defaults.get(crypto_symbol, "--"))
                widgets['block_reward_output'].setText(self.block_rewards_defaults.get(crypto_symbol, "--"))
                widgets['reward_per_block_output'].setText("00")
                widgets['daily_reward_output'].setText("00")
                widgets['weekly_reward_output1'].setText("00")
                widgets['monthly_reward_output'].setText("00")
                widgets['yearly_reward_output'].setText("00")
                widgets['logo'].clear()
            else: # if the row is active
                # Reset display to its universal default state before applying priority logic
                widgets['rate'].setText("")
                widgets['unit'].setText("")
                widgets['logo'].clear()
                widgets['block_reward_output'].setText(self.block_rewards_defaults.get(crypto_symbol, "--"))
                widgets['block_duration_input'].setText(self.block_durations_defaults.get(crypto_symbol, "--"))


                # 1. Populate Network Power/Unit (from OCR or pasted data)
                if crypto_symbol in self._last_detected_values:
                    info = self._last_detected_values[crypto_symbol]
                    widgets['rate'].setText(str(info['rate']))
                    widgets['unit'].setText(info.get('unit', ''))
                    # Icon logic from OCR
                    if self.image_analyzer_widget and self.image_analyzer_widget.pasted_image:
                        icon_box = self.image_analyzer_widget.find_icon_box(
                            self.image_analyzer_widget.pasted_image,
                            info['ticker_x'],
                            info['ticker_y'],
                            info['ticker_height']
                        )
                        if icon_box:
                            try:
                                x, y, w, h = icon_box
                                icon_img = self.image_analyzer_widget.pasted_image.crop((x, y, x+w, y+h))
                                icon_pixmap = self.pil_to_pixmap(icon_img)
                                scaled_pixmap = icon_pixmap.scaled(
                                    widgets['logo'].size(),
                                    Qt.KeepAspectRatio,
                                    Qt.SmoothTransformation
                                )
                                self.crypto_widgets[crypto_symbol]['logo'].setPixmap(scaled_pixmap)
                            except Exception:
                                pass
                elif crypto_symbol in self._last_pasted_values:
                    info = self._last_pasted_values[crypto_symbol]
                    if info['rate']: widgets['rate'].setText(str(info['rate']))
                    if info['unit']: widgets['unit'].setText(info.get('unit', ''))
                
                # 2. Populate Block Duration/Reward (from saved data, overriding the "--" default)
                if crypto_symbol in self._user_overridden_block_data:
                    user_saved_data = self._user_overridden_block_data[crypto_symbol]
                    if user_saved_data.get('block_duration'):
                        widgets['block_duration_input'].setText(user_saved_data['block_duration'])
                    if user_saved_data.get('block_reward'):
                        widgets['block_reward_output'].setText(user_saved_data['block_reward'])
                
                # Ensure there's an icon for active rows (either OCR's or default)
                if widgets['logo'].pixmap() is None or widgets['logo'].pixmap().isNull():
                     self._load_crypto_icon(crypto_symbol)

            widgets['rate'].blockSignals(False)
            widgets['unit'].blockSignals(False)
            widgets['block_duration_input'].blockSignals(False)
            widgets['block_reward_output'].blockSignals(False)
            widgets['reward_per_block_output'].blockSignals(False)
            widgets['daily_reward_output'].blockSignals(False)
            widgets['weekly_reward_output1'].blockSignals(False)
            widgets['monthly_reward_output'].blockSignals(False)
            widgets['yearly_reward_output'].blockSignals(False)

        # Trigger recalculations for all *currently active* rows based on the selected tier
        for crypto_symbol in self.crypto_list:
            if crypto_symbol in TIER_CRYPTO_MAPPING.get(selected_tier, []):
                self._recalculate_row_rewards(crypto_symbol)
            else:
                pass


    def _recalculate_row_rewards(self, crypto_symbol):
        try:
            user_power_str = self.image_analyzer_widget.power_input_box.text()
            
            network_hashrate_str = self.crypto_widgets[crypto_symbol]['rate'].text()
            network_unit = self.crypto_widgets[crypto_symbol]['unit'].text()

            coin_block_reward_str = self.crypto_widgets[crypto_symbol]['block_reward_output'].text()
            block_duration_str = self.crypto_widgets[crypto_symbol]['block_duration_input'].text()

            # MODIFIED: Always assign current_duration_text and current_reward_text
            current_duration_text = block_duration_str.strip()
            current_reward_text = coin_block_reward_str.strip()

            if not self._is_initializing: # Only save if NOT during initial setup
                if crypto_symbol not in self._user_overridden_block_data:
                    self._user_overridden_block_data[crypto_symbol] = {}
                
                # MODIFIED: Robust saving logic for block duration - save if not empty and not "--"
                if current_duration_text and current_duration_text != "--":
                    self._user_overridden_block_data[crypto_symbol]['block_duration'] = current_duration_text
                else:
                    self._user_overridden_block_data[crypto_symbol].pop('block_duration', None)
                
                # MODIFIED: Robust saving logic for block reward - save if not empty and not "--"
                if current_reward_text and current_reward_text != "--":
                    self._user_overridden_block_data[crypto_symbol]['block_reward'] = current_reward_text
                else:
                    self._user_overridden_block_data[crypto_symbol].pop('block_reward', None)
                
                # Remove crypto entry entirely if both duration and reward are now effectively "default"
                if not self._user_overridden_block_data.get(crypto_symbol):
                    self._user_overridden_block_data.pop(crypto_symbol, None)

                self.block_data_manager.save_block_data(self._user_overridden_block_data)


            # Use "00" for calculation if the input string is empty or "--", to prevent ValueError
            duration_for_calc = current_duration_text if current_duration_text and current_duration_text != "--" else "00"
            reward_for_calc = current_reward_text if current_reward_text and current_reward_text != "--" else "00"

            reward_per_block = calculate_reward_per_block(
                user_power_str, "Gh/s",
                reward_for_calc,
                network_hashrate_str, network_unit
            )
            blocks_per_day = calculate_blocks_per_day(duration_for_calc)

            daily_reward = calculate_reward_per_day(reward_per_block, blocks_per_day)
            weekly_reward = daily_reward * 7
            monthly_reward = daily_reward * 30.44
            yearly_reward = daily_reward * 365.25

            self._original_reward_values[crypto_symbol] = {
                'reward_per_block': reward_per_block,
                'daily_reward': daily_reward,
                'weekly_reward': weekly_reward,
                'monthly_reward': monthly_reward,
                'yearly_reward': yearly_reward
            }

            self._update_displayed_rewards(crypto_symbol)

        except ValueError:
            widgets = self.crypto_widgets[crypto_symbol]
            widgets['reward_per_block_output'].setText("00")
            widgets['daily_reward_output'].setText("00")
            widgets['weekly_reward_output1'].setText("00")
            widgets['monthly_reward_output'].setText("00")
            widgets['yearly_reward_output'].setText("00")
            self._original_reward_values[crypto_symbol] = {
                'reward_per_block': 0.0, 'daily_reward': 0.0, 'weekly_reward': 0.0,
                'monthly_reward': 0.0, 'yearly_reward': 0.0
            }
        except Exception as e:
            traceback.print_exc()
            widgets = self.crypto_widgets[crypto_symbol]
            widgets['reward_per_block_output'].setText("00")
            widgets['daily_reward_output'].setText("00")
            widgets['weekly_reward_output1'].setText("00")
            widgets['monthly_reward_output'].setText("00")
            widgets['yearly_reward_output'].setText("00")
            self._original_reward_values[crypto_symbol] = {
                'reward_per_block': 0.0, 'daily_reward': 0.0, 'weekly_reward': 0.0,
                'monthly_reward': 0.0, 'yearly_reward': 0.0
            }

    def _on_currency_combo_changed(self, index):
        selected_currency = self.currency_combo.itemText(index)
        self._currency_display_mode = selected_currency
        if selected_currency == "USDT":
            self.crypto_slider.fetch_usdt_conversion_rates()
            QApplication.processEvents()
            fetched_usdt_rates = self.crypto_slider.get_usdt_rates()
            self.conversion_rates["USDT"].update(fetched_usdt_rates)
        elif selected_currency == "Euro":
            self.crypto_slider.fetch_euro_conversion_rates()
            QApplication.processEvents()
            fetched_eur_rates = self.crypto_slider.get_euro_rates()
            self.conversion_rates["Euro"].update(fetched_eur_rates)


        active_cryptos_for_tier = TIER_CRYPTO_MAPPING.get(self.image_analyzer_widget.global_tier_combo.currentText(), [])
        for crypto in self.crypto_list:
            if crypto in active_cryptos_for_tier:
                self._update_displayed_rewards(crypto)

    def _update_displayed_rewards(self, crypto_symbol):
        widgets = self.crypto_widgets[crypto_symbol]
        current_currency_mode = self._currency_display_mode

        original_rewards = self._original_reward_values.get(crypto_symbol, {
            'reward_per_block': 0.0,
            'daily_reward': 0.0,
            'weekly_reward': 0.0,
            'monthly_reward': 0.0,
            'yearly_reward': 0.0
        })

        reward_per_block = original_rewards['reward_per_block']
        daily_reward = original_rewards['daily_reward']
        weekly_reward = original_rewards['daily_reward'] * 7
        monthly_reward = original_rewards['daily_reward'] * 30.44
        yearly_reward = original_rewards['daily_reward'] * 365.25

        if current_currency_mode == "USDT":
            conversion_rate = self.conversion_rates["USDT"].get(crypto_symbol, 1.0)
            reward_per_block *= conversion_rate
            daily_reward *= conversion_rate
            weekly_reward *= conversion_rate
            monthly_reward *= conversion_rate
            yearly_reward *= conversion_rate
        elif current_currency_mode == "Euro":
            conversion_rate = self.conversion_rates["Euro"].get(crypto_symbol, 1.0)
            reward_per_block *= conversion_rate
            daily_reward *= conversion_rate
            weekly_reward *= conversion_rate
            monthly_reward *= conversion_rate
            yearly_reward *= conversion_rate

        def format_reward_output(value):
            if abs(value) < 1e-9:
                return "00"
            formatted_str = f"{value:.8f}".rstrip('0').rstrip('.')
            if formatted_str == '':
                return "00"
            if len(formatted_str) > 10 and '.' not in formatted_str:
                 return formatted_str[:10]
            return formatted_str

        widgets['reward_per_block_output'].setText(format_reward_output(reward_per_block))
        widgets['daily_reward_output'].setText(format_reward_output(daily_reward))
        widgets['weekly_reward_output1'].setText(format_reward_output(weekly_reward))
        widgets['monthly_reward_output'].setText(format_reward_output(monthly_reward))
        widgets['yearly_reward_output'].setText(format_reward_output(yearly_reward))


    def _update_crypto_row_visibility_only(self):
        selected_tier = self.image_analyzer_widget.global_tier_combo.currentText()
        active_cryptos_for_tier = TIER_CRYPTO_MAPPING.get(selected_tier, [])

        for crypto_symbol in self.crypto_list:
            is_active = crypto_symbol in active_cryptos_for_tier

            widgets_to_control = [
                self.crypto_widgets[crypto_symbol]['logo'],
                self.crypto_widgets[crypto_symbol]['ticker'],
                self.crypto_widgets[crypto_symbol]['network_power_wrapper'],
                self.crypto_widgets[crypto_symbol]['block_duration_input'],
                self.crypto_widgets[crypto_symbol]['block_reward_output'],
                self.crypto_widgets[crypto_symbol]['reward_per_block_output'],
                self.crypto_widgets[crypto_symbol]['daily_reward_output'],
                self.crypto_widgets[crypto_symbol]['weekly_reward_output1'],
                self.crypto_widgets[crypto_symbol]['monthly_reward_output'],
                self.crypto_widgets[crypto_symbol]['yearly_reward_output']
            ]

            for widget in widgets_to_control:
                widget.setVisible(is_active)

            widgets = self.crypto_widgets[crypto_symbol]
            if not is_active:
                widgets['rate'].blockSignals(True)
                widgets['unit'].blockSignals(True)
                widgets['block_duration_input'].blockSignals(True)
                widgets['block_reward_output'].blockSignals(True)

                widgets['rate'].setText("")
                widgets['unit'].setText("")
                widgets['block_duration_input'].setText(self.block_durations_defaults.get(crypto_symbol, "--"))
                widgets['block_reward_output'].setText(self.block_rewards_defaults.get(crypto_symbol, "--"))
                widgets['reward_per_block_output'].setText("00")
                widgets['daily_reward_output'].setText("00")
                widgets['weekly_reward_output1'].setText("00")
                widgets['monthly_reward_output'].setText("00")
                widgets['yearly_reward_output'].setText("00")
                widgets['logo'].clear()

                widgets['rate'].blockSignals(False)
                widgets['unit'].blockSignals(False)
                widgets['block_duration_input'].blockSignals(False)
                widgets['block_reward_output'].blockSignals(False)
            else:
                if widgets['logo'].pixmap() is None or widgets['logo'].pixmap().isNull():
                     self._load_crypto_icon(crypto_symbol)


    def update_crypto_list(self, detected_values, user_power_input_str, selected_tier):
        is_clear_image_event = (self.image_analyzer_widget.pasted_image is None) and (not detected_values)

        if not is_clear_image_event:
            self._last_detected_values.update(detected_values)
        else:
            self._last_detected_values = {}

        for crypto_symbol_key in self.crypto_list:
            widgets = self.crypto_widgets[crypto_symbol_key]
            widgets['rate'].blockSignals(True)
            widgets['unit'].blockSignals(True)
            widgets['block_duration_input'].blockSignals(True)
            widgets['block_reward_output'].blockSignals(True)

            widgets['rate'].setText("")
            widgets['unit'].setText("")
            widgets['logo'].clear()
            
            # --- Initialize Block Duration and Reward to their defaults first ---
            # These lines are crucial to ensure that if no saved data, "--" is the starting point.
            widgets['block_duration_input'].setText(self.block_durations_defaults.get(crypto_symbol_key, "--"))
            widgets['block_reward_output'].setText(self.block_rewards_defaults.get(crypto_symbol_key, "--"))
            
            widgets['reward_per_block_output'].setText("00")
            widgets['daily_reward_output'].setText("00")
            widgets['weekly_reward_output1'].setText("00")
            widgets['monthly_reward_output'].setText("00")
            widgets['yearly_reward_output'].setText("00")

            # --- Populating input fields (Rate, Unit, Duration, Reward) based on priority ---
            # Priority 1: OCR Data (for network rate/unit)
            if crypto_symbol_key in detected_values:
                info = detected_values[crypto_symbol_key]
                widgets['rate'].setText(str(info['rate']))
                widgets['unit'].setText(info.get('unit', ''))
                if self.image_analyzer_widget and self.image_analyzer_widget.pasted_image:
                    icon_box = self.image_analyzer_widget.find_icon_box(
                        self.image_analyzer_widget.pasted_image,
                        info['ticker_x'],
                        info['ticker_y'],
                        info['ticker_height']
                    )
                    if icon_box:
                        try:
                            x, y, w, h = icon_box
                            icon_img = self.image_analyzer_widget.pasted_image.crop((x, y, x+w, y+h))
                            icon_pixmap = self.pil_to_pixmap(icon_img)
                            scaled_pixmap = icon_pixmap.scaled(
                                widgets['logo'].size(),
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation
                            )
                            widgets['logo'].setPixmap(scaled_pixmap)
                        except Exception:
                            pass
            # Priority 2: Manually Pasted Data (for network rate/unit, if no OCR data)
            elif crypto_symbol_key in self._last_pasted_values:
                info = self._last_pasted_values[crypto_symbol_key]
                if info['rate']: widgets['rate'].setText(str(info['rate']))
                if info['unit']: widgets['unit'].setText(info.get('unit', ''))
            
            # Priority 3: User-Overridden (Saved) Block Duration/Reward
            # This applies if the saved data exists, overriding the "--" default already set.
            if crypto_symbol_key in self._user_overridden_block_data:
                user_saved_data = self._user_overridden_block_data[crypto_symbol_key]
                if user_saved_data.get('block_duration'):
                    widgets['block_duration_input'].setText(user_saved_data['block_duration'])
                if user_saved_data.get('block_reward'):
                    widgets['block_reward_output'].setText(user_saved_data['block_reward'])
            
            # Icon fallback if no custom icon was set by OCR
            if widgets['logo'].pixmap() is None or widgets['logo'].pixmap().isNull():
                 self._load_crypto_icon(crypto_symbol_key)

            widgets['rate'].blockSignals(False)
            widgets['unit'].blockSignals(False)
            widgets['block_duration_input'].blockSignals(False)
            widgets['block_reward_output'].blockSignals(False)

        self._update_crypto_row_visibility_only()
        
        for crypto_symbol in self.crypto_list:
            if crypto_symbol in TIER_CRYPTO_MAPPING.get(selected_tier, []):
                self._recalculate_row_rewards(crypto_symbol)
            else:
                pass

        self._is_initializing = False # NEW: Initialization complete, allow saving from now on

    def update_from_pasted_data(self, pasted_data):
        self._last_pasted_values.update(pasted_data)

        selected_tier = self.image_analyzer_widget.global_tier_combo.currentText()

        for crypto_symbol_key in self.crypto_list:
            widgets = self.crypto_widgets[crypto_symbol_key]
            widgets['rate'].blockSignals(True)
            widgets['unit'].blockSignals(True)

            if crypto_symbol_key in TIER_CRYPTO_MAPPING.get(selected_tier, []) and crypto_symbol_key not in self._last_detected_values:
                widgets['rate'].setText("")
                widgets['unit'].setText("")

                if crypto_symbol_key in pasted_data:
                    info = pasted_data[crypto_symbol_key]
                    if info['rate']: widgets['rate'].setText(str(info['rate']))
                    if info['unit']: widgets['unit'].setText(info.get('unit', ''))
                elif crypto_symbol_key in self._last_pasted_values:
                    info = self._last_pasted_values[crypto_symbol_key]
                    if info['rate']: widgets['rate'].setText(str(info['rate']))
                    if info['unit']: widgets['unit'].setText(info.get('unit', ''))
            
            widgets['rate'].blockSignals(False)
            widgets['unit'].blockSignals(False)
        
        for crypto_symbol in self.crypto_list:
            if crypto_symbol in TIER_CRYPTO_MAPPING.get(selected_tier, []):
                self._recalculate_row_rewards(crypto_symbol)


    def clear_pasted_data(self):
        self._last_pasted_values = {}
        self.update_crypto_list(self._last_detected_values, self.image_analyzer_widget.power_input_box.text(), self.image_analyzer_widget.global_tier_combo.currentText())


    def set_block_durations(self, durations_dict):
        for ticker, duration_text in durations_dict.items():
            if ticker in self.crypto_widgets:
                current_text = self.crypto_widgets[ticker]['block_duration_input'].text()
                if current_text != duration_text:
                    self.crypto_widgets[ticker]['block_duration_input'].blockSignals(True)
                    self.crypto_widgets[ticker]['block_duration_input'].setText(duration_text)
                    self.crypto_widgets[ticker]['block_duration_input'].blockSignals(False)
                    self._recalculate_row_rewards(ticker)
