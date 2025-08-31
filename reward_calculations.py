import math
import re # Import re for parsing duration strings

# Import the convert_power_to_ghs function and UNIT_MULTIPLIERS from Leagues_Info.py
from Leagues_Info import convert_power_to_ghs, UNIT_MULTIPLIERS

def parse_duration_to_seconds(duration_str):
    """
    Parses a duration string (e.g., "10 Min 4 Sec", "40 min 5 sec", "00")
    into total seconds.

    Args:
        duration_str (str): The duration string from the UI.

    Returns:
        float: The total duration in seconds. Returns 0.0 if parsing fails or input is "00".
    """
    if duration_str.strip() == "00":
        return 0.0

    total_seconds = 0.0
    # Modified regex to allow 'm' for minutes and 's' for seconds, in addition to full words/abbreviations
    match = re.search(r'(\d+)\s*(m|min(?:ute)?s?)\s*(\d+)\s*(s|sec(?:ond)?s?)', duration_str, re.IGNORECASE)
    if match:
        minutes = int(match.group(1))
        # Group 2 is the minute unit ('m', 'min', etc.), not used for value
        seconds = int(match.group(3)) # This needs to be group 3 now, as group 2 is the unit
        total_seconds = (minutes * 60) + seconds
    else:
        # Fallback for simple number input, assume it's seconds if no 'min'/'sec' is found
        single_num_match = re.search(r'(\d+\.?\d*)', duration_str)
        if single_num_match:
            total_seconds = float(single_num_match.group(1))
            print(f"Warning: Ambiguous duration format '{duration_str}'. Assuming it's in seconds: {total_seconds}")
        else:
            print(f"Warning: Could not parse duration string '{duration_str}'. Returning 0.0.")
            return 0.0 # Return 0.0 if parsing fails

    return total_seconds

def calculate_reward_per_block(user_power_str, user_unit, coin_block_reward_str, network_hashrate_str, network_unit):
    """
    Calculates the estimated reward for mining one block based on user's power
    and the network's total hashrate.

    Args:
        user_power_str (str): The user's hashing power as a string (e.g., "1.546").
        user_unit (str): The unit of user's power (e.g., "Eh/s").
        coin_block_reward_str (str): The reward for mining one block as a string (e.g., "54").
        network_hashrate_str (str): The total network hashrate as a string (e.g., "11.081").
        network_unit (str): The unit of network hashrate (e.g., "Zh/s").

    Returns:
        float: The estimated reward for mining one block. Returns 0.0 if network hashrate is zero.
    """
    print(f"DEBUG: calculate_reward_per_block received: user_power_str='{user_power_str}', user_unit='{user_unit}', coin_block_reward_str='{coin_block_reward_str}', network_hashrate_str='{network_hashrate_str}', network_unit='{network_unit}'")

    user_power_ghs = convert_power_to_ghs(user_power_str, user_unit, UNIT_MULTIPLIERS)
    network_hashrate_ghs = convert_power_to_ghs(network_hashrate_str, network_unit, UNIT_MULTIPLIERS)
    
    # Safely convert coin_block_reward_str to float, defaulting to 0.0 if empty or invalid
    try:
        coin_block_reward = float(coin_block_reward_str)
    except ValueError:
        coin_block_reward = 0.0
        print(f"Warning: Invalid coin_block_reward_str '{coin_block_reward_str}'. Using 0.0.")

    print(f"DEBUG: calculate_reward_per_block: user_power_ghs={user_power_ghs}")
    print(f"DEBUG: calculate_reward_per_block: network_hashrate_ghs={network_hashrate_ghs}")
    print(f"DEBUG: calculate_reward_per_block: coin_block_reward={coin_block_reward}")

    if network_hashrate_ghs == 0:
        print("Warning: Network hashrate in Gh/s is zero. Returning 0.0 reward.")
        return 0.0

    # Calculate your share of the network's hashrate
    share_of_network = user_power_ghs / network_hashrate_ghs
    print(f"DEBUG: calculate_reward_per_block: share_of_network={share_of_network}")

    # Calculate the reward per block
    reward = share_of_network * coin_block_reward
    print(f"DEBUG: calculate_reward_per_block: final reward={reward}")
    return reward

def calculate_blocks_per_day(block_duration_str):
    """
    Calculates the average number of blocks mined per day on the network.

    Args:
        block_duration_str (str): The average time to mine one block (e.g., "10 Min 4 Sec").

    Returns:
        float: The average number of blocks mined per day. Returns 0.0 if duration is invalid.
    """
    block_duration_seconds = parse_duration_to_seconds(block_duration_str)
    print(f"DEBUG: calculate_blocks_per_day: block_duration_seconds={block_duration_seconds}")

    if block_duration_seconds > 0:
        return (24 * 60 * 60) / block_duration_seconds
    return 0.0

def calculate_reward_per_day(reward_per_block, blocks_per_day):
    """
    Calculates the estimated reward per day.

    Args:
        reward_per_block (float): The estimated reward for mining one block.
        blocks_per_day (float): The average number of blocks mined per day on the network.

    Returns:
        float: The estimated reward per day.
    """
    return reward_per_block * blocks_per_day

def calculate_reward_per_week(reward_per_day):
    """
    Calculates the estimated reward per week.

    Args:
        reward_per_day (float): The estimated reward per day.

    Returns:
        float: The estimated reward per week.
    """
    return reward_per_day * 7

def calculate_reward_per_month(reward_per_day):
    """
    Calculates the estimated reward per month (approx. 30.44 days).

    Args:
        reward_per_day (float): The estimated reward per day.

    Returns:
        float: The estimated reward per month.
    """
    return reward_per_day * 30.44 # Average days in a month

def calculate_reward_per_year(reward_per_day):
    """
    Calculates the estimated reward per year (approx. 365.25 days).

    Args:
        reward_per_day (float): The estimated reward per day.

    Returns:
        float: The estimated reward per year.
    """
    return reward_per_day * 365.25 # Average days in a year (accounting for leap years)
