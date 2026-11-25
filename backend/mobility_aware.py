from backend.signal import normalized_quality


def choose_mobility(user: dict, towers: list, signals: dict, weights: dict, stability_margin: float,
                    users: list) -> tuple[str | None, dict, str]:
    eligible = [tower for tower in towers if tower["enabled"]]
    scores = {}
    user_x, user_y = user["x"], user["y"]
    dx, dy = user["dx"], user["dy"]
    for tower in eligible:
        load = sum(1 for item in users if item.get("connected_tower_mobility") == tower["id"])
        capacity = tower["capacity"]
        c = max(0.0, 1 - load / capacity)
        q = normalized_quality(signals.get(tower["id"], -120))
        projected_x = user_x + dx
        projected_y = user_y + dy
        distance_now = ((tower["x"] - user_x) ** 2 + (tower["y"] - user_y) ** 2) ** 0.5
        distance_next = ((tower["x"] - projected_x) ** 2 + (tower["y"] - projected_y) ** 2) ** 0.5
        m = max(0.0, min(1.0, 0.5 + (distance_now - distance_next) / 20))
        score = weights["signal"] * q + weights["capacity"] * c + weights["mobility"] * m
        scores[tower["id"]] = {"signal": round(q, 3), "capacity": round(c, 3),
                               "mobility": round(m, 3), "score": round(score, 3)}
    if not eligible:
        return None, scores, "failed"
    ranked = sorted(scores, key=lambda tower_id: scores[tower_id]["score"], reverse=True)
    best = ranked[0]
    current = user.get("connected_tower_mobility")
    if current in scores and best != current:
        if scores[current]["score"] + stability_margin / 100 >= scores[best]["score"]:
            return current, scores, "maintain"
    if best and sum(1 for item in users if item.get("connected_tower_mobility") == best) >= \
            next(tower["capacity"] for tower in eligible if tower["id"] == best):
        ranked = [tower_id for tower_id in ranked if
                  sum(1 for item in users if item.get("connected_tower_mobility") == tower_id) <
                  next(tower["capacity"] for tower in eligible if tower["id"] == tower_id)]
        if not ranked:
            return None, scores, "failed"
        best = ranked[0]
    return best, scores, "handover" if current and best != current else "initial"
