def move_user(user: dict, speed_scale: float) -> None:
    user["x"] += user["dx"] * speed_scale * user["speed"]
    user["y"] += user["dy"] * speed_scale * user["speed"]
    if user["x"] >= 100 or user["x"] <= 0:
        user["dx"] *= -1
        user["x"] = min(100, max(0, user["x"]))
    if user["y"] >= 100 or user["y"] <= 0:
        user["dy"] *= -1
        user["y"] = min(100, max(0, user["y"]))
