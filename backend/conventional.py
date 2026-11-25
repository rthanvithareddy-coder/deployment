def choose_conventional(user: dict, towers: list, signals: dict, threshold: float, stability_margin: float,
                        users: list) -> tuple[str | None, str]:
    current = user.get("connected_tower_conventional")
    eligible = [tower for tower in towers if tower["enabled"]]
    if current:
        current_tower = next((tower for tower in eligible if tower["id"] == current), None)
        if current_tower:
            current_signal = signals.get(current, -120)
            if current_signal >= threshold:
                return current, "maintain"
    candidates = sorted(
        eligible,
        key=lambda tower: (
            tower_load(tower["id"], users, eligible, "conventional") >= tower["capacity"],
            -signals.get(tower["id"], -120),
        ),
    )
    candidates = [tower for tower in candidates
                  if tower_load(tower["id"], users, eligible, "conventional") < tower["capacity"]]
    if not candidates:
        return None, "failed"
    best = candidates[0]
    best_signal = signals.get(best["id"], -120)
    if best_signal < threshold:
        return None, "failed"
    if current and best["id"] != current:
        current_signal = signals.get(current, -120)
        if best_signal < current_signal + stability_margin:
            return current, "maintain"
    return best["id"], "handover" if current and best["id"] != current else "initial"


def tower_load(tower_id: str, users: list, towers: list, algorithm: str) -> int:
    return sum(1 for user in users if user.get("connected_tower_conventional") == tower_id)
