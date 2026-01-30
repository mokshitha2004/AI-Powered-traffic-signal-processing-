# streamlit_app.py
# Updated: removed simulation frame from center and moved all charts to a full-width analytics area at the bottom.
# Overwrite your existing file with this.

import streamlit as st
import subprocess
import pandas as pd
import os
import time
import plotly.graph_objs as go
import plotly.express as px

# ---------------- Config ----------------
BASE_DIR = r"C:\Users\Mokshitha Thota\Documents\projects\AI POWERED TSP\SendAnywhere_746655\AdaptiveTrafficNEW"
UPLOADED_SCRIPT_PATH = os.path.join(BASE_DIR, "adaptive_main.py")  # provided earlier in this conversation

PERF_AI = os.path.join(BASE_DIR, "performance_ai.csv")
PERF_BASE = os.path.join(BASE_DIR, "performance_baseline.csv")
AI_CYCLE = os.path.join(BASE_DIR, "ai_cycle_debug.csv")
SIM_SCRIPT_MAIN = os.path.join(BASE_DIR, "adaptive_main.py")
SIM_SCRIPT_COMPARE = os.path.join(BASE_DIR, "adaptive_compare.py")
FRAME_PNG = os.path.join(BASE_DIR, "frame.png")
FRAME_PNG_MNT = "/mnt/data/frame.png"   # container fallback (not used now)
# ----------------------------------------

st.set_page_config(page_title="AI Traffic Signal — Analytics", layout="wide", initial_sidebar_state="collapsed")

# ---------- Small CSS ----------
st.markdown(
    """
    <style>
    .controls-row { display:flex; gap:14px; align-items:center; justify-content:flex-start; margin-bottom:12px; }
    .control-btn { border-radius:12px; padding:10px 16px; font-weight:700; }
    .kpi-grid { display:grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom:12px; }
    .kpi-card { background: linear-gradient(90deg,#ffecd2,#fcb69f); padding:12px; border-radius:10px; box-shadow:0 8px 20px rgba(15,25,40,0.06); }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------- Helpers ----------
def read_csv_safe(path):
    if not os.path.exists(path):
        return None
    try:
        return pd.read_csv(path, encoding="utf-8", engine="python")
    except Exception:
        try:
            return pd.read_csv(path, encoding="latin1", engine="python")
        except Exception:
            return None

def fmt(x):
    try:
        return f"{float(x):.2f}"
    except Exception:
        return "-"

def compute_total_vehicles_from_df(df):
    if df is None:
        return '-'
    cols = {c.lower(): c for c in df.columns}
    # throughput
    if 'throughput' in cols:
        try:
            return int(df[cols['throughput']].sum())
        except Exception:
            pass
    # wide format north/east/south/west
    if all(k in cols for k in ['north','east','south','west']):
        try:
            total = int(df[[cols['north'], cols['east'], cols['south'], cols['west']]].sum(axis=1).sum())
            return total
        except Exception:
            pass
    return '-'

# --- Safe rerun wrapper (covers multiple Streamlit versions) ---
def safe_rerun():
    """Try to trigger a rerun across different Streamlit versions.

    Order of attempts:
      1. st.experimental_rerun() if exposed
      2. raise internal RerunException() if available
      3. fallback: set a session flag and call st.stop()
    """
    # 1) Preferred public API (may be missing on some builds)
    try:
        st.experimental_rerun()
        return
    except Exception:
        # AttributeError or others: keep trying
        pass

    # 2) Try raising the internal RerunException
    try:
        from streamlit.runtime.scriptrunner.script_runner import RerunException
        raise RerunException()
    except Exception:
        # 3) Last-resort fallback
        st.session_state["_safe_rerun_requested"] = True
        st.stop()

# Optional: handle the session flag on app start if you want to run re-init code
if st.session_state.get("_safe_rerun_requested"):
    # Clear the flag and continue. Add any reinitialization logic here if needed.
    st.session_state["_safe_rerun_requested"] = False


def compute_summary():
    summary = {
        'total_base':'-','total_ai':'-',
        'avg_queue_base':{'North':'-','East':'-','South':'-','West':'-'},
        'avg_queue_ai':{'North':'-','East':'-','South':'-','West':'-'},
        'ai_queue_reduction':'-',
        'time_series': None
    }

    if os.path.exists(PERF_BASE) and os.path.exists(PERF_AI):
        dfb = read_csv_safe(PERF_BASE)
        dfa = read_csv_safe(PERF_AI)
        if dfb is None or dfa is None:
            return summary

        total_base = compute_total_vehicles_from_df(dfb)
        total_ai = compute_total_vehicles_from_df(dfa)

        dirs = ['North','East','South','West']
        avg_base = {d:'-' for d in dirs}
        avg_ai = {d:'-' for d in dirs}

        lcols_b = [c.lower() for c in dfb.columns]
        if 'region' in lcols_b and 'avg_queue' in lcols_b:
            cmap = {c.lower(): c for c in dfb.columns}
            gb = dfb.groupby(cmap['region'])[cmap['avg_queue']].mean().to_dict()
            for d in dirs:
                v = gb.get(d, None)
                if v is not None and not pd.isna(v):
                    avg_base[d] = fmt(v)
        else:
            cmap = {c.lower(): c for c in dfb.columns}
            if all(k in cmap for k in ['north','east','south','west']):
                for d in dirs:
                    try:
                        avg_base[d] = fmt(dfb[cmap[d.lower()]].mean())
                    except Exception:
                        avg_base[d] = '-'

        lcols_a = [c.lower() for c in dfa.columns]
        if 'region' in lcols_a and 'avg_queue' in lcols_a:
            cmap = {c.lower(): c for c in dfa.columns}
            ga = dfa.groupby(cmap['region'])[cmap['avg_queue']].mean().to_dict()
            for d in dirs:
                v = ga.get(d, None)
                if v is not None and not pd.isna(v):
                    avg_ai[d] = fmt(v)
        else:
            cmap = {c.lower(): c for c in dfa.columns}
            if all(k in cmap for k in ['north','east','south','west']):
                for d in dirs:
                    try:
                        avg_ai[d] = fmt(dfa[cmap[d.lower()]].mean())
                    except Exception:
                        avg_ai[d] = '-'

        # reduction
        try:
            s_base = sum([float(x) for x in avg_base.values() if x != '-'])
            s_ai = sum([float(x) for x in avg_ai.values() if x != '-'])
            red = round(100.0*(s_base - s_ai)/s_base, 2) if (s_base not in (0,'-') and s_base !=0) else '-'
        except Exception:
            red = '-'

        # optional time series
        time_df = None
        for df_try in (dfb, dfa):
            cols_try = [c.lower() for c in df_try.columns]
            if ('step' in cols_try or 'time' in cols_try) and all(k in cols_try for k in ['north','east','south','west']):
                step_col = [c for c in df_try.columns if c.lower() in ('step','time')][0]
                time_df = df_try[[step_col] + [c for c in df_try.columns if c.lower() in ('north','east','south','west')]].copy()
                time_df.columns = ['Step','North','East','South','West']
                break

        summary = {
            'total_base': total_base,
            'total_ai': total_ai,
            'avg_queue_base': avg_base,
            'avg_queue_ai': avg_ai,
            'ai_queue_reduction': red,
            'time_series': time_df
        }

    return summary

def show_kpis_area(summary, placeholder):
    t_base = summary.get('total_base', '-')
    t_ai = summary.get('total_ai', '-')
    reduction = summary.get('ai_queue_reduction', '-')
    # KPI cards
    placeholder.markdown(
        f"""
        <div class="kpi-grid">
          <div class="kpi-card"><b>Total vehicles</b><br><span style="font-size:22px">{t_base}</span><br><small>Baseline</small></div>
          <div class="kpi-card"><b>Total vehicles</b><br><span style="font-size:22px">{t_ai}</span><br><small>AI</small></div>
          <div class="kpi-card"><b>AI queue reduction</b><br><span style="font-size:22px">{reduction}%</span><br><small>Lower is better</small></div>
        </div>
        """,
        unsafe_allow_html=True
    )


def plot_all_charts(summary, placeholder):
    # grouped bar
    dirs = ['North','East','South','West']
    base_vals = [float(summary['avg_queue_base'].get(d,0)) if summary['avg_queue_base'].get(d,'-')!='-' else 0 for d in dirs]
    ai_vals = [float(summary['avg_queue_ai'].get(d,0))    if summary['avg_queue_ai'].get(d,'-')!='-' else 0 for d in dirs]

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(x=dirs, y=base_vals, name='Baseline', marker_color='#ff7a59'))
    fig_bar.add_trace(go.Bar(x=dirs, y=ai_vals, name='AI', marker_color='#ffd86b'))
    fig_bar.update_layout(barmode='group', title='Avg queue per direction', template='plotly_white', height=380)
    placeholder.plotly_chart(fig_bar, use_container_width=True)

    # pie (baseline & AI) side-by-side using two plots one after another
    df_pie = pd.DataFrame({'Direction': dirs, 'Baseline': base_vals, 'AI': ai_vals})
    fig_p_base = px.pie(df_pie, names='Direction', values='Baseline', title='Baseline avg-queue distribution')
    fig_p_ai = px.pie(df_pie, names='Direction', values='AI', title='AI avg-queue distribution')
    placeholder.plotly_chart(fig_p_base, use_container_width=True)
    placeholder.plotly_chart(fig_p_ai, use_container_width=True)

    # donut showing reduction
    try:
        red_val = float(summary.get('ai_queue_reduction', 0)) if summary.get('ai_queue_reduction','-')!='-' else 0.0
    except Exception:
        red_val = 0.0
    fig_donut = go.Figure(data=[go.Pie(values=[red_val, max(0,100-red_val)], labels=['Reduced','Remaining'], hole=.6)])
    fig_donut.update_layout(title='AI Queue Reduction (%)', height=300)
    placeholder.plotly_chart(fig_donut, use_container_width=True)

    # time series if available
    ts = summary.get('time_series', None)
    if ts is not None:
        try:
            ts['Total'] = ts[['North','East','South','West']].sum(axis=1)
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(x=ts['Step'], y=ts['Total'], mode='lines+markers', name='Total vehicles'))
            for d in ['North','East','South','West']:
                fig_line.add_trace(go.Scatter(x=ts['Step'], y=ts[d], mode='lines', name=d))
            fig_line.update_layout(title='Per-step vehicle counts', height=420, template='plotly_white')
            placeholder.plotly_chart(fig_line, use_container_width=True)
        except Exception:
            placeholder.info("Time-series not plotted due to unexpected format.")

# ---------- UI layout ----------
st.title("🚦 AI Powered Traffic Signal Processing")
st.subheader("Simulation + Analytics Dashboard")
st.markdown("---")

# layout: left for file buttons + logs; right for controls (buttons)
left_col, right_col = st.columns([1,3])

with right_col:
    # controls row (buttons)
    bc1, bc2, bc3, bc4 = st.columns([1,1,1,0.6])
    run_clicked = bc1.button("▶️ Run Simulation")
    analyze_clicked = bc2.button("📊 Analyze (show dashboard)")
    show_kpi_clicked = bc3.button("🔍 Show KPI & Chart")
    reset_clicked = bc4.button("🔄 Reset State")

    # IMPORTANT: we intentionally removed the central simulation frame image display per request.
    # The viewer area is no longer used for the static WhatsApp image.

with left_col:
    st.header("Files & Logs")
    if st.button("Open: Baseline CSV"):
        df = read_csv_safe(PERF_BASE)
        if df is not None:
            st.dataframe(df)
            st.download_button("Download baseline CSV", df.to_csv(index=False, encoding='utf-8'), file_name="performance_baseline.csv")
        else:
            st.warning("performance_baseline.csv not found or unreadable.")
    if st.button("Open: AI CSV"):
        df = read_csv_safe(PERF_AI)
        if df is not None:
            st.dataframe(df)
            st.download_button("Download ai CSV", df.to_csv(index=False, encoding='utf-8'), file_name="performance_ai.csv")
        else:
            st.warning("performance_ai.csv not found or unreadable.")
    if st.button("Open: AI Cycle CSV"):
        df = read_csv_safe(AI_CYCLE)
        if df is not None:
            st.dataframe(df)
            st.download_button("Download ai_cycle_debug.csv", df.to_csv(index=False, encoding='utf-8'), file_name="ai_cycle_debug.csv")
        else:
            st.warning("ai_cycle_debug.csv not found or unreadable.")
    logs_box = st.empty()

# quick reset
if reset_clicked:
    safe_rerun()

# run simulation (keeps previous synchronous streaming + log filtering)
if run_clicked:
    if not os.path.exists(SIM_SCRIPT_MAIN):
        st.error("adaptive_main.py not found in project folder.")
    else:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        try:
            proc = subprocess.Popen(
                ["python", SIM_SCRIPT_MAIN],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env
            )
        except Exception as e:
            st.error(f"Failed to start simulation: {e}")
            proc = None

        if proc:
            lines = []
            with st.spinner("Simulation running..."):
                while True:
                    ln = proc.stdout.readline()
                    if ln == "" and proc.poll() is not None:
                        break
                    if ln:
                        low = ln.lower()
                        # filter YOLO noise
                        if ("ultralytics" in low) or ("yolo disabled" in low) or ("no module named 'ultralytics'".lower() in low):
                            continue
                        lines.append(ln.rstrip())
                        logs_box.text("\n".join(lines[-300:]))

            proc.wait()
            logs_box.text("\n".join(lines[-300:] + ["✅ Simulation finished."]))

            # compare script optional
            if os.path.exists(SIM_SCRIPT_COMPARE):
                try:
                    pc = subprocess.Popen(["python", SIM_SCRIPT_COMPARE], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
                    comp_lines = []
                    with st.spinner("Running compare..."):
                        while True:
                            cl = pc.stdout.readline()
                            if cl == "" and pc.poll() is not None:
                                break
                            if cl:
                                if ("ultralytics" in cl.lower()) or ("yolo disabled" in cl.lower()):
                                    continue
                                comp_lines.append(cl.rstrip())
                                logs_box.text("\n".join(comp_lines[-300:]))
                        pc.wait()
                    logs_box.text("\n".join(lines[-300:] + ["✅ Compare finished."]))
                except Exception:
                    st.warning("Compare script failed or produced no output.")

# Analyze => show KPI cards and charts in a full-width analytics area at bottom
# Show KPI & Chart does the same (use whichever you prefer)
if analyze_clicked or show_kpi_clicked:
    summary = compute_summary()

    # full-width analytics container at the bottom
    analytics = st.container()
    with analytics:
        st.markdown("## Analytics")
        # KPI area (right-side previously) — show here full width
        show_kpis_area(summary, st)

        # Charts (all full-width stacked)
        plot_all_charts(summary, st)

        # small transparent table of summary values
        summary_tbl = {
            'metric': ['Total vehicles (baseline)','Total vehicles (AI)','AI queue reduction (%)'],
            'value': [summary.get('total_base','-'), summary.get('total_ai','-'), summary.get('ai_queue_reduction','-')]
        }
        st.table(pd.DataFrame(summary_tbl))

st.markdown("---")
st.caption("Made with ❤️ — AI Traffic Signal project.")
