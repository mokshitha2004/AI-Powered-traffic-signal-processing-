try:
    view = traci.gui.getIDList()[0]
except Exception:
    view = None

import sys
# --- FIX WINDOWS UNICODE ERROR ---
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except:
    pass
# ---------------------------------
# ==========================================================
#   ADAPTIVE TRAFFIC SIGNAL WITH FAIRNESS + DENSITY LOGIC
#   Debug logs saved to ai_cycle_debug.csv (Option B)
# ==========================================================

import os
import time
import csv
import random
import traceback
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SUMO_CONFIG = os.path.join(BASE_DIR, "simulation.sumocfg")
NET_FILE = os.path.join(BASE_DIR, "network.net.xml")
ROUTE_FILE = os.path.join(BASE_DIR, "routes.rou.xml")
BASE_CSV = os.path.join(BASE_DIR, "performance_baseline.csv")
AI_CSV = os.path.join(BASE_DIR, "performance_ai.csv")
DEBUG_CSV = os.path.join(BASE_DIR, "ai_cycle_debug.csv")
FRAME_PATH = os.path.join(BASE_DIR, "frame.png")
DASH_PNG = os.path.join(BASE_DIR, "dashboard.png")
YOLO_MODEL_PATH = os.path.join(BASE_DIR, "yolov8n.pt")

try:
    import traci
    from traci import trafficlight
except:
    raise RuntimeError("Install SUMO & set SUMO_HOME")

import pandas as pd
import matplotlib.pyplot as plt


# ==========================================================
# CONFIG
# ==========================================================
SUMO_BINARY = "sumo-gui"
SUMO_CONFIG = "simulation.sumocfg"
NET_FILE = "network.net.xml"
ROUTE_FILE = "routes.rou.xml"
TLS_ID = "center"

SLEEP_BETWEEN_STEPS = 0.004
YOLO_EVERY_N_STEPS = 10
MAX_STEPS = 1200

BASE_CSV = "performance_baseline.csv"
AI_CSV = "performance_ai.csv"
DEBUG_CSV = "ai_cycle_debug.csv"
DASH_PNG = "dashboard.png"

APPROACH_EDGES = {
    "north": "north_in",
    "east": "east_in",
    "south": "south_in",
    "west": "west_in",
}

GUI_FAST_FILE = "gui_fast.xml"


# ==========================================================
# GUI FAST MODE
# ==========================================================
def ensure_gui_fast_file():
    if os.path.exists(GUI_FAST_FILE):
        return
    with open(GUI_FAST_FILE, "w") as f:
        f.write("""
<viewsettings>
    <delay value="0"/>
    <antialiasing value="false"/>
    <showLaneBorders value="false"/>
    <showLinkDecals value="false"/>
    <background value="0,0,0"/>
</viewsettings>
""")

import random

def safe_traci_start():
    ensure_gui_fast_file()
    random_seed = random.randint(1, 999999)

    traci.start([
        SUMO_BINARY,
        "-c", SUMO_CONFIG,
        "--start",
        "--quit-on-end",
        f"--gui-settings-file={GUI_FAST_FILE}",
        "--seed", str(random_seed)
    ])
    
    print(f"Using SUMO seed: {random_seed}")
    time.sleep(0.05)


# ==========================================================
# YOLO
# ==========================================================
USE_YOLO = True
YOLO_CLASSES_VEH = {2, 3, 5, 7}
_yolo = None

try:
    from ultralytics import YOLO
    _yolo = YOLO("yolov8n.pt")
    print("YOLO Loaded")
except:
    USE_YOLO = False
    print("YOLO disabled")


def yolo_total_from_gui(view_id, snap="frame.png"):
    if not USE_YOLO:
        return 0
    try:
        traci.gui.screenshot(view_id, snap)
        res = _yolo(snap, verbose=False)
        return sum(1 for box in res[0].boxes if int(box.cls[0]) in YOLO_CLASSES_VEH)
    except:
        return 0


# ==========================================================
# HELPERS
# ==========================================================
def get_counts():
    q = {}
    for d, e in APPROACH_EDGES.items():
        try:
            q[d] = traci.edge.getLastStepVehicleNumber(e)
        except:
            q[d] = 0
    return q


# ==========================================================
# 8-PHASE TRAFFIC LOGIC
# ==========================================================
def install_8_phase_tls(tls):
    try:
        lanes = traci.trafficlight.getControlledLanes(tls)
        if not lanes:
            return

        def approach(l):
            return l.split("_")[0]

        phases = []
        dirs = ["north", "east", "south", "west"]

        def make_state(g, col):
            s = ""
            for ln in lanes:
                if approach(ln) == g:
                    s += col
                else:
                    s += "r"
            return s

        for g in dirs:
            phases.append(trafficlight.Phase(15, make_state(g, "G")))
            phases.append(trafficlight.Phase(3, make_state(g, "y")))

        logic = trafficlight.Logic("8phase", 0, 0, phases)
        traci.trafficlight.setProgramLogic(tls, logic)

    except:
        traceback.print_exc()


# ==========================================================
# BASELINE (unchanged)
# ==========================================================
def baseline_run(max_steps=MAX_STEPS):
    print("\nRunning Baseline...")

    with open(BASE_CSV, "w", newline="") as f:
        csv.writer(f).writerow(["Step", "North", "East", "South", "West", "GreenTime"])

    safe_traci_start()
    install_8_phase_tls(TLS_ID)

    step = 0
    phase = 0
    next_change = 0

    while step < max_steps and traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()

        if step >= next_change:
            traci.trafficlight.setPhase(TLS_ID, phase)
            dur = 15 if phase % 2 == 0 else 3
            traci.trafficlight.setPhaseDuration(TLS_ID, dur)
            next_change = step + dur
            phase = (phase + 1) % 8

        q = get_counts()
        with open(BASE_CSV, "a", newline="") as f:
            csv.writer(f).writerow([step, q["north"], q["east"], q["south"], q["west"], 15])

        step += 1

    traci.close()


# ==========================================================
# ADAPTIVE AI WITH FAIRNESS + DENSITY
# (compact debug → CSV only, no prints)
# ==========================================================
def adaptive_run(max_steps=MAX_STEPS):
    print("\nRunning ADAPTIVE AI...")

    # main AI CSV
    with open(AI_CSV, "w", newline="") as f:
        csv.writer(f).writerow([
            "Step","North","East","South","West",
            "SelectedGroup","YOLO_Total","Fused_Total","GreenTime"
        ])

    # debug CSV
    with open(DEBUG_CSV, "w", newline="") as f:
        csv.writer(f).writerow([
            "Step", "ActiveGroups", "CycleOrder", "Selected",
            "Vehicles", "GreenTime"
        ])

    safe_traci_start()
    install_8_phase_tls(TLS_ID)

    step = 0
    view = traci.gui.getIDList()[0]

    groups = ["north","east","south","west"]

    cycle_list = []
    cycle_index = 0
    rotation_count = 0

    group_to_phase = {"north":0,"east":2,"south":4,"west":6}
    cur_group = "north"
    next_switch = 0

    MIN_G, MAX_G = 12, 45
    YEL = 3

    while step < max_steps and traci.simulation.getMinExpectedNumber() > 0:

        traci.simulationStep()
        q = get_counts()

        # active lanes only
        active = [g for g in groups if q[g] > 0]

        if len(active) == 0:
            step += 1
            continue

        # fairness cycle
        if rotation_count < len(active):

            if not cycle_list:
                cycle_list = sorted(active, key=lambda g: q[g], reverse=True)
                cycle_index = 0

            selected = cycle_list[cycle_index % len(cycle_list)]
            cycle_index += 1
            rotation_count += 1

        else:
            selected = max(active, key=lambda g: q[g])
            rotation_count = 0
            cycle_index = 0
            cycle_list = []

        # green time calculation
        base_time = q[selected] * 5.0
        fairness = min(q.values()) * 2
        green = int(max(MIN_G, min(MAX_G, base_time + fairness)))

        # YOLO occasionally
        if USE_YOLO and step % YOLO_EVERY_N_STEPS == 0:
            yolo = yolo_total_from_gui(view)
        else:
            yolo = 0

        fused = max(sum(q.values()), yolo)

        # signal switching
        if step >= next_switch:

            if step > 0:
                # yellow
                y_phase = group_to_phase[cur_group] + 1
                traci.trafficlight.setPhase(TLS_ID, y_phase)
                traci.trafficlight.setPhaseDuration(TLS_ID, YEL)
                traci.simulationStep()

            # green
            cur_group = selected
            traci.trafficlight.setPhase(TLS_ID, group_to_phase[cur_group])
            traci.trafficlight.setPhaseDuration(TLS_ID, green)
            next_switch = step + green

        # save main CSV
        with open(AI_CSV, "a", newline="") as f:
            csv.writer(f).writerow([
                step, q["north"], q["east"], q["south"], q["west"],
                selected, yolo, fused, green
            ])

        # save debug CSV
        with open(DEBUG_CSV, "a", newline="") as f:
            csv.writer(f).writerow([
                step, active, cycle_list if cycle_list else "[]",
                selected, q[selected], green
            ])

        step += 1

    traci.close()
    print("AI Complete")


# ==========================================================
# SUMMARY + DASHBOARD
# ==========================================================
def summarize(csv_file, label):
    df = pd.read_csv(csv_file)
    lanes = ["North","East","South","West"]
    df["Total"] = df[lanes].sum(axis=1)
    print(f"\nSummary {label}:", df["Total"].sum())
    return df["Total"].sum(), df[lanes].mean().to_dict()


def make_and_save_dashboard():
    df_b = pd.read_csv(BASE_CSV)
    df_a = pd.read_csv(AI_CSV)

    avg_b = df_b[["North","East","South","West"]].mean()
    avg_a = df_a[["North","East","South","West"]].mean()

    fig, ax = plt.subplots(figsize=(8,5))
    idx = range(4)
    w = 0.35

    ax.bar([i-w/2 for i in idx], avg_b, width=w, label="Baseline")
    ax.bar([i+w/2 for i in idx], avg_a, width=w, label="AI")

    ax.set_xticks(idx)
    ax.set_xticklabels(["North","East","South","West"])
    ax.set_ylabel("Avg Queue")
    ax.set_title("Baseline vs AI")
    ax.legend()

    plt.tight_layout()
    plt.savefig(DASH_PNG)
    plt.close()
def print_cmd_dashboard():
    df_b = pd.read_csv(BASE_CSV)
    df_a = pd.read_csv(AI_CSV)

    avg_b = df_b[["North","East","South","West"]].mean().round(2)
    avg_a = df_a[["North","East","South","West"]].mean().round(2)

    total_b = int(df_b[["North","East","South","West"]].sum().sum())
    total_a = int(df_a[["North","East","South","West"]].sum().sum())

    green_b = round(df_b["GreenTime"].mean(), 2)
    green_a = round(df_a["GreenTime"].mean(), 2)

    improvement = 0
    if avg_b.sum() > 0:
        improvement = round(
            (avg_b.sum() - avg_a.sum()) / avg_b.sum() * 100,
            2
        )

    print("\n--------------------------------------------")
    print("          TRAFFIC SIGNAL PERFORMANCE        ")
    print("--------------------------------------------\n")

    print("BASELINE PERFORMANCE")
    print(f"• Total Vehicles: {total_b}")
    print("• Avg Queue:")
    print(f"- North: {avg_b['North']}")
    print(f"- East : {avg_b['East']}")
    print(f"- South: {avg_b['South']}")
    print(f"- West : {avg_b['West']}")
    print(f"• Avg Green Time: {green_b} sec\n")

    print("ADAPTIVE AI PERFORMANCE")
    print(f"• Total Vehicles: {total_a}")
    print("• Avg Queue:")
    print(f"- North: {avg_a['North']}")
    print(f"- East : {avg_a['East']}")
    print(f"- South: {avg_a['South']}")
    print(f"- West : {avg_a['West']}")
    print(f"• Avg Green Time: {green_a} sec\n")

    print("--------------------------------------------")
    print(f"      AI QUEUE REDUCTION: {improvement} %")
    print("--------------------------------------------\n")



# ==========================================================
# MAIN
# ==========================================================
def main():
    # ---- Run Baseline Simulation ----
    baseline_run()

    #  FIX 1: Force baseline CSV to fully write before dashboard reads it
    baseline_df = pd.read_csv(BASE_CSV)
    baseline_df.to_csv(BASE_CSV, index=False)

    # ---- Run Adaptive AI Simulation ----
    adaptive_run()

    #  FIX 2: Force AI CSV to fully write before dashboard reads it
    ai_df = pd.read_csv(AI_CSV)
    ai_df.to_csv(AI_CSV, index=False)

    # ---- Now print & plot with fresh CSV data ----
    print_cmd_dashboard()
    make_and_save_dashboard()


if __name__ == "__main__":
    main()
