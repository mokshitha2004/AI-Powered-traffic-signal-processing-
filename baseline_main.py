#!/usr/bin/env python3
"""
baseline_main.py
Fixed-Time Traffic Signal Controller for SUMO
Outputs:
 - performance_baseline.csv
 - frame.png
Author: Mokshitha (Final Clean Version)
"""

import traci
import os
import time
import pandas as pd

# ---------------- PATH SETTINGS ----------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SUMO_CONFIG = os.path.join(BASE_DIR, "simulation.sumocfg")
FRAME_PATH = os.path.join(BASE_DIR, "frame.png")
OUT_CSV = os.path.join(BASE_DIR, "performance_baseline.csv")

TLS_ID = "center"     # your real TLS ID

GREEN_TIME = 15
YELLOW_TIME = 3

DIRECTIONS = ["North", "East", "South", "West"]


def detect_direction(lane_id):
    lid = lane_id.lower()
    if "north" in lid or "_n" in lid or lid.startswith("n"):
        return "North"
    if "south" in lid or "_s" in lid or lid.startswith("s"):
        return "South"
    if "east" in lid or "_e" in lid or lid.startswith("e"):
        return "East"
    if "west" in lid or "_w" in lid or lid.startswith("w"):
        return "West"
    return "North"


def run_baseline():
    print("\nStarting Baseline Fixed-Time Simulation...\n")

    traci.start([
        "sumo-gui",
        "-c", SUMO_CONFIG,
        "--start",
        "--quit-on-end"
    ])

    lanes = traci.trafficlight.getControlledLanes(TLS_ID)
    lanes = list(dict.fromkeys(lanes))  # keep order

    lane_to_dir = {ln: detect_direction(ln) for ln in lanes}

    try:
        view = traci.gui.getIDList()[0]
    except:
        view = None

    step = 0
    queue_history = {d: [] for d in DIRECTIONS}
    total_vehicles = set()

    programs = traci.trafficlight.getCompleteRedYellowGreenDefinition(TLS_ID)
    phases = programs[0].phases
    green_phases = [i for i, p in enumerate(phases) if "G" in p.state]

    if not green_phases:
        print("ERROR: No green phases detected!")
        traci.close()
        return

    while traci.simulation.getMinExpectedNumber() > 0:
        for idx in green_phases:

            traci.trafficlight.setPhase(TLS_ID, idx)

            for _ in range(GREEN_TIME):
                traci.simulationStep()
                step += 1

                lane_counts = {
                    ln: traci.lane.getLastStepVehicleNumber(ln)
                    for ln in lanes
                }

                dir_counts = {d: 0 for d in DIRECTIONS}
                for ln, c in lane_counts.items():
                    dir_counts[lane_to_dir[ln]] += c

                for d in DIRECTIONS:
                    queue_history[d].append(dir_counts[d])

                for vid in traci.vehicle.getIDList():
                    total_vehicles.add(vid)

                if view and step % 5 == 0:
                    traci.gui.screenshot(view, FRAME_PATH)

            for _ in range(YELLOW_TIME):
                traci.simulationStep()
                step += 1

    traci.close()

    rows = []
    for d in DIRECTIONS:
        avg_q = sum(queue_history[d]) / len(queue_history[d])
        rows.append({
            "region": d,
            "avg_queue": round(avg_q, 2),
            "throughput": len(total_vehicles),
            "avg_green": GREEN_TIME
        })

    pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8")

    print("Baseline Simulation Completed Successfully!")
    print("Saved:", OUT_CSV)


if __name__ == "__main__":
    run_baseline()
