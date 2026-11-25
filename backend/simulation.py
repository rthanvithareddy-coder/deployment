import asyncio
import random
import time
from datetime import datetime, timezone

from backend.mobility import move_user
from backend.network import calculate_user_signals
from backend.conventional import choose_conventional
from backend.mobility_aware import choose_mobility
from backend.metrics import calculate_metrics
from backend.database import save_experiment


class Simulation:
    def __init__(self):
        self.running = False
        self.started_at = None
        self.elapsed_seconds = 0.0
        self.tick = 0
        self.settings = {
            "user_count": 12,
            "speed": 1.0,
            "handover_threshold": -90,
            "stability_margin": 4,
            "weights": {"signal": 0.5, "capacity": 0.3, "mobility": 0.2},
            "scenario": "Normal Mobility",
        }
        self.towers = [
            {"id": "A", "name": "Tower A", "x": 25, "y": 50, "capacity": 20, "enabled": True},
            {"id": "B", "name": "Tower B", "x": 50, "y": 25, "capacity": 20, "enabled": True},
            {"id": "C", "name": "Tower C", "x": 75, "y": 55, "capacity": 20, "enabled": True},
        ]
        self.users = []
        self.events = []
        self.history_samples = []
        self._ensure_users()

    def _ensure_users(self):
        target = int(self.settings["user_count"])
        while len(self.users) < target:
            index = len(self.users)
            angle = random.uniform(0, 2 * 3.141592653589793)
            self.users.append({
                "id": f"U{index + 1}",
                "x": random.uniform(5, 95),
                "y": random.uniform(5, 95),
                "dx": 0.35 * (1 if random.random() > 0.5 else -1),
                "dy": 0.20 * (1 if random.random() > 0.5 else -1),
                "speed": self.settings["speed"],
                "connected_tower_conventional": None,
                "connected_tower_mobility": None,
                "signal_conventional": -120,
                "signal_mobility": -120,
                "factors": {},
            })
        if len(self.users) > target:
            self.users = self.users[:target]

    def reset(self):
        self.running = False
        self.elapsed_seconds = 0.0
        self.tick = 0
        self.events = []
        self.history_samples = []
        self.users = []
        self._ensure_users()
        self._apply_scenario(self.settings["scenario"])

    def update_settings(self, data: dict):
        self.settings.update({key: value for key, value in data.items() if value is not None})
        if "speed" in data:
            for user in self.users:
                user["speed"] = float(data["speed"])
        if "weights" in data:
            total = sum(float(value) for value in data["weights"].values())
            if total <= 0:
                raise ValueError("Mobility-aware weights must have a positive sum")
            self.settings["weights"] = {key: float(value) / total for key, value in data["weights"].items()}
        if "user_count" in data:
            self._ensure_users()

    def set_scenario(self, name: str):
        self.settings["scenario"] = name
        self._apply_scenario(name)

    def _apply_scenario(self, name: str):
        if name == "High Congestion":
            self.settings["user_count"] = max(40, int(self.settings["user_count"]))
        elif name == "High-Speed Mobility":
            self.settings["speed"] = max(3.0, float(self.settings["speed"]))
        elif name == "Tower Failure":
            for tower in self.towers:
                tower["enabled"] = tower["id"] != "B"
        elif name == "Combined Scenario":
            self.settings["user_count"] = max(50, int(self.settings["user_count"]))
            self.settings["speed"] = max(3.5, float(self.settings["speed"]))
            for tower in self.towers:
                tower["enabled"] = tower["id"] != "B"
        else:
            for tower in self.towers:
                tower["enabled"] = True
        self.settings["speed"] = float(self.settings["speed"])
        self._ensure_users()
        for user in self.users:
            user["speed"] = self.settings["speed"]

    def start(self):
        self.running = True
        if self.started_at is None:
            self.started_at = time.monotonic()

    def pause(self):
        self.running = False

    def resume(self):
        self.running = True

    def step(self):
        if not self.running:
            return
        self.tick += 1
        self.elapsed_seconds += 0.5
        speed_scale = 0.35
        average_signal_c = []
        average_signal_m = []
        for user in self.users:
            move_user(user, speed_scale)
            signals = calculate_user_signals(user, self.towers)
            current_c = user["connected_tower_conventional"]
            current_m = user["connected_tower_mobility"]
            conventional_choice, conventional_status = choose_conventional(
                user, self.towers, signals, self.settings["handover_threshold"],
                self.settings["stability_margin"], self.users)
            mobility_choice, factor_scores, mobility_status = choose_mobility(
                user, self.towers, signals, self.settings["weights"],
                self.settings["stability_margin"], self.users)

            if conventional_choice != current_c:
                if conventional_choice is None:
                    event_type = "failed"
                else:
                    event_type = "handover"
                self.events.append({
                    "algorithm": "conventional", "type": event_type, "user": user["id"],
                    "from": current_c, "to": conventional_choice, "delay_ms": 40,
                    "interruption_ms": 0 if event_type == "handover" else 120,
                    "unnecessary": conventional_status == "handover" and current_c is not None and
                                   signals.get(conventional_choice, -120) <= signals.get(current_c, -120),
                })
            if mobility_choice != current_m:
                if mobility_choice is None:
                    event_type = "failed"
                else:
                    event_type = "handover"
                self.events.append({
                    "algorithm": "mobility", "type": event_type, "user": user["id"],
                    "from": current_m, "to": mobility_choice, "delay_ms": 28,
                    "interruption_ms": 0 if event_type == "handover" else 80,
                    "unnecessary": mobility_status == "handover" and current_m is not None and
                                   factor_scores.get(mobility_choice, {}).get("score", 0) <
                                   factor_scores.get(current_m, {}).get("score", 0),
                })

            user["connected_tower_conventional"] = conventional_choice
            user["connected_tower_mobility"] = mobility_choice
            user["signal_conventional"] = signals.get(conventional_choice, -120) if conventional_choice else -120
            user["signal_mobility"] = signals.get(mobility_choice, -120) if mobility_choice else -120
            user["factors"] = factor_scores
            average_signal_c.append(user["signal_conventional"])
            average_signal_m.append(user["signal_mobility"])
        metrics = calculate_metrics(self.events, len(self.users))
        average_c = round(sum(average_signal_c) / len(average_signal_c), 1) if average_signal_c else -120
        average_m = round(sum(average_signal_m) / len(average_signal_m), 1) if average_signal_m else -120
        utilization = {}
        for tower in self.towers:
            utilization[tower["id"]] = {
                "conventional": self.tower_utilization(tower, "conventional"),
                "mobility": self.tower_utilization(tower, "mobility"),
            }
        self.history_samples.append({
            "tick": self.tick,
            "signal_conventional": average_c,
            "signal_mobility": average_m,
            "conventional_handover_count": sum(
                1 for event in self.events if event["algorithm"] == "conventional" and event["type"] == "handover"),
            "mobility_handover_count": sum(
                1 for event in self.events if event["algorithm"] == "mobility" and event["type"] == "handover"),
        })
        self.history_samples = self.history_samples[-120:]

    def tower_utilization(self, tower: dict, algorithm: str):
        key = f"connected_tower_{algorithm}"
        load = sum(1 for user in self.users if user.get(key) == tower["id"])
        return round(min(100.0, load / tower["capacity"] * 100), 1)

    def state(self):
        metrics = calculate_metrics(self.events, len(self.users))
        avg_c = [user["signal_conventional"] for user in self.users]
        avg_m = [user["signal_mobility"] for user in self.users]
        user_signals = []
        for user in self.users:
            signals = calculate_user_signals(user, self.towers)
            user_signals.append({"id": user["id"], "x": round(user["x"], 2), "y": round(user["y"], 2),
                                 "speed": user["speed"],
                                 "connected_conventional": user["connected_tower_conventional"],
                                 "connected_mobility": user["connected_tower_mobility"],
                                 "signal_conventional": user["signal_conventional"],
                                 "signal_mobility": user["signal_mobility"],
                                 "factor_scores": user["factors"],
                                 "tower_signals": signals})
        tower_states = []
        congestion_values = []
        for tower in self.towers:
            conventional_load = sum(1 for user in self.users if user["connected_tower_conventional"] == tower["id"])
            mobility_load = sum(1 for user in self.users if user["connected_tower_mobility"] == tower["id"])
            congestion = round(max(
                conventional_load / tower["capacity"],
                mobility_load / tower["capacity"]) * 100, 1)
            congestion_values.append(congestion)
            tower_states.append({
                **tower,
                "conventional_load": conventional_load,
                "mobility_load": mobility_load,
                "congestion": congestion,
            })
        return {
            "running": self.running,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "tick": self.tick,
            "settings": self.settings,
            "towers": tower_states,
            "users": user_signals,
            "events": self.events[-30:][::-1],
            "history": self.history_samples,
            "metrics": metrics,
            "summary": {
                "active_users": len(self.users),
                "available_towers": sum(1 for tower in self.towers if tower["enabled"]),
                "connected_users": sum(1 for user in self.users
                                       if user["connected_tower_conventional"] or user["connected_tower_mobility"]),
                "total_handovers": sum(1 for event in self.events if event["type"] == "handover"),
                "successful_handovers": sum(1 for event in self.events if event["type"] == "handover"),
                "failed_handovers": sum(1 for event in self.events if event["type"] == "failed"),
                "average_signal_dbm": round(
                    sum(avg_c + avg_m) / max(1, len(avg_c + avg_m)), 1),
                "network_congestion": "High" if max(congestion_values, default=0) >= 85 else
                                      "Moderate" if max(congestion_values, default=0) >= 60 else "Low",
            },
        }

    def save_experiment(self, name: str):
        state = self.state()
        metrics = state["metrics"]
        record = {
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": state["elapsed_seconds"],
            "user_count": len(self.users),
            "tower_count": sum(1 for tower in self.towers if tower["enabled"]),
            "scenario": self.settings["scenario"],
            "conventional_results": metrics["conventional"],
            "mobility_results": metrics["mobility"],
        }
        experiment_id = save_experiment(record)
        return experiment_id, record
