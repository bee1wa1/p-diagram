# p_diagram_app.py
# Streamlit app to compose a Parameter Diagram (P-Diagram) for FMEA / robust design

import json
from io import BytesIO
from typing import Dict, List

import streamlit as st

try:
    import graphviz  # for export as SVG/PNG
    _GRAPHVIZ_AVAILABLE = True
except Exception:
    _GRAPHVIZ_AVAILABLE = False

# --- Helpers ---
DEFAULT_STATE = {
    "title": "My System / Subsystem",
    "intended_input": ["User command", "Supply power", "Sensor signal"],
    "ideal_function": ["Convert input to heat", "Maintain temperature ±2°C"],
    "desired_outputs": ["Target temperature reached", "Energy usage within limits"],
    "control_factors": [
        {"Factor": "PID gains", "Setting/Range": "Kp=1.2 Ki=0.3 Kd=0.05", "Notes": ""},
        {"Factor": "Supply voltage", "Setting/Range": "230V ±10%", "Notes": ""},
    ],
    "noise_factors": [
        {"Category": "Environment", "Factor": "Ambient temperature", "Notes": "5–40°C"},
        {"Category": "Usage", "Factor": "Door openings", "Notes": "Frequent/infrequent"},
        {"Category": "Manufacturing", "Factor": "Thermistor tolerance", "Notes": "±1% / ±3%"},
        {"Category": "Aging/Degradation", "Factor": "Insulation wear", "Notes": "Over time"},
        {"Category": "Other", "Factor": "Voltage dips", "Notes": "EN 61000-4-11"},
    ],
    "error_states": [
        "Overshoot/undershoot",
        "Slow response",
        "Runaway heating",
        "Sensor failure / drift",
    ],
    "orientation": "Left-to-Right",
    "include_legend": True,
}

ORIENTATIONS = {"Left-to-Right": "LR", "Top-to-Bottom": "TB", "Bottom-to-Top": "BT", "Right-to-Left": "RL"}

def ensure_session_state():
    if "pdiag" not in st.session_state:
        st.session_state.pdiag = DEFAULT_STATE.copy()

def _newline_join(items: List[str]) -> str:
    return "\\n".join([f"• {s}" for s in items if str(s).strip()] or ["—"])

def _table_to_lines(rows: List[Dict[str, str]], cols: List[str], prefix_bullets=True) -> List[str]:
    lines = []
    for r in rows:
        vals = [str(r.get(c, "")).strip() for c in cols]
        text = " | ".join([v if v else "—" for v in vals])
        lines.append(("• " if prefix_bullets else "") + text)
    return lines or ["—"]

def build_dot(p: Dict) -> str:
    rankdir = ORIENTATIONS.get(p.get("orientation", "Left-to-Right"), "LR")
    input_txt = _newline_join(p.get("intended_input", []))
    ideal_txt = _newline_join(p.get("ideal_function", []))
    desired_txt = _newline_join(p.get("desired_outputs", []))
    error_txt = _newline_join(p.get("error_states", []))

    control_lines = _table_to_lines(p.get("control_factors", []), ["Factor", "Setting/Range", "Notes"])
    control_txt = "\\n".join(control_lines)

    categories = ["Environment", "Usage", "Manufacturing", "Aging/Degradation", "Other"]
    by_cat = {c: [] for c in categories}
    for row in p.get("noise_factors", []):
        cat = row.get("Category", "Other")
        if cat not in by_cat:
            cat = "Other"
        by_cat[cat].append(
            ("• " + " | ".join([row.get("Factor", ""), row.get("Notes", "")]).strip(" |")).strip()
        )
    noise_sections = []
    for c in categories:
        lines = by_cat[c] or ["—"]
        block = f"<B>{c}</B><BR ALIGN='LEFT'/>" + "<BR ALIGN='LEFT'/>".join(lines)
        noise_sections.append(block)
    noise_html = "<BR/><HR/><BR/>".join(noise_sections)

    title = p.get("title", "Parameter Diagram")
    dot = f"""
digraph PDiagram {{
    rankdir={rankdir};
    graph [fontsize=10, labelloc="t", label="{title.replace('"','\\\"')}"];
    node [shape=box, style="rounded,filled", fillcolor="#f7f7f9", color="#cccccc", fontname="Helvetica"];
    edge [color="#888888", arrowsize=0.8];

    subgraph cluster_input {{
        label="Input Signal";
        color="#dddddd";
        n_input [label="{('{0}').format(input_txt)}", shape=box, style="rounded,filled", fillcolor="#eef6ff"];
    }}

    subgraph cluster_control {{
        label="Control Factors (Design/Process)";
        color="#dddddd";
        n_control [label="{('{0}').format(control_txt)}", shape=box, style="rounded,filled", fillcolor="#e9ffe9"];
    }}

    subgraph cluster_noise {{
        label="Noise Factors";
        color="#dddddd";
        n_noise [label=<
            <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">
                <TR><TD ALIGN="LEFT">{noise_html}</TD></TR>
            </TABLE>
        >, shape=box, style="rounded,filled", fillcolor="#fff7e6"];
    }}

    subgraph cluster_system {{
        label="System / Ideal Function";
        color="#dddddd";
        n_system [label="{('{0}').format(ideal_txt)}", shape=box, style="rounded,filled", fillcolor="#ffffff"];
    }}

    subgraph cluster_output {{
        label="Desired Output(s)";
        color="#dddddd";
        n_out [label="{('{0}').format(desired_txt)}", shape=box, style="rounded,filled", fillcolor="#eef6ff"];
    }}

    subgraph cluster_errors {{
        label="Error States / Undesired Output(s)";
        color="#dddddd";
        n_err [label="{('{0}').format(error_txt)}", shape=box, style="rounded,filled", fillcolor="#ffecec"];
    }}

    n_input -> n_system;
    n_control -> n_system;
    n_noise -> n_system;
    n_system -> n_out;
    n_system -> n_err [style=dashed];

    { 'legend [shape=note, label="Legend\\nSolid: intended flow\\nDashed: unintended / failure path", fontsize=9]; legend -> n_out [style=invis];' if p.get('include_legend', True) else '' }
}}
    """
    return dot

def _safe_json_download(obj: Dict, filename: str):
    data = json.dumps(obj, indent=2).encode("utf-8")
    st.download_button("💾 Download JSON", data, file_name=filename, mime="application/json")

def _export_graph(dot: str, fmt: str) -> BytesIO:
    if not _GRAPHVIZ_AVAILABLE:
        raise RuntimeError("Graphviz Python package/executables not available.")
    src = graphviz.Source(dot, format=fmt, engine="dot")
    binary = src.pipe(format=fmt)
    return BytesIO(binary)

# --- UI ---
st.set_page_config(page_title="P-Diagram Builder", page_icon="📐", layout="wide")
ensure_session_state()
p = st.session_state.pdiag

st.title("📐 Parameter Diagram (P-Diagram) Builder")
st.caption("Compose a P-Diagram to support FMEA, robust design, and DRBFM discussions.")

with st.sidebar:
    st.subheader("📋 Project")
    p["title"] = st.text_input("Title", value=p["title"])
    p["orientation"] = st.selectbox("Diagram orientation", list(ORIENTATIONS.keys()),
                                    index=list(ORIENTATIONS.keys()).index(p["orientation"]))
    p["include_legend"] = st.checkbox("Include legend", value=p["include_legend"])

    st.markdown("---")
    st.subheader("📁 Save / Load")
    _safe_json_download(p, filename="p_diagram.json")
    uploaded = st.file_uploader("Load from JSON", type=["json"])
    if uploaded:
        try:
            loaded = json.load(uploaded)
            st.session_state.pdiag = {**p, **loaded}
            st.success("Loaded P-Diagram from JSON.")
        except Exception as e:
            st.error(f"Could not load JSON: {e}")

tabs = st.tabs(["Inputs & Outputs", "Factors", "Diagram", "Export", "Help"])

with tabs[0]:
    st.subheader("🎯 Intended Input(s)")
    p["intended_input"] = st.data_editor(
        p.get("intended_input", []),
        num_rows="dynamic",
        use_container_width=True,
        key="ed_inputs",
    )

    st.subheader("⚙️ Ideal Function")
    p["ideal_function"] = st.data_editor(
        p.get("ideal_function", []),
        num_rows="dynamic",
        use_container_width=True,
        key="ed_ideal",
    )

    st.subheader("✅ Desired Output(s)")
    p["desired_outputs"] = st.data_editor(
        p.get("desired_outputs", []),
        num_rows="dynamic",
        use_container_width=True,
        key="ed_outputs",
    )

    st.subheader("⚠️ Error States / Undesired Output(s)")
    p["error_states"] = st.data_editor(
        p.get("error_states", []),
        num_rows="dynamic",
        use_container_width=True,
        key="ed_errors",
    )

with tabs[1]:
    st.subheader("🎚️ Control Factors (Design / Process)")
    if not p.get("control_factors"):
        p["control_factors"] = []
    p["control_factors"] = st.data_editor(
        p["control_factors"],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Factor": st.column_config.TextColumn("Factor"),
            "Setting/Range": st.column_config.TextColumn("Setting/Range"),
            "Notes": st.column_config.TextColumn("Notes"),
        },
        key="ed_control",
    )

    st.subheader("🌪️ Noise Factors")
    if not p.get("noise_factors"):
        p["noise_factors"] = []
    p["noise_factors"] = st.data_editor(
        p["noise_factors"],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Category": st.column_config.SelectboxColumn(
                "Category",
                options=["Environment", "Usage", "Manufacturing", "Aging/Degradation", "Other"],
                required=True,
            ),
            "Factor": st.column_config.TextColumn("Factor"),
            "Notes": st.column_config.TextColumn("Notes"),
        },
        key="ed_noise",
    )

with tabs[2]:
    st.subheader("🖼️ Live Diagram")
    dot = build_dot(p)
    st.graphviz_chart(dot, use_container_width=True)

with tabs[3]:
    st.subheader("📤 Export")
    st.write("Download a snapshot of your P-Diagram as SVG or PNG. "
             "If export fails, you can still take a screenshot of the live diagram.")
    dot = build_dot(p)
    col1, col2 = st.columns(2)
    with col1:
        try:
            svg_buf = _export_graph(dot, "svg")
            st.download_button("⬇️ Download SVG", data=svg_buf, file_name="p_diagram.svg", mime="image/svg+xml")
        except Exception as e:
            st.info("SVG export not available on this system.")
            st.caption(f"Details: {e}")
    with col2:
        try:
            png_buf = _export_graph(dot, "png")
            st.download_button("⬇️ Download PNG", data=png_buf, file_name="p_diagram.png", mime="image/png")
        except Exception as e:
            st.info("PNG export not available on this system.")
            st.caption(f"Details: {e}")

with tabs[4]:
    st.subheader("How to use this app")
    st.markdown("""
1) **Fill Inputs & Outputs**  
2) **Add Factors** (Control & Noise)  
3) **Review Diagram**  
4) **Export** (SVG/PNG) or **Save/Load** JSON
""")
    st.subheader("Run locally")
    st.code("pip install streamlit graphviz\nstreamlit run p_diagram_app.py", language="bash")
    st.caption("For PNG/SVG export, also install Graphviz system binaries (e.g., via your OS package manager).")