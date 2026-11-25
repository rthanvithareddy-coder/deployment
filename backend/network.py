from backend.signal import calculate_signal


def tower_load(tower_id: str, users: list, towers: list, algorithm: str) -> int:
    connection_key = f"connected_tower_{algorithm}"
    return sum(1 for user in users if user.get(connection_key) == tower_id)


def utilization(tower: dict, users: list, algorithm: str) -> float:
    load = tower_load(tower["id"], users, [tower], algorithm)
    return round(min(100.0, load / tower["capacity"] * 100), 1)


def available_towers(towers: list) -> list:
    return [tower for tower in towers if tower["enabled"]]


def calculate_user_signals(user: dict, towers: list) -> dict:
    return {
        tower["id"]: calculate_signal(tower["x"], tower["y"], user["x"], user["y"])
        for tower in towers if tower["enabled"]
    }
