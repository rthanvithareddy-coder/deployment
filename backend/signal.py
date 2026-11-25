import math


def calculate_signal(tx_x: float, tx_y: float, rx_x: float, rx_y: float) -> float:
    """Distance-based illustrative simulation model: -45 dBm at 1 unit, -25 dBm per decade."""
    distance = max(1.0, math.hypot(tx_x - rx_x, tx_y - rx_y))
    return round(-45 - 25 * math.log10(distance), 1)


def normalized_quality(signal_dbm: float) -> float:
    return max(0.0, min(1.0, (signal_dbm + 110) / 55))
