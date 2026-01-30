# adaptive_main.py — FINAL VERSION (with YOLO + SUMO fusion)
import sys
import os
import time
import traci
import pandas as pd
import traceback

# ----- Windows UTF-8 fix -----
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# ================================================================
# PATH SETTINGS
# ================================================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SUMO_CONFIG = os.path.join(BASE_DIR, "simulation.sumocfg")
FRAME_PATH = os.path.join(BASE_DIR, "frame.png")

AI_CSV = os.path.join(BASE_DIR, "performance_ai.csv")
DEBUG_CSV = os.path.join(BASE_DIR, "ai_cycle_debug.csv")

TLS_ID = "center"

# SUMO Inputs (edge ids must match your map)
APPROACH = {
    "north": "north_in",
    "east": "east_in",
    "south": "south_in",
    "west": "west_in"
}

# ================================================================
# YOLO SETTINGS
# ================================================================
USE_YOLO = True
YOLO_MODEL_PATH = os.path.join(BASE_DIR, "yolov8n.pt")
YOLO_CLASSES = {2, 3, 5, 7}   # car, bus, truck, motorcycle
YOLO_EVERY_N_STEPS = 10

_yolo = None
try:
    from ultralytics import YOLO
    _yolo = YOLO(YOLO_MODEL_PATH)
    print("YOLO successfully loaded:", YOLO_MODEL_PATH)
except Exception as e:
    USE_YOLO = False
    print("YOLO disabled (not found or failed to load):", e)

# ================================================================
# SAFE SUMO START
# ================================================================
def safe_start():
    import random
    seed = random.randint(1, 999999)
    traci.start([
        "sumo-gui",
        "-c", SUMO_CONFIG,
        "--start",
        "--quit-on-end",
        "--seed", str(seed)
    ])
    print("SUMO started with seed:", seed)
    # small pause so GUI initi

