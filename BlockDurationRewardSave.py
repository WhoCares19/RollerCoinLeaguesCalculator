import os
import json
import re

class BlockDataPersistenceManager:
    HEADER_TEXT = (
        "if you wish, change appropriate values here and it will be adjusted in the calculator too\n"
        "--------------------------------------------------------------------------------------\n"
    )

    def __init__(self, base_dir):
        self.config_dir = os.path.join(base_dir, "Calconfig")
        self.save_file_path = os.path.join(self.config_dir, "Save file for Block Reward and Duration.txt")
        self._ensure_config_dir_exists()

    def _ensure_config_dir_exists(self):
        if not os.path.exists(self.config_dir):
            try:
                os.makedirs(self.config_dir)
                print(f"DEBUG: BlockDataPersistenceManager: Created directory: {self.config_dir}")
            except OSError as e:
                print(f"ERROR: BlockDataPersistenceManager: Could not create config directory {self.config_dir}: {e}")

    def load_block_data(self):
        data = {}
        if os.path.exists(self.save_file_path):
            try:
                with open(self.save_file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                current_ticker = None
                for line in lines:
                    line_stripped_newline = line.strip('\n') # Strip newline, but preserve leading spaces for reward_match
                    if not line_stripped_newline or line_stripped_newline.startswith("if you wish,") or line_stripped_newline.startswith("----"):
                        continue

                    # Try to match "TICKER - block duration: VALUE" (or "TICKER - block duration: --")
                    duration_match = re.match(r'([a-zA-Z]+)\s+-\s+block duration:\s*(.*)', line_stripped_newline, re.IGNORECASE)
                    if duration_match:
                        current_ticker = duration_match.group(1).upper()
                        duration_value = duration_match.group(2).strip()
                        if current_ticker not in data:
                            data[current_ticker] = {}
                        data[current_ticker]['block_duration'] = duration_value
                        continue

                    # Match "      block reward: VALUE"
                    reward_match = re.match(r'\s{6}block reward:\s*(.*)', line_stripped_newline, re.IGNORECASE)
                    if reward_match and current_ticker:
                        reward_value = reward_match.group(1).strip()
                        if current_ticker not in data:
                            data[current_ticker] = {}
                        data[current_ticker]['block_reward'] = reward_value
                        continue

                print(f"DEBUG: BlockDataPersistenceManager: Loaded block data from {self.save_file_path}: {data}")
            except IOError as e:
                print(f"ERROR: BlockDataPersistenceManager: Failed to read from {self.save_file_path}: {e}")
            except Exception as e:
                print(f"ERROR: BlockDataPersistenceManager: Error parsing {self.save_file_path}: {e}")
        else:
            print(f"DEBUG: BlockDataPersistenceManager: Save file not found at {self.save_file_path}. Returning empty data.")
        return data

    def save_block_data(self, data_to_save):
        self._ensure_config_dir_exists()
        try:
            with open(self.save_file_path, 'w', encoding='utf-8') as f:
                f.write(self.HEADER_TEXT)
                
                sorted_tickers = sorted(data_to_save.keys())

                for ticker in sorted_tickers:
                    block_data = data_to_save[ticker]
                    
                    duration = block_data.get('block_duration', '')
                    reward = block_data.get('block_reward', '')

                    # Only write an entry for the ticker if there's *any* data (duration or reward)
                    if duration or reward:
                        # Always write the "ticker - block duration" line.
                        # If duration is empty, use "--" to maintain a consistent format for loading.
                        display_duration = duration if duration else "--"
                        f.write(f"{ticker} - block duration: {display_duration}\n")
                        
                        if reward:
                            f.write(f"      block reward: {reward}\n")
                        
                        f.write("\n") # Add a blank line between crypto entries
                        
            print(f"DEBUG: BlockDataPersistenceManager: Saved block data to {self.save_file_path}")
        except IOError as e:
            print(f"ERROR: BlockDataPersistenceManager: Failed to write to {self.save_file_path}: {e}")
