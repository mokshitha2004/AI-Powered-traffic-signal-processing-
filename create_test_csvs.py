# create_test_csvs.py
# Create demo performance CSVs and a sample frame.png to test Streamlit UI quickly

import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

BASE_DIR = r"/mnt/data"
PERF_BASE = os.path.join(BASE_DIR, "performance_baseline.csv")
PERF_AI = os.path.join(BASE_DIR, "performance_ai.csv")
AI_CYCLE = os.path.join(BASE_DIR, "ai_cycle_debug.csv")
FRAME = os.path.join(BASE_DIR, "frame.png")

dirs = ["North","East","South","West"]
base_vals = [12.5, 10.2, 15.0, 8.6]
ai_vals = [8.3, 7.0, 10.1, 5.5]

df_base = pd.DataFrame({
    "region": dirs,
    "avg_queue": [f"{v:.2f}" for v in base_vals],
    "throughput": [120, 130, 110, 140]
})
df_ai = pd.DataFrame({
    "region": dirs,
    "avg_queue": [f"{v:.2f}" for v in ai_vals],
    "throughput": [125, 135, 115, 145]
})
df_cycle = pd.DataFrame({
    "step": list(range(0,100,10)),
    "selected_lane": ["lane0","lane1","lane2","lane3","lane0","lane1","lane2","lane3","lane0","lane1"],
    "green_duration": [12,10,15,9,11,10,14,8,12,10],
    "counts": ["{\"North\":12}" for _ in range(10)]
})

df_base.to_csv(PERF_BASE, index=False, encoding="utf-8")
df_ai.to_csv(PERF_AI, index=False, encoding="utf-8")
df_cycle.to_csv(AI_CYCLE, index=False, encoding="utf-8")

# create a sample frame image (simple placeholder)
img = Image.new("RGB",(1200,700), color=(240,240,240))
d = ImageDraw.Draw(img)
d.rectangle([50,50,1150,650], outline=(0,0,0), width=3)
d.text((60,60), "Simulation Frame (Demo)", fill=(0,0,0))
img.save(FRAME)
print("Demo CSVs and frame.png created at", BASE_DIR)
