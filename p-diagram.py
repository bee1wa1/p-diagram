# p_diagram_merged_app.py
# Streamlit app:
# 1) Build a P-Diagram for FMEA / robust design / DRBFM
# 2) Simulate input-output relationships:
#    - input on x-axis
#    - output on y-axis
#    - control factors modify the mean curve
#    - noise factors create scatter band

import copy
import json
from io import BytesIO
from typing import Dict, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    import graphviz

    _GRAPHVIZ_AVAILABLE = True
except Exception:
    _GRAPHVIZ_AVAILABLE = False


# =============================================================================
# Example states
# =============================================================================

SIMPLE_MODE = "Simple teaching example — PA66 vs POM"
EXHAUSTIVE_MODE = "Exhaustive realistic example — Full gear transmission"
CUSTOM_MODE = "Custom loaded P-Diagram"

PRESET_MODES = [
    SIMPLE_MODE,
    EXHAUSTIVE_MODE,
]

SIMPLE_MATERIAL_STATE = {
    "title": "Plastic Gear Material Comparison: PA66 vs POM",
    "orientation": "Left-to-Right",
    "include_legend": True,
    "intended_input": [
        "Transmitted torque (Nm)",
        "Rotational speed (rpm)",
    ],
    "ideal_function": [
        "Transmit torque with acceptable efficiency and wear resistance",
    ],
    "desired_outputs": [
        "Efficiency (%)",
        "Wear resistance index",
    ],
    "control_factors": [
        {
            "Factor": "Gear material",
            "Setting/Range": "PA66 / POM",
            "Notes": "Main design choice for this simplified example",
        },
        {
            "Factor": "Tooth geometry",
            "Setting/Range": "Same geometry for comparison",
            "Notes": "Kept constant to isolate the material effect",
        },
        {
            "Factor": "Lubrication condition",
            "Setting/Range": "Dry / greased",
            "Notes": "Influences friction and wear",
        },
    ],
    "noise_factors": [
        {
            "Category": "Usage",
            "Factor": "Load variation",
            "Notes": "Customer torque variation around nominal load",
        },
        {
            "Category": "Environment",
            "Factor": "Temperature variation",
            "Notes": "Cold and hot operating conditions",
        },
        {
            "Category": "Environment",
            "Factor": "Dust / contamination",
            "Notes": "Particles may increase abrasive wear",
        },
        {
            "Category": "Manufacturing",
            "Factor": "Dimensional variation",
            "Notes": "Tooth profile, backlash and molding variation",
        },
    ],
    "error_states": [
        "Efficiency loss",
        "Excessive wear",
        "Tooth damage",
        "Increased noise",
    ],
}

EXHAUSTIVE_GEAR_STATE = {
    "title": "Gear Transmission (Spur/Helical)",
    "orientation": "Left-to-Right",
    "include_legend": True,
    "intended_input": [
        "Input torque (Nm)",
        "Input rotational speed (rpm)",
        "Duty cycle / load spectrum",
        "Direction of rotation",
        "Axial and radial reaction loads",
        "Lubrication oil supply, if actively controlled",
    ],
    "ideal_function": [
        "Transmit torque and speed according to the specified gear ratio",
        "Maintain smooth meshing and correct kinematics",
        "Limit contact and bending stresses within design allowables",
        "Maintain adequate lubrication film to minimize wear",
        "Keep temperature rise within specified limits",
    ],
    "desired_outputs": [
        "Specified output torque and speed",
        "Gear ratio achieved within tolerance",
        "Low noise and vibration within target",
        "High efficiency above target",
        "Stable operating temperature below target rise",
        "Minimal wear over required service life",
    ],
    "control_factors": [
        {
            "Factor": "Gear material & hardness",
            "Setting/Range": "Material, hardness, surface treatment",
            "Notes": "Defines strength, friction, wear and fatigue resistance",
        },
        {
            "Factor": "Tooth geometry",
            "Setting/Range": "Module, pressure angle, helix angle",
            "Notes": "Defines stress, contact ratio and NVH behavior",
        },
        {
            "Factor": "Profile shift / crowning",
            "Setting/Range": "x, Cα/Cβ per load",
            "Notes": "Edge load mitigation",
        },
        {
            "Factor": "Face width",
            "Setting/Range": "Defined from torque and life requirement",
            "Notes": "Influences contact stress and bending strength",
        },
        {
            "Factor": "Surface finish / grinding",
            "Setting/Range": "Ra target",
            "Notes": "Important for pitting, scuffing and noise",
        },
        {
            "Factor": "Heat treatment",
            "Setting/Range": "Carburizing, nitriding, induction hardening",
            "Notes": "Controls case depth, hardness and toughness",
        },
        {
            "Factor": "Backlash & tolerances",
            "Setting/Range": "Per gear quality class / internal specification",
            "Notes": "Important for NVH and thermal expansion",
        },
        {
            "Factor": "Shaft alignment & housing stiffness",
            "Setting/Range": "Target μm / mrad",
            "Notes": "Controls load distribution across face width",
        },
        {
            "Factor": "Bearing selection & preload",
            "Setting/Range": "Bearing type / preload value",
            "Notes": "Influences mesh alignment and vibration",
        },
        {
            "Factor": "Lubricant type & viscosity",
            "Setting/Range": "Viscosity grade per operating temperature",
            "Notes": "Controls lubrication film thickness",
        },
        {
            "Factor": "Lubrication method",
            "Setting/Range": "Splash / bath / jet / forced lubrication",
            "Notes": "Defines oil availability at mesh contact",
        },
        {
            "Factor": "Sealing solution",
            "Setting/Range": "Lip seal / mechanical seal / labyrinth",
            "Notes": "Controls ingress and leakage",
        },
    ],
    "noise_factors": [
        {
            "Category": "Environment",
            "Factor": "Ambient temperature variation",
            "Notes": "Cold start / hot climate",
        },
        {
            "Category": "Environment",
            "Factor": "Dust, particulates and moisture",
            "Notes": "Ingress risk",
        },
        {
            "Category": "Environment",
            "Factor": "Corrosive agents",
            "Notes": "Chemicals / salt fog",
        },
        {
            "Category": "Usage",
            "Factor": "Shock loads / overload events",
            "Notes": "Start-up, impacts, abuse loads",
        },
        {
            "Category": "Usage",
            "Factor": "Duty cycle variability",
            "Notes": "Different load spectra, stop/start, reversals",
        },
        {
            "Category": "Usage",
            "Factor": "Operator or installation behavior",
            "Notes": "Improper warm-up, overload, wrong mounting",
        },
        {
            "Category": "Manufacturing",
            "Factor": "Tooth profile and lead deviations",
            "Notes": "Fα / Fβ scatter",
        },
        {
            "Category": "Manufacturing",
            "Factor": "Pitch error and runout",
            "Notes": "Fp / Fr variation",
        },
        {
            "Category": "Manufacturing",
            "Factor": "Material, hardness and case depth scatter",
            "Notes": "Batch-to-batch and part-to-part variation",
        },
        {
            "Category": "Aging/Degradation",
            "Factor": "Lubricant oxidation or contamination",
            "Notes": "Water, wear debris, viscosity change",
        },
        {
            "Category": "Aging/Degradation",
            "Factor": "Seal wear and leakage",
            "Notes": "Oil loss over time",
        },
        {
            "Category": "Aging/Degradation",
            "Factor": "Bearing degradation",
            "Notes": "Affects alignment and vibration",
        },
        {
            "Category": "Other",
            "Factor": "Housing deformation / thermal growth",
            "Notes": "Load and temperature dependent deformation",
        },
        {
            "Category": "Other",
            "Factor": "Assembly variation / installation misalignment",
            "Notes": "Mounting and tolerance stack-up",
        },
    ],
    "error_states": [
        "Tooth pitting / micropitting",
        "Scuffing / scoring",
        "Spalling / flake failure",
        "Tooth root bending fatigue / breakage",
        "Excessive noise / NVH",
        "Overheating of gearbox",
        "Accelerated wear due to poor lubrication",
        "Efficiency loss",
        "Oil leakage / foaming",
        "Corrosion of gear flanks",
    ],
}

DEFAULT_STATE = SIMPLE_MATERIAL_STATE

ORIENTATIONS = {
    "Left-to-Right": "LR",
    "Top-to-Bottom": "TB",
    "Bottom-to-Top": "BT",
    "Right-to-Left": "RL",
}

NOISE_CATEGORIES = [
    "Environment",
    "Usage",
    "Manufacturing",
    "Aging/Degradation",
    "Other",
]

MATERIAL_PRESETS = {
    "PA66": {
        "efficiency_baseline": 82.0,
        "efficiency_drop": 10.0,
        "wear_resistance_baseline": 65.0,
        "wear_sensitivity": 35.0,
        "scatter_multiplier": 1.15,
    },
    "POM": {
        "efficiency_baseline": 88.0,
        "efficiency_drop": 6.0,
        "wear_resistance_baseline": 78.0,
        "wear_sensitivity": 22.0,
        "scatter_multiplier": 0.90,
    },
}


# =============================================================================
# General helpers
# =============================================================================

def ensure_session_state() -> None:
    if "example_mode" not in st.session_state:
        st.session_state.example_mode = SIMPLE_MODE

    if "pdiag" not in st.session_state:
        st.session_state.pdiag = copy.deepcopy(SIMPLE_MATERIAL_STATE)


def load_example(example_mode: str) -> None:
    if example_mode == SIMPLE_MODE:
        st.session_state.pdiag = copy.deepcopy(SIMPLE_MATERIAL_STATE)
        st.session_state.example_mode = SIMPLE_MODE

    elif example_mode == EXHAUSTIVE_MODE:
        st.session_state.pdiag = copy.deepcopy(EXHAUSTIVE_GEAR_STATE)
        st.session_state.example_mode = EXHAUSTIVE_MODE


def reset_current_example() -> None:
    if st.session_state.example_mode == SIMPLE_MODE:
        load_example(SIMPLE_MODE)

    elif st.session_state.example_mode == EXHAUSTIVE_MODE:
        load_example(EXHAUSTIVE_MODE)

    else:
        st.session_state.pdiag = copy.deepcopy(SIMPLE_MATERIAL_STATE)
        st.session_state.example_mode = SIMPLE_MODE


def text_to_list(text: str) -> List[str]:
    return [line.strip(" -•\t") for line in text.splitlines() if line.strip()]


def list_to_text(items: List[str]) -> str:
    return "\n".join(items or [])


def bullet_text(items: List[str]) -> str:
    clean = [str(x).strip() for x in items if str(x).strip()]

    if not clean:
        return "—"

    return "\n".join(f"• {x}" for x in clean)


def escape_dot_text(text: str) -> str:
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
    )


def normalize_table(data, required_columns: List[str]) -> pd.DataFrame:
    df = pd.DataFrame(data or [])

    for col in required_columns:
        if col not in df.columns:
            df[col] = ""

    return df[required_columns].fillna("")


def dataframe_to_records(df: pd.DataFrame) -> List[Dict[str, str]]:
    if df is None or df.empty:
        return []

    return df.fillna("").to_dict(orient="records")


def table_to_lines(rows: List[Dict[str, str]], cols: List[str]) -> str:
    lines = []

    for row in rows or []:
        vals = [str(row.get(c, "")).strip() for c in cols]
        vals = [v if v else "—" for v in vals]
        lines.append("• " + " | ".join(vals))

    return "\n".join(lines) if lines else "—"


def get_factor_names(rows: List[Dict[str, str]]) -> List[str]:
    names = []

    for row in rows or []:
        factor = str(row.get("Factor", "")).strip()

        if factor:
            names.append(factor)

    return names


def json_download(obj: Dict, filename: str) -> None:
    data = json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")

    st.download_button(
        "💾 Download JSON",
        data,
        file_name=filename,
        mime="application/json",
    )


def safe_key(text: str) -> str:
    clean = "".join(ch if ch.isalnum() else "_" for ch in str(text))
    return clean[:80]


def current_mode_key() -> str:
    return safe_key(st.session_state.example_mode)


def behavior_label(input_name: str, output_name: str) -> str:
    input_lower = input_name.lower()
    output_lower = output_name.lower()

    if "torque" in input_lower and "efficiency" in output_lower:
        return "Torque-efficiency characteristic"

    if "torque" in input_lower and "wear" in output_lower:
        return "Torque-wear characteristic"

    if "material" in output_lower:
        return "Material-dependent performance characteristic"

    return "Input-output performance characteristic"


# =============================================================================
# Graphviz P-Diagram helpers
# =============================================================================

def build_noise_text(rows: List[Dict[str, str]]) -> str:
    by_cat = {cat: [] for cat in NOISE_CATEGORIES}

    for row in rows or []:
        cat = str(row.get("Category", "Other")).strip()

        if cat not in by_cat:
            cat = "Other"

        factor = str(row.get("Factor", "")).strip()
        notes = str(row.get("Notes", "")).strip()

        if not factor and not notes:
            continue

        if factor and notes:
            by_cat[cat].append(f"- {factor} | {notes}")
        elif factor:
            by_cat[cat].append(f"- {factor}")
        elif notes:
            by_cat[cat].append(f"- {notes}")

    sections = []

    for cat in NOISE_CATEGORIES:
        lines = by_cat.get(cat, [])

        if lines:
            section = cat + ":\n" + "\n".join(lines)
        else:
            section = cat + ":\n- —"

        sections.append(section)

    return "\n\n".join(sections)


def build_dot(p: Dict) -> str:
    rankdir = ORIENTATIONS.get(p.get("orientation", "Left-to-Right"), "LR")

    title = escape_dot_text(p.get("title", "Parameter Diagram"))

    input_txt = escape_dot_text(bullet_text(p.get("intended_input", [])))
    ideal_txt = escape_dot_text(bullet_text(p.get("ideal_function", [])))
    desired_txt = escape_dot_text(bullet_text(p.get("desired_outputs", [])))
    error_txt = escape_dot_text(bullet_text(p.get("error_states", [])))

    control_txt = escape_dot_text(
        table_to_lines(
            p.get("control_factors", []),
            ["Factor", "Setting/Range", "Notes"],
        )
    )

    noise_txt = escape_dot_text(
        build_noise_text(
            p.get("noise_factors", [])
        )
    )

    legend_dot = ""

    if p.get("include_legend", True):
        legend_dot = """
        legend [
            shape=note,
            label="Legend\\nSolid arrows: intended functional flow\\nDashed arrow: undesired / failure path",
            fontsize=9,
            fillcolor="#ffffff"
        ];
        legend -> n_out [style=invis];
        """

    dot = f"""
digraph PDiagram {{
    rankdir={rankdir};

    graph [
        fontsize=14,
        labelloc="t",
        label="{title}",
        bgcolor="white",
        pad=0.3,
        nodesep=0.6,
        ranksep=0.8
    ];

    node [
        shape=box,
        style="rounded,filled",
        color="#bbbbbb",
        fontname="Helvetica",
        fontsize=10,
        margin=0.12
    ];

    edge [
        color="#777777",
        arrowsize=0.8,
        fontname="Helvetica",
        fontsize=9
    ];

    subgraph cluster_input {{
        label="Input Signal";
        color="#dddddd";
        n_input [
            label="{input_txt}",
            fillcolor="#eef6ff"
        ];
    }}

    subgraph cluster_control {{
        label="Control Factors\\nDesign / Process choices";
        color="#dddddd";
        n_control [
            label="{control_txt}",
            fillcolor="#e9ffe9"
        ];
    }}

    subgraph cluster_noise {{
        label="Noise Factors\\nUncontrolled / variable conditions";
        color="#dddddd";
        n_noise [
            label="{noise_txt}",
            fillcolor="#fff7e6"
        ];
    }}

    subgraph cluster_system {{
        label="System / Ideal Function";
        color="#dddddd";
        n_system [
            label="{ideal_txt}",
            fillcolor="#ffffff"
        ];
    }}

    subgraph cluster_output {{
        label="Desired Output(s)";
        color="#dddddd";
        n_out [
            label="{desired_txt}",
            fillcolor="#eef6ff"
        ];
    }}

    subgraph cluster_errors {{
        label="Error States / Undesired Output(s)";
        color="#dddddd";
        n_err [
            label="{error_txt}",
            fillcolor="#ffecec"
        ];
    }}

    n_input -> n_system [label="intended signal"];
    n_control -> n_system [label="set by design"];
    n_noise -> n_system [label="disturbance"];
    n_system -> n_out [label="robust function"];
    n_system -> n_err [style=dashed, label="loss of function"];

    {legend_dot}
}}
"""
    return dot


def export_graph(dot: str, fmt: str) -> BytesIO:
    if not _GRAPHVIZ_AVAILABLE:
        raise RuntimeError("Graphviz Python package/executables not available.")

    src = graphviz.Source(dot, format=fmt, engine="dot")
    binary = src.pipe(format=fmt)

    return BytesIO(binary)


# =============================================================================
# Generic response simulator helpers
# =============================================================================

def response_direction(output_name: str) -> str:
    text = output_name.lower()

    lower_is_better_keywords = [
        "noise",
        "vibration",
        "temperature",
        "wear",
        "loss",
        "leakage",
        "deformation",
        "stress",
        "damage",
        "failure",
        "corrosion",
        "pitting",
        "scuffing",
    ]

    if any(k in text for k in lower_is_better_keywords):
        return "lower_is_better"

    return "higher_is_better"


def build_response_data(
    input_name: str,
    output_name: str,
    control_settings: Dict[str, float],
    control_effects: Dict[str, str],
    noise_settings: Dict[str, float],
    n_points: int,
    seed: int,
    x_min: float,
    x_max: float,
    base_slope: float,
    base_offset: float,
    base_curvature: float,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    x = np.linspace(x_min, x_max, n_points)
    x_norm = (x - x_min) / max(x_max - x_min, 1e-9)

    slope_multiplier = 1.0
    offset_shift = 0.0
    curvature_shift = 0.0

    for factor, setting in control_settings.items():
        effect_type = control_effects.get(factor, "Slope / sensitivity")

        if effect_type == "Slope / sensitivity":
            slope_multiplier += 0.25 * setting

        elif effect_type == "Offset / baseline":
            offset_shift += 10.0 * setting

        elif effect_type == "Curvature / non-linearity":
            curvature_shift += 0.35 * setting

    slope_multiplier = max(0.05, slope_multiplier)
    curvature = max(0.2, base_curvature + curvature_shift)

    mean_y = base_offset + offset_shift + base_slope * slope_multiplier * (
        x_norm ** curvature
    )

    direction = response_direction(output_name)

    if direction == "lower_is_better":
        response_type = "Lower is better"
    else:
        response_type = "Higher is better"

    total_noise_intensity = sum(abs(v) for v in noise_settings.values())

    sigma = 2.0 + 4.0 * total_noise_intensity
    sigma_x = sigma * (0.7 + 0.6 * x_norm)

    y_scatter = mean_y + rng.normal(
        loc=0.0,
        scale=sigma_x,
        size=n_points,
    )

    upper_band = mean_y + 2.0 * sigma_x
    lower_band = mean_y - 2.0 * sigma_x

    df = pd.DataFrame(
        {
            "input": x,
            "mean_output": mean_y,
            "scatter_output": y_scatter,
            "upper_band": upper_band,
            "lower_band": lower_band,
            "noise_sigma": sigma_x,
        }
    )

    df["input_name"] = input_name
    df["output_name"] = output_name
    df["response_interpretation"] = response_type

    return df


def build_response_figure(
    df: pd.DataFrame,
    input_name: str,
    output_name: str,
    show_scatter: bool,
    show_band: bool,
) -> go.Figure:
    fig = go.Figure()

    if show_band:
        fig.add_trace(
            go.Scatter(
                x=df["input"],
                y=df["upper_band"],
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["input"],
                y=df["lower_band"],
                mode="lines",
                fill="tonexty",
                line=dict(width=0),
                name="Noise band",
                hoverinfo="skip",
            )
        )

    fig.add_trace(
        go.Scatter(
            x=df["input"],
            y=df["mean_output"],
            mode="lines",
            name="Mean response",
            line=dict(width=3),
        )
    )

    if show_scatter:
        fig.add_trace(
            go.Scatter(
                x=df["input"],
                y=df["scatter_output"],
                mode="markers",
                name="Observed response with noise",
                marker=dict(size=6, opacity=0.55),
            )
        )

    fig.update_layout(
        title=f"{behavior_label(input_name, output_name)}",
        xaxis_title=input_name,
        yaxis_title=output_name,
        template="plotly_white",
        hovermode="closest",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
        margin=dict(l=40, r=20, t=80, b=40),
    )

    return fig


# =============================================================================
# Simple material response simulator helpers
# =============================================================================

def build_material_response_data(
    selected_materials: List[str],
    input_name: str,
    output_name: str,
    noise_settings: Dict[str, float],
    n_points: int,
    seed: int,
    x_min: float,
    x_max: float,
) -> pd.DataFrame:
    rows = []

    for i, selected_material in enumerate(selected_materials):
        rng = np.random.default_rng(seed + i)

        material = MATERIAL_PRESETS.get(
            selected_material,
            MATERIAL_PRESETS["PA66"],
        )

        x = np.linspace(x_min, x_max, n_points)
        x_norm = (x - x_min) / max(x_max - x_min, 1e-9)

        output_lower = output_name.lower()

        if "efficiency" in output_lower:
            mean_y = (
                material["efficiency_baseline"]
                - material["efficiency_drop"] * (x_norm ** 1.4)
            )
            y_axis_label = "Efficiency (%)"

        elif "wear" in output_lower:
            mean_y = (
                material["wear_resistance_baseline"]
                - material["wear_sensitivity"] * (x_norm ** 1.6)
            )
            y_axis_label = "Wear resistance index"

        else:
            mean_y = 80.0 - 20.0 * x_norm
            y_axis_label = output_name

        total_noise_intensity = sum(abs(v) for v in noise_settings.values())

        sigma = (
            1.5 + 4.0 * total_noise_intensity
        ) * material["scatter_multiplier"]

        sigma_x = sigma * (0.8 + 0.5 * x_norm)

        y_scatter = mean_y + rng.normal(
            loc=0.0,
            scale=sigma_x,
            size=n_points,
        )

        upper_band = mean_y + 2.0 * sigma_x
        lower_band = mean_y - 2.0 * sigma_x

        df_material = pd.DataFrame(
            {
                "input": x,
                "mean_output": mean_y,
                "scatter_output": y_scatter,
                "upper_band": upper_band,
                "lower_band": lower_band,
                "noise_sigma": sigma_x,
            }
        )

        df_material["material"] = selected_material
        df_material["input_name"] = input_name
        df_material["output_name"] = y_axis_label

        rows.append(df_material)

    return pd.concat(rows, ignore_index=True)


def build_material_response_figure(
    df: pd.DataFrame,
    input_name: str,
    output_name: str,
    show_band: bool,
) -> go.Figure:
    fig = go.Figure()

    material_styles = {
        "PA66": {
            "line_color": "rgb(31, 119, 180)",
            "band_color": "rgba(31, 119, 180, 0.18)",
            "line_dash": "solid",
        },
        "POM": {
            "line_color": "rgb(255, 127, 14)",
            "band_color": "rgba(255, 127, 14, 0.18)",
            "line_dash": "solid",
        },
    }

    materials = list(df["material"].dropna().unique())

    for material in materials:
        df_m = df[df["material"] == material].copy()

        style = material_styles.get(
            material,
            {
                "line_color": "rgb(80, 80, 80)",
                "band_color": "rgba(80, 80, 80, 0.15)",
                "line_dash": "solid",
            },
        )

        if show_band:
            fig.add_trace(
                go.Scatter(
                    x=df_m["input"],
                    y=df_m["upper_band"],
                    mode="lines",
                    line=dict(
                        width=0,
                        color=style["band_color"],
                    ),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=df_m["input"],
                    y=df_m["lower_band"],
                    mode="lines",
                    fill="tonexty",
                    fillcolor=style["band_color"],
                    line=dict(
                        width=0,
                        color=style["band_color"],
                    ),
                    name=f"Scatter band - {material}",
                    hoverinfo="skip",
                )
            )

        fig.add_trace(
            go.Scatter(
                x=df_m["input"],
                y=df_m["mean_output"],
                mode="lines",
                name=f"Mean response - {material}",
                line=dict(
                    color=style["line_color"],
                    width=4,
                    dash=style["line_dash"],
                ),
            )
        )

    fig.update_layout(
        title=f"PA66 vs POM — {behavior_label(input_name, output_name)}",
        xaxis_title=input_name,
        yaxis_title=output_name,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
        margin=dict(l=40, r=20, t=80, b=40),
    )

    return fig


# =============================================================================
# Streamlit UI
# =============================================================================

st.set_page_config(
    page_title="P-Diagram Builder and Response Simulator",
    page_icon="📐",
    layout="wide",
)

ensure_session_state()
p = st.session_state.pdiag

st.title("📐 P-Diagram Builder and Response Simulator")

st.caption(
    "Build a P-Diagram for robust design, then visualize how inputs, outputs, "
    "control factors and noise factors interact."
)


# =============================================================================
# Sidebar
# =============================================================================

with st.sidebar:
    st.subheader("🧭 Example mode")

    if st.session_state.example_mode == CUSTOM_MODE:
        st.warning(
            "You are working with a custom loaded P-Diagram. "
            "Loading a preset below will replace it."
        )

    preset_index = 0

    if st.session_state.example_mode in PRESET_MODES:
        preset_index = PRESET_MODES.index(st.session_state.example_mode)

    selected_preset = st.radio(
        "Choose preset example",
        options=PRESET_MODES,
        index=preset_index,
        key="sidebar_preset_selector",
    )

    if st.button("Load selected preset"):
        load_example(selected_preset)
        st.rerun()

    if st.session_state.example_mode == SIMPLE_MODE:
        st.info(
            "This mode shows the full app using a simple PA66 vs POM plastic gear example. "
            "It is best for teaching the P-Diagram logic."
        )

    elif st.session_state.example_mode == EXHAUSTIVE_MODE:
        st.info(
            "This mode shows a more realistic gear-transmission example. "
            "It is useful to explain the complexity of real engineering applications."
        )

    else:
        st.info(
            "This mode uses the custom P-Diagram loaded from JSON."
        )

    st.markdown("---")
    st.subheader("📋 Project")

    p["title"] = st.text_input(
        "Title",
        value=p.get("title", ""),
        key=f"title_{current_mode_key()}",
    )

    orientation_options = list(ORIENTATIONS.keys())
    current_orientation = p.get("orientation", "Left-to-Right")

    if current_orientation not in orientation_options:
        current_orientation = "Left-to-Right"

    p["orientation"] = st.selectbox(
        "Diagram orientation",
        orientation_options,
        index=orientation_options.index(current_orientation),
        key=f"orientation_{current_mode_key()}",
    )

    p["include_legend"] = st.checkbox(
        "Include legend",
        value=bool(p.get("include_legend", True)),
        key=f"legend_{current_mode_key()}",
    )

    st.markdown("---")
    st.subheader("📁 Save / Load")

    json_download(p, filename="p_diagram.json")

    uploaded = st.file_uploader(
        "Load from JSON",
        type=["json"],
    )

    if uploaded:
        try:
            loaded = json.load(uploaded)
            st.session_state.pdiag = {
                **copy.deepcopy(SIMPLE_MATERIAL_STATE),
                **loaded,
            }
            st.session_state.example_mode = CUSTOM_MODE
            st.success("Loaded custom P-Diagram from JSON.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not load JSON: {e}")

    if st.button("Reset current example"):
        reset_current_example()
        st.rerun()


# Refresh pointer after potential sidebar edits
p = st.session_state.pdiag
mode_key = current_mode_key()


# =============================================================================
# Tabs
# =============================================================================

tab_inputs, tab_factors, tab_diagram, tab_response, tab_export, tab_help = st.tabs(
    [
        "1. Inputs & Outputs",
        "2. Factors",
        "3. P-Diagram",
        "4. Response Simulator",
        "5. Export",
        "6. Help",
    ]
)


# =============================================================================
# Tab 1 — Inputs & Outputs
# =============================================================================

with tab_inputs:
    st.header("1. Inputs & Outputs")

    st.subheader("🎯 Intended Input Signal(s)")
    st.caption(
        "Signals, energy or information intentionally applied to the system. "
        "Do not place environmental disturbances here."
    )

    p["intended_input"] = text_to_list(
        st.text_area(
            "One intended input per line",
            value=list_to_text(p.get("intended_input", [])),
            height=150,
            key=f"txt_intended_input_{mode_key}",
        )
    )

    st.subheader("⚙️ Ideal Function")
    st.caption(
        "What the system should do when it transforms the intended input into the desired output."
    )

    p["ideal_function"] = text_to_list(
        st.text_area(
            "One ideal function statement per line",
            value=list_to_text(p.get("ideal_function", [])),
            height=150,
            key=f"txt_ideal_function_{mode_key}",
        )
    )

    st.subheader("✅ Desired Output(s)")
    st.caption(
        "Measurable expected outputs, performances or customer-relevant results."
    )

    p["desired_outputs"] = text_to_list(
        st.text_area(
            "One desired output per line",
            value=list_to_text(p.get("desired_outputs", [])),
            height=150,
            key=f"txt_desired_outputs_{mode_key}",
        )
    )

    st.subheader("⚠️ Error States / Undesired Output(s)")
    st.caption(
        "Failure manifestations, degraded outputs or loss of intended function."
    )

    p["error_states"] = text_to_list(
        st.text_area(
            "One error state per line",
            value=list_to_text(p.get("error_states", [])),
            height=150,
            key=f"txt_error_states_{mode_key}",
        )
    )


# =============================================================================
# Tab 2 — Factors
# =============================================================================

with tab_factors:
    st.header("2. Factors")

    st.subheader("🎚️ Control Factors")
    st.caption(
        "Design or process parameters the engineering team can specify, select or control."
    )

    control_df = normalize_table(
        p.get("control_factors", []),
        ["Factor", "Setting/Range", "Notes"],
    )

    edited_control_df = st.data_editor(
        control_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Factor": st.column_config.TextColumn("Factor"),
            "Setting/Range": st.column_config.TextColumn("Setting / Range"),
            "Notes": st.column_config.TextColumn("Notes"),
        },
        key=f"ed_control_{mode_key}",
    )

    p["control_factors"] = dataframe_to_records(edited_control_df)

    st.subheader("🌪️ Noise Factors")
    st.caption(
        "Uncontrolled or variable conditions: environment, usage, manufacturing scatter, aging and installation variation."
    )

    noise_df = normalize_table(
        p.get("noise_factors", []),
        ["Category", "Factor", "Notes"],
    )

    edited_noise_df = st.data_editor(
        noise_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Category": st.column_config.SelectboxColumn(
                "Category",
                options=NOISE_CATEGORIES,
                required=True,
            ),
            "Factor": st.column_config.TextColumn("Factor"),
            "Notes": st.column_config.TextColumn("Notes"),
        },
        key=f"ed_noise_{mode_key}",
    )

    p["noise_factors"] = dataframe_to_records(edited_noise_df)


# =============================================================================
# Tab 3 — P-Diagram
# =============================================================================

with tab_diagram:
    st.header("3. Live P-Diagram")

    if st.session_state.example_mode == SIMPLE_MODE:
        st.info(
            "Simple teaching example: the same P-Diagram logic is shown with only a few inputs, outputs, control factors and noise factors."
        )
    elif st.session_state.example_mode == EXHAUSTIVE_MODE:
        st.info(
            "Exhaustive realistic example: the same P-Diagram logic expands into a more complete engineering view."
        )

    dot = build_dot(p)

    st.graphviz_chart(
        dot,
        use_container_width=True,
    )

    with st.expander("Show Graphviz DOT source"):
        st.code(dot, language="dot")


# =============================================================================
# Tab 4 — Response Simulator
# =============================================================================

with tab_response:
    st.header("4. Input-Output Response Simulator")

    if st.session_state.example_mode == SIMPLE_MODE:
        st.markdown(
            """
This tab shows the simplified PA66 vs POM material-comparison case.

The selected materials change the mean response curves. Noise factors create the scatter bands.

This mode is useful for explaining the P-Diagram logic clearly.
"""
        )

        simple_inputs = p.get("intended_input", []) or SIMPLE_MATERIAL_STATE["intended_input"]
        simple_outputs = p.get("desired_outputs", []) or SIMPLE_MATERIAL_STATE["desired_outputs"]
        simple_noise_factors = get_factor_names(p.get("noise_factors", []))

        if not simple_noise_factors:
            simple_noise_factors = [
                "Load variation",
                "Temperature variation",
                "Dust / contamination",
                "Dimensional variation",
            ]

        st.subheader("A. Select materials, input and output")

        col1, col2, col3 = st.columns(3)

        with col1:
            selected_materials = st.multiselect(
                "Gear materials to compare",
                options=["PA66", "POM"],
                default=["PA66", "POM"],
                key=f"simple_materials_selected_{mode_key}",
            )

        with col2:
            selected_input = st.selectbox(
                "x-axis: input",
                options=simple_inputs,
                key=f"simple_material_selected_input_{mode_key}",
            )

        with col3:
            selected_output = st.selectbox(
                "y-axis: output",
                options=simple_outputs,
                key=f"simple_material_selected_output_{mode_key}",
            )

        if not selected_materials:
            st.warning("Select at least one material to plot.")
            st.stop()

        st.subheader("B. Input range and simulation settings")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            x_min = st.number_input(
                "Input minimum",
                value=0.0,
                step=1.0,
                key=f"simple_material_x_min_{mode_key}",
            )

        with col2:
            x_max = st.number_input(
                "Input maximum",
                value=100.0,
                step=1.0,
                key=f"simple_material_x_max_{mode_key}",
            )

        with col3:
            n_points = st.slider(
                "Number of calculated points",
                min_value=20,
                max_value=500,
                value=120,
                step=10,
                key=f"simple_material_n_points_{mode_key}",
            )

        with col4:
            seed = st.number_input(
                "Random seed",
                value=42,
                step=1,
                key=f"simple_material_seed_{mode_key}",
            )

        show_band = st.checkbox(
            "Show scatter band",
            value=True,
            key=f"simple_material_show_band_{mode_key}",
        )

        st.subheader("C. Noise factor settings")

        noise_settings = {}

        selected_noise_factors = st.multiselect(
            "Select noise factors",
            options=simple_noise_factors,
            default=simple_noise_factors,
            key=f"simple_material_selected_noise_factors_{mode_key}",
        )

        for factor in selected_noise_factors:
            noise_settings[factor] = st.slider(
                factor,
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                step=0.05,
                key=f"simple_material_noise_setting_{mode_key}_{safe_key(factor)}",
                help="0 = negligible variation; 1 = severe variation.",
            )

        st.subheader("D. Response plot")

        if x_max <= x_min:
            st.error("Input maximum must be greater than input minimum.")
        else:
            df_response = build_material_response_data(
                selected_materials=selected_materials,
                input_name=selected_input,
                output_name=selected_output,
                noise_settings=noise_settings,
                n_points=int(n_points),
                seed=int(seed),
                x_min=float(x_min),
                x_max=float(x_max),
            )

            fig = build_material_response_figure(
                df=df_response,
                input_name=selected_input,
                output_name=selected_output,
                show_band=show_band,
            )

            st.plotly_chart(fig, use_container_width=True)

            with st.expander("Interpretation"):
                st.markdown(
                    f"""
Behavior name:

{behavior_label(selected_input, selected_output)}

This plot compares PA66 and POM under the same input range and the same noise-factor settings.

In this simplified teaching model, POM is represented with higher efficiency, better wear resistance and a narrower scatter band.

PA66 is represented with lower efficiency, lower wear resistance and a wider scatter band.

Material choice changes the mean response curve.

Noise factors create variation around each mean curve.

This is a conceptual model for explaining robust design. It is not a validated material model.
"""
                )

            with st.expander("Material assumptions used in the simplified model"):
                st.dataframe(
                    pd.DataFrame(MATERIAL_PRESETS).T,
                    use_container_width=True,
                )
                st.caption(
                    "These values are illustrative assumptions for teaching robust design. "
                    "They are not validated material data."
                )

            with st.expander("Simulation data"):
                st.dataframe(df_response, use_container_width=True)

            csv = df_response.to_csv(index=False).encode("utf-8")

            st.download_button(
                "⬇️ Download response simulation data as CSV",
                data=csv,
                file_name="simple_material_response_simulation.csv",
                mime="text/csv",
            )

    else:
        st.markdown(
            """
This tab shows a generic response model based on the current P-Diagram.

The selected input is plotted on the x-axis. The selected output is plotted on the y-axis.
Control factors modify the mean response curve. Noise factors create scatter around the curve.

This mode is useful for showing the complexity of real engineering applications.
"""
        )

        inputs = p.get("intended_input", []) or DEFAULT_STATE["intended_input"]
        outputs = p.get("desired_outputs", []) or DEFAULT_STATE["desired_outputs"]

        control_factor_names = get_factor_names(p.get("control_factors", []))
        noise_factor_names = get_factor_names(p.get("noise_factors", []))

        st.subheader("A. Select input and output")

        col1, col2 = st.columns(2)

        with col1:
            selected_input = st.selectbox(
                "x-axis: input signal",
                options=inputs,
                key=f"generic_response_selected_input_{mode_key}",
            )

        with col2:
            selected_output = st.selectbox(
                "y-axis: desired output",
                options=outputs,
                key=f"generic_response_selected_output_{mode_key}",
            )

        st.subheader("B. Base response settings")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            x_min = st.number_input(
                "Input minimum",
                value=0.0,
                step=1.0,
                key=f"generic_response_x_min_{mode_key}",
            )

        with col2:
            x_max = st.number_input(
                "Input maximum",
                value=100.0,
                step=1.0,
                key=f"generic_response_x_max_{mode_key}",
            )

        with col3:
            base_offset = st.number_input(
                "Output baseline",
                value=10.0,
                step=1.0,
                key=f"generic_response_base_offset_{mode_key}",
            )

        with col4:
            base_slope = st.number_input(
                "Output range / sensitivity",
                value=80.0,
                step=1.0,
                key=f"generic_response_base_slope_{mode_key}",
            )

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            base_curvature = st.slider(
                "Base curvature",
                min_value=0.3,
                max_value=3.0,
                value=1.0,
                step=0.1,
                help=(
                    "1.0 = linear; above 1.0 = stronger effect at high input; "
                    "below 1.0 = stronger effect at low input."
                ),
                key=f"generic_response_base_curvature_{mode_key}",
            )

        with col2:
            n_points = st.slider(
                "Number of simulated points",
                min_value=20,
                max_value=500,
                value=120,
                step=10,
                key=f"generic_response_n_points_{mode_key}",
            )

        with col3:
            seed = st.number_input(
                "Random seed",
                value=42,
                step=1,
                key=f"generic_response_seed_{mode_key}",
            )

        with col4:
            show_band = st.checkbox(
                "Show noise band",
                value=True,
                key=f"generic_response_show_band_{mode_key}",
            )

        show_scatter = st.checkbox(
            "Show simulated scatter points",
            value=True,
            key=f"generic_response_show_scatter_{mode_key}",
        )

        st.subheader("C. Control factor settings")

        st.caption(
            "Control factors are design choices. They modify slope, baseline or curvature of the response."
        )

        control_settings = {}
        control_effects = {}

        if not control_factor_names:
            st.warning("No control factors available.")
        else:
            selected_control_factors = st.multiselect(
                "Select control factors to include in the response model",
                options=control_factor_names,
                default=control_factor_names[: min(5, len(control_factor_names))],
                key=f"generic_response_selected_control_factors_{mode_key}",
            )

            for factor in selected_control_factors:
                with st.expander(f"Control factor: {factor}", expanded=False):
                    control_effects[factor] = st.selectbox(
                        "Effect on response",
                        options=[
                            "Slope / sensitivity",
                            "Offset / baseline",
                            "Curvature / non-linearity",
                        ],
                        key=f"generic_response_control_effect_{mode_key}_{safe_key(factor)}",
                    )

                    control_settings[factor] = st.slider(
                        "Control factor setting",
                        min_value=-1.0,
                        max_value=1.0,
                        value=0.0,
                        step=0.05,
                        key=f"generic_response_control_setting_{mode_key}_{safe_key(factor)}",
                        help=(
                            "-1 = weaker / unfavorable setting; "
                            "+1 = stronger / favorable setting."
                        ),
                    )

        st.subheader("D. Noise factor settings")

        st.caption(
            "Noise factors represent real-world variation. They increase the scatter around the mean response."
        )

        noise_settings = {}

        if not noise_factor_names:
            st.warning("No noise factors available.")
        else:
            selected_noise_factors = st.multiselect(
                "Select noise factors to include in the response model",
                options=noise_factor_names,
                default=noise_factor_names[: min(5, len(noise_factor_names))],
                key=f"generic_response_selected_noise_factors_{mode_key}",
            )

            for factor in selected_noise_factors:
                noise_settings[factor] = st.slider(
                    factor,
                    min_value=0.0,
                    max_value=1.0,
                    value=0.3,
                    step=0.05,
                    key=f"generic_response_noise_setting_{mode_key}_{safe_key(factor)}",
                    help="0 = negligible variation; 1 = severe variation.",
                )

        st.subheader("E. Response plot")

        if x_max <= x_min:
            st.error("Input maximum must be greater than input minimum.")
        else:
            df_response = build_response_data(
                input_name=selected_input,
                output_name=selected_output,
                control_settings=control_settings,
                control_effects=control_effects,
                noise_settings=noise_settings,
                n_points=int(n_points),
                seed=int(seed),
                x_min=float(x_min),
                x_max=float(x_max),
                base_slope=float(base_slope),
                base_offset=float(base_offset),
                base_curvature=float(base_curvature),
            )

            fig = build_response_figure(
                df=df_response,
                input_name=selected_input,
                output_name=selected_output,
                show_scatter=show_scatter,
                show_band=show_band,
            )

            st.plotly_chart(fig, use_container_width=True)

            with st.expander("Interpretation"):
                st.markdown(
                    f"""
Behavior name:

{behavior_label(selected_input, selected_output)}

Selected input:

{selected_input}

Selected output:

{selected_output}

Response interpretation:

{df_response["response_interpretation"].iloc[0]}

The curve represents the expected deterministic relationship between input and output.

Control factors modify the mean response.

Noise factors create output variation around the mean response.
"""
                )

            with st.expander("Simulation data"):
                st.dataframe(df_response, use_container_width=True)

            csv = df_response.to_csv(index=False).encode("utf-8")

            st.download_button(
                "⬇️ Download response simulation data as CSV",
                data=csv,
                file_name="generic_response_simulation.csv",
                mime="text/csv",
            )


# =============================================================================
# Tab 5 — Export
# =============================================================================

with tab_export:
    st.header("5. Export")

    st.write(
        "Download the current P-Diagram as JSON, SVG or PNG. "
        "The JSON file can be loaded again later."
    )

    json_download(p, filename="p_diagram.json")

    dot = build_dot(p)

    col1, col2 = st.columns(2)

    with col1:
        try:
            svg_buf = export_graph(dot, "svg")
            st.download_button(
                "⬇️ Download SVG",
                data=svg_buf,
                file_name="p_diagram.svg",
                mime="image/svg+xml",
            )
        except Exception as e:
            st.info("SVG export not available on this system.")
            st.caption(f"Details: {e}")

    with col2:
        try:
            png_buf = export_graph(dot, "png")
            st.download_button(
                "⬇️ Download PNG",
                data=png_buf,
                file_name="p_diagram.png",
                mime="image/png",
            )
        except Exception as e:
            st.info("PNG export not available on this system.")
            st.caption(f"Details: {e}")


# =============================================================================
# Tab 6 — Help
# =============================================================================

with tab_help:
    st.header("6. Help")

    st.subheader("What is a P-Diagram?")

    st.markdown(
        """
A Parameter Diagram describes how a system should transform intended inputs into desired outputs, and how this transformation can be disturbed by real-world variation.

Core logic:

Input signal + Control factors + Noise factors → System / Ideal function → Desired output or undesired output
"""
    )

    st.subheader("Meaning of each element")

    st.markdown(
        """
| P-Diagram element | Meaning | FMEA connection |
|---|---|---|
| Input signal | What intentionally enters the system | Operating condition / input |
| Ideal function | What the system should do | Function |
| Desired output | What should be achieved | Requirement |
| Error state | What goes wrong | Failure mode / failure effect |
| Control factor | Design or process choice | Prevention control |
| Noise factor | Uncontrolled variation | Cause / usage / environment / variation |
"""
    )

    st.subheader("Why two examples are available")

    st.markdown(
        """
| Example | Purpose |
|---|---|
| Simple teaching example — PA66 vs POM | Shows the full P-Diagram logic with a very simple plastic gear material comparison |
| Exhaustive realistic example — Full gear transmission | Shows how the same logic expands in a real engineering application |

The simple example is best for explaining the method.

The exhaustive example is best for showing what happens in reality: more inputs, more outputs, more control factors, more noise factors and more failure mechanisms.
"""
    )

    st.subheader("Behavior terminology")

    st.markdown(
        """
For a spring, force versus displacement is usually described by stiffness or compliance.

For the plastic gear example:

| x-axis | y-axis | Suggested behavior name |
|---|---|---|
| Transmitted torque | Efficiency | Torque-efficiency characteristic |
| Transmitted torque | Wear resistance index | Torque-wear characteristic |
| Transmitted torque | Efficiency / wear for PA66 vs POM | Material-dependent performance characteristic |
"""
    )

    st.subheader("Important rule")

    st.info(
        "Ambient temperature, dust, moisture, aging, usage variability and manufacturing scatter "
        "are normally noise factors, not intended inputs."
    )

    st.subheader("Run locally")

    st.code(
        "pip install streamlit pandas numpy plotly graphviz\n"
        "streamlit run p_diagram_merged_app.py",
        language="bash",
    )

    st.caption(
        "For SVG/PNG export, install the Graphviz system binaries in addition to the Python package."
    )
