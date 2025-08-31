import re

TIER_CRYPTO_MAPPING = {
    "Bronze I": ["RLT", "RST", "BTC", "LTC"],
    "Bronze II": ["RLT", "RST", "BTC", "LTC", "BNB"],
    "Bronze III": ["RLT", "RST", "BTC", "LTC", "BNB", "POL"],
    "Silver I": ["RLT", "RST", "BTC", "LTC", "BNB", "POL", "XRP"],
    "Silver II": ["RLT", "RST", "BTC", "LTC", "BNB", "POL", "XRP", "DOGE"],
    "Silver III": ["RLT", "RST", "BTC", "LTC", "BNB", "POL", "XRP", "DOGE", "ETH"],
    "Gold I": ["RLT", "RST", "BTC", "LTC", "BNB", "POL", "XRP", "DOGE", "ETH", "TRX"],
    "Gold II": ["RLT", "RST", "BTC", "LTC", "BNB", "POL", "XRP", "DOGE", "ETH", "TRX", "SOL"],
    "Gold III": ["RLT", "RST", "BTC", "LTC", "BNB", "POL", "XRP", "DOGE", "ETH", "TRX", "SOL"],
    "Platinum I": ["RLT", "RST", "BTC", "LTC", "BNB", "POL", "XRP", "DOGE", "ETH", "TRX", "SOL"],
    "Platinum II": ["RLT", "RST", "BTC", "LTC", "BNB", "POL", "XRP", "DOGE", "ETH", "TRX", "SOL"],
    "Platinum III": ["RLT", "RST", "BTC", "LTC", "BNB", "POL", "XRP", "DOGE", "ETH", "TRX", "SOL"],
    "Diamond I": ["RST", "BTC", "LTC", "BNB", "POL", "XRP", "DOGE", "ETH", "TRX", "SOL"],
    "Diamond II": ["RST", "BTC", "LTC", "BNB", "POL", "XRP", "DOGE", "ETH", "TRX", "SOL"],
    "Diamond III": ["RST", "BTC", "LTC", "BNB", "POL", "XRP", "DOGE", "ETH", "TRX", "SOL"]
}

UNIT_MULTIPLIERS = {
    "Gh/s": 1,
    "Th/s": 1000,
    "Ph/s": 1000**2,  # 1,000,000
    "Eh/s": 1000**3,  # 1,000,000,000
    "Zh/s": 1000**4   # 1,000,000,000,000
}

# === UPDATED TIER_POWER_RANGES WITH ROLLERCOIN'S SPECIFIC VALUES ===
TIER_POWER_RANGES = {
    "Bronze I": (0 * UNIT_MULTIPLIERS["Gh/s"], 5 * UNIT_MULTIPLIERS["Ph/s"]),
    "Bronze II": (5 * UNIT_MULTIPLIERS["Ph/s"], 30 * UNIT_MULTIPLIERS["Ph/s"]),
    "Bronze III": (30 * UNIT_MULTIPLIERS["Ph/s"], 100 * UNIT_MULTIPLIERS["Ph/s"]),
    "Silver I": (100 * UNIT_MULTIPLIERS["Ph/s"], 200 * UNIT_MULTIPLIERS["Ph/s"]),
    "Silver II": (200 * UNIT_MULTIPLIERS["Ph/s"], 500 * UNIT_MULTIPLIERS["Ph/s"]),
    "Silver III": (500 * UNIT_MULTIPLIERS["Ph/s"], 1 * UNIT_MULTIPLIERS["Eh/s"]),
    "Gold I": (1 * UNIT_MULTIPLIERS["Eh/s"], 2 * UNIT_MULTIPLIERS["Eh/s"]),
    "Gold II": (2 * UNIT_MULTIPLIERS["Eh/s"], 5 * UNIT_MULTIPLIERS["Eh/s"]),
    "Gold III": (5 * UNIT_MULTIPLIERS["Eh/s"], 15 * UNIT_MULTIPLIERS["Eh/s"]),
    "Platinum I": (15 * UNIT_MULTIPLIERS["Eh/s"], 50 * UNIT_MULTIPLIERS["Eh/s"]),
    "Platinum II": (50 * UNIT_MULTIPLIERS["Eh/s"], 100 * UNIT_MULTIPLIERS["Eh/s"]),
    "Platinum III": (100 * UNIT_MULTIPLIERS["Eh/s"], 200 * UNIT_MULTIPLIERS["Eh/s"]),
    "Diamond I": (200 * UNIT_MULTIPLIERS["Eh/s"], 400 * UNIT_MULTIPLIERS["Eh/s"]),
    "Diamond II": (400 * UNIT_MULTIPLIERS["Eh/s"], 10 * UNIT_MULTIPLIERS["Zh/s"]),
    "Diamond III": (10 * UNIT_MULTIPLIERS["Zh/s"], float('inf')) # "above" means no upper limit
}
# ====================================================================

def convert_power_to_ghs(power_value_str, unit, unit_multipliers_dict):
    try:
        match = re.search(r'(\d[\d,]*\.?\d*)\s*([a-zA-Z/]+)?', power_value_str, re.IGNORECASE)
        
        if match:
            power_numeric_str = match.group(1).replace(',', '')
            detected_unit_str = match.group(2)

            power_float = float(power_numeric_str)

            # Start with the unit passed as argument (e.g., from the QComboBox)
            effective_unit = unit 

            # Attempt to normalize the provided unit (from dropdown)
            if effective_unit:
                effective_unit_upper = effective_unit.upper()
                if effective_unit_upper in ["G", "GH/S"]: effective_unit = "Gh/s"
                elif effective_unit_upper in ["T", "TH/S"]: effective_unit = "Th/s"
                elif effective_unit_upper in ["P", "PH/S"]: effective_unit = "Ph/s"
                elif effective_unit_upper in ["E", "EH/S"]: effective_unit = "Eh/s"
                elif effective_unit_upper in ["Z", "ZH/S"]: effective_unit = "Zh/s"
            
            # Attempt to normalize the detected unit (from OCR/text input).
            # If a unit is detected here, it *overrides* the dropdown unit for that specific value.
            if detected_unit_str: 
                detected_unit_upper = detected_unit_str.upper()
                if detected_unit_upper in ["G", "GH/S"]: effective_unit = "Gh/s"
                elif detected_unit_upper in ["T", "TH/S"]: effective_unit = "Th/s"
                elif detected_unit_upper in ["P", "PH/S"]: effective_unit = "Ph/s"
                elif detected_unit_upper in ["E", "EH/S"]: effective_unit = "Eh/s"
                elif detected_unit_upper in ["Z", "ZH/S"]: effective_unit = "Zh/s"
                # If a unit was detected in the string, and it wasn't one of the known ones,
                # then ensure effective_unit reflects that it's unrecognized.
                else:
                    effective_unit = detected_unit_str # Keep the raw detected unit to fail the check below

            # Check if the effective_unit (after all normalization attempts) is a valid key.
            # If not, return 0.0, which will cause calculations to output "00".
            if effective_unit not in unit_multipliers_dict:
                print(f"Warning: Unrecognized unit '{effective_unit}'. Treating power as 0 Gh/s.")
                return 0.0

            multiplier = unit_multipliers_dict[effective_unit] # Now safely get the multiplier

            return power_float * multiplier
        else:
            # If no numeric match is found at all (e.g., input is just "abc" or empty)
            return 0.0
    except ValueError:
        # If the numeric part cannot be converted to float (e.g., "1.2.3" or "invalid")
        return 0.0
    except Exception as e:
        # Catch any other unexpected errors during conversion
        print(f"Error in convert_power_to_ghs: {e}")
        return 0.0

def determine_tier_from_power(user_power_ghs, tier_power_ranges_dict):
    for tier, (lower_bound_ghs, upper_bound_ghs) in tier_power_ranges_dict.items():
        epsilon = 1e-9 # Small value to handle floating point inaccuracies at boundaries
        if lower_bound_ghs - epsilon <= user_power_ghs < upper_bound_ghs - epsilon:
            return tier
    return None
