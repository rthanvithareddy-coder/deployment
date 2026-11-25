def calculate_metrics(events: list, users: int) -> dict:
    conventional = [event for event in events if event["algorithm"] == "conventional"]
    mobility = [event for event in events if event["algorithm"] == "mobility"]

    def summarize(items):
        handovers = [event for event in items if event["type"] in ("handover", "failed")]
        success = sum(1 for event in handovers if event["type"] == "handover")
        failed = sum(1 for event in handovers if event["type"] == "failed")
        total = success + failed
        unnecessary = sum(1 for event in handovers if event.get("unnecessary"))
        delays = [event["delay_ms"] for event in handovers if event.get("delay_ms") is not None]
        interruptions = [event["interruption_ms"] for event in handovers if event.get("interruption_ms") is not None]
        throughput = max(0.0, round(success * 1.8 + users * 0.25 - failed * 0.6, 2))
        return {
            "handover_success_rate": round(success / total * 100, 1) if total else 100.0,
            "handover_failure_rate": round(failed / total * 100, 1) if total else 0.0,
            "average_handover_delay_ms": round(sum(delays) / len(delays), 1) if delays else 0.0,
            "unnecessary_handover_count": unnecessary,
            "average_throughput_mbps": throughput,
            "connection_interruption_ms": round(sum(interruptions) / len(interruptions), 1) if interruptions else 0.0,
        }

    return {"conventional": summarize(conventional), "mobility": summarize(mobility)}
