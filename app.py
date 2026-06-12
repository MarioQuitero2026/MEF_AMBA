"""
AMBA I — Dashboard Interactivo
app.py — Streamlit cloud-native, sin dependencia de Excel ni macros.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from params import (Params, Controles, Macro, Deuda, WaccParams,
                    Capex, Opex, Equity, Cronograma)
from timeline import build_timeline
from financiacion import optimizar_rcop, barrido_rcop, calcular_tir
from resultados import calcular_resultados

# ─────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AMBA I — MEF Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

AZUL   = "#10069F"
CYAN   = "#00B5E2"
ROJO   = "#DA291C"
GRIS   = "#F0F2F6"
GRIS_OSCURO = "#E4E7EF"

st.markdown(f"""
<style>
    /* ── Tipografía global IDOM: Arial ── */
    html, body, [class*="css"] {{
        font-family: Arial, sans-serif;
    }}

    /* ── Fondo principal ── */
    .main .block-container {{
        background-color: white;
        padding-top: 1.5rem;
    }}

    /* ── Header superior: banda azul IDOM ── */
    .idom-header {{
        background: {AZUL};
        padding: 14px 24px 12px 24px;
        margin: -1.5rem -1rem 1.5rem -1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    .idom-header .idom-project {{
        color: white;
        font-size: 15px;
        font-weight: 600;
        letter-spacing: 0.3px;
    }}
    .idom-header .idom-sub {{
        color: {CYAN};
        font-size: 12px;
        font-weight: 400;
        margin-top: 2px;
    }}
    .idom-badge {{
        background: {CYAN};
        color: {AZUL};
        font-weight: 700;
        font-size: 12px;
        padding: 4px 10px;
        border-radius: 4px;
        letter-spacing: 0.5px;
    }}
    .idom-badge-off {{
        background: {ROJO};
        color: white;
        font-weight: 700;
        font-size: 12px;
        padding: 4px 10px;
        border-radius: 4px;
    }}

    /* ── Metric cards ── */
    .metric-card {{
        background: white;
        border-left: 4px solid {AZUL};
        border-radius: 6px;
        padding: 12px 16px;
        margin: 4px 0;
        box-shadow: 0 1px 3px rgba(16,6,159,0.10);
    }}
    .metric-card .label {{
        font-size: 11px;
        color: #555;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    .metric-card .value {{
        font-size: 24px;
        color: {AZUL};
        font-weight: 700;
        line-height: 1.2;
        margin-top: 2px;
    }}
    .metric-card .delta {{
        font-size: 11px;
        color: #888;
        margin-top: 2px;
    }}
    .metric-card-cyan {{
        border-left-color: {CYAN};
    }}
    .metric-card-cyan .value {{
        color: #007AAA;
    }}
    .metric-card-rojo {{
        border-left-color: {ROJO};
    }}
    .metric-card-rojo .value {{
        color: {ROJO};
    }}

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 2px;
        background: {GRIS};
        border-radius: 6px;
        padding: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 4px;
        font-family: Arial, sans-serif;
        font-weight: 600;
        font-size: 13px;
        color: #555;
        padding: 6px 16px;
    }}
    .stTabs [aria-selected="true"] {{
        background: {AZUL} !important;
        color: white !important;
    }}

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {{
        background: {GRIS};
        border-right: 2px solid {GRIS_OSCURO};
    }}
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {{
        color: {AZUL};
        font-family: Arial, sans-serif;
    }}

    /* ── Section dividers ── */
    .idom-section {{
        border-left: 3px solid {CYAN};
        padding-left: 10px;
        margin: 16px 0 8px 0;
        color: {AZUL};
        font-weight: 700;
        font-size: 14px;
        letter-spacing: 0.3px;
    }}

    /* ── Slider accent color ── */
    .stSlider [data-baseweb="slider"] {{
        color: {AZUL};
    }}

    /* ── Botones ── */
    .stButton > button {{
        background-color: {AZUL};
        color: white;
        font-family: Arial, sans-serif;
        font-weight: 600;
        border: none;
        border-radius: 4px;
        padding: 8px 20px;
    }}
    .stButton > button:hover {{
        background-color: #0D0585;
        color: white;
    }}

    /* ── Títulos ── */
    h1, h2, h3 {{ color: {AZUL}; font-family: Arial, sans-serif; }}

    /* ── Footer IDOM ── */
    .idom-footer {{
        border-top: 2px solid {AZUL};
        padding: 10px 0 0 0;
        margin-top: 24px;
        color: #888;
        font-size: 11px;
        display: flex;
        justify-content: space-between;
    }}
</style>
""", unsafe_allow_html=True)


def metric_card(label, value, delta=""):
    st.markdown(f"""
    <div class="metric-card">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        <div class="delta">{delta}</div>
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# SIDEBAR — Parámetros
# ─────────────────────────────────────────────────────────────────────
st.sidebar.image("idom_logo.png", width=110)
st.sidebar.markdown(
    f"<div style='height:2px; background:{AZUL}; margin: 6px 0 14px 0; border-radius:1px'></div>",
    unsafe_allow_html=True
)
st.sidebar.title("Parámetros del Modelo")

st.sidebar.markdown("### Selectores de Escenario")
rigi          = st.sidebar.toggle("CON RIGI",                    value=True)
cap_global    = st.sidebar.toggle("CAPEX Global (Curva S)",      value=True)
inf_rcop      = st.sidebar.toggle("Indexar RCOP a IPC",          value=True)
capitalizar   = st.sidebar.toggle("Capitalizar intereses",       value=True)
beta_fija_tog = st.sidebar.toggle("Beta fija (sin Hamada)",      value=True)

st.sidebar.markdown("### Estructura de Capital")
pct_deuda_pct = st.sidebar.slider("% Deuda", 0, 90, 80, step=5,
                               format="%d%%",
                               help="Proporción de deuda sobre CAPEX total")
pct_deuda = pct_deuda_pct / 100

st.sidebar.markdown("### Costo de Capital")
kd_anual_pct = st.sidebar.slider("Kd (costo deuda nominal EA)", 6.0, 20.0, 12.0,
                               step=0.5, format="%.1f%%")
kd_anual = kd_anual_pct / 100

rf_pct   = st.sidebar.slider("Tasa libre de riesgo (RF)", 1.0, 6.0, 2.86,
                               step=0.1, format="%.2f%%")
rf = rf_pct / 100

rp_default = 8.0 if rigi else 10.0
rp_min     = 4.0 if rigi else 6.0
rp_pct     = st.sidebar.slider("Riesgo país",
                               rp_min, 18.0, rp_default,
                               step=0.5, format="%.1f%%")
rp = rp_pct / 100

beta_u   = st.sidebar.slider("Beta desapalancada", 0.15, 0.60, 0.30, step=0.05,
                              format="%.2f")

st.sidebar.markdown("### CAPEX y OPEX")
capex_total = st.sidebar.number_input(
    "CAPEX Total (USD M)",
    min_value=500.0, max_value=1200.0,
    value=848.65 if rigi else 898.02,
    step=10.0,
)
tasa_opex_pct = st.sidebar.slider("OPEX total (% CAPEX EA)", 0.5, 4.0, 1.63, step=0.1,
                               format="%.2f%%",
                               help="Porcentaje del CAPEX como OPEX anual")
tasa_opex = tasa_opex_pct / 100

st.sidebar.markdown("---")
run_button = st.sidebar.button("▶ Ejecutar Modelo", type="primary", use_container_width=True)
run_barrido = st.sidebar.button("📊 Barrido Completo RCOP", use_container_width=True)

# ─────────────────────────────────────────────────────────────────────
# CONSTRUIR PARAMS
# ─────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def get_timeline():
    return build_timeline()

def build_params() -> Params:
    p = Params()
    p.controles.rigi              = rigi
    p.controles.capex_global      = cap_global
    p.controles.inflacion_rcop    = inf_rcop
    p.controles.capitalizar_intereses = capitalizar
    p.controles.beta_fija         = beta_fija_tog
    p.deuda.kd_anual              = kd_anual
    p.deuda.pct_deuda             = pct_deuda
    p.wacc.rf                     = rf
    p.wacc.riesgo_pais_rigi       = rp if rigi else p.wacc.riesgo_pais_rigi
    p.wacc.riesgo_pais_sin_rigi   = rp if not rigi else p.wacc.riesgo_pais_sin_rigi
    p.wacc.beta_desapalancada     = beta_u
    p.capex.capex_total_rigi      = capex_total * 1e6
    p.capex.capex_total_sin_rigi  = capex_total * 1e6
    p.opex.seguros_polizas        = tasa_opex * 0.15
    p.opex.personal               = tasa_opex * 0.25
    p.opex.mantenimiento          = tasa_opex * 0.30
    p.opex.operacion_sistema      = tasa_opex * 0.12
    p.opex.logistica              = tasa_opex * 0.06
    p.opex.impuestos_operacion    = tasa_opex * 0.12
    return p


# ─────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────
badge_html = (f"<span class='idom-badge'>CON RIGI</span>" if rigi
              else f"<span class='idom-badge-off'>SIN RIGI</span>")
st.markdown(f"""
<div class="idom-header">
    <div>
        <div class="idom-project">AMBA I — Modelo Económico Financiero</div>
        <div class="idom-sub">Concesión de Obra Pública · Transmisión Eléctrica 500/220/132 kV · Argentina</div>
    </div>
    <div style="display:flex; align-items:center; gap:12px;">
        {badge_html}
        <div style="color:{CYAN}; font-size:12px; text-align:right;">
            Deuda: {pct_deuda:.0%} &nbsp;|&nbsp; Kd: {kd_anual:.1%}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# ESTADO DE SESIÓN
# ─────────────────────────────────────────────────────────────────────
if "res" not in st.session_state:
    st.session_state.res = None
if "df_barrido" not in st.session_state:
    st.session_state.df_barrido = None

# ─────────────────────────────────────────────────────────────────────
# EJECUCIÓN
# ─────────────────────────────────────────────────────────────────────
tl = get_timeline()

if run_button or st.session_state.res is None:
    with st.spinner("Optimizando RCOP..."):
        try:
            p = build_params()
            res_opt = optimizar_rcop(pct_deuda, p, tl, verbose=False)
            res = calcular_resultados(res_opt["rcop_vpn"], pct_deuda, p, tl)
            res["tir_proyecto"] = calcular_tir(res["df_financiacion"]["fcff"].values)
            res["tir_equity"]   = calcular_tir(res["df_financiacion"]["fcfe"].values)
            st.session_state.res = res
            st.session_state.p   = p
        except Exception as e:
            st.error(f"Error en optimización: {e}")
            st.stop()

if run_barrido:
    with st.spinner("Ejecutando barrido completo (0%–90% deuda)..."):
        try:
            p = build_params()
            df_b = barrido_rcop(p, tl,
                                pct_deuda_range=np.arange(0.0, 0.91, 0.05),
                                verbose=False)
            st.session_state.df_barrido = df_b
        except Exception as e:
            st.error(f"Error en barrido: {e}")

res = st.session_state.res
if res is None:
    st.stop()

df_fin  = res["df_financiacion"].copy()
df_c    = res["df_cfdas"].copy()
df_cap  = res["df_capex"].copy()

# Forzar dtype datetime en columna bop (puede llegar como object en Streamlit Cloud)
for _df in [df_fin, df_c, df_cap]:
    _df["bop"] = pd.to_datetime(_df["bop"])

# ─────────────────────────────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────────────────────────────
st.markdown(f"<div class='idom-section'>Indicadores Clave</div>", unsafe_allow_html=True)

tir_p = res.get('tir_proyecto', 0) or 0
tir_e = res.get('tir_equity',   0) or 0
vpn_fcfe_val = res.get('vpn_equity', 0) or 0
vpn_fcff_val = res.get('vpn_proyecto', 0) or 0

# Semáforo VPN FCFE: verde si ≈ 0, amarillo si pequeño, rojo si grande
vpn_fcfe_abs = abs(vpn_fcfe_val)
if vpn_fcfe_abs < 1_000:          # < USD 1,000 → prácticamente cero
    fcfe_color_class = ""
    fcfe_delta = "≈ 0  ✓  Ke satisfecha"
elif vpn_fcfe_abs < 1_000_000:    # < 1M → aceptable
    fcfe_color_class = "metric-card-cyan"
    fcfe_delta = f"{'↑' if vpn_fcfe_val > 0 else '↓'} USD {vpn_fcfe_val/1e6:.3f}M vs 0"
else:                              # > 1M → revisar
    fcfe_color_class = "metric-card-rojo"
    fcfe_delta = f"{'↑' if vpn_fcfe_val > 0 else '↓'} USD {vpn_fcfe_val/1e6:.2f}M vs 0"

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
with c1:
    metric_card("RCOP (VPN)", f"USD {res['rcop_vpn']/1e6:.0f}M",
                "Variable de licitación")
with c2:
    st.markdown(f"""
    <div class="metric-card {fcfe_color_class}">
        <div class="label">VPN FCFE</div>
        <div class="value">USD {vpn_fcfe_val/1e6:.2f}M</div>
        <div class="delta">{fcfe_delta}</div>
    </div>""", unsafe_allow_html=True)
with c3:
    metric_card("VPN FCFF", f"USD {vpn_fcff_val/1e6:.1f}M",
                f"Tasa: WACC {res['wacc_anual']:.2%}")
with c4:
    metric_card("TIR Equity", f"{tir_e:.2%}",
                f"Ke objetivo: {res['ke_anual']:.2%}")
with c5:
    metric_card("TIR Proyecto", f"{tir_p:.2%}",
                f"WACC: {res['wacc_anual']:.2%}")
with c6:
    metric_card("WACC", f"{res['wacc_anual']:.2%}",
                f"Ke: {res['ke_anual']:.2%}")
with c7:
    deuda_total = res['deuda_max_t1'] + res['deuda_max_t2']
    metric_card("Deuda T1+T2",
                f"USD {deuda_total/1e6:.0f}M",
                f"{pct_deuda:.0%} del CAPEX")

st.divider()

# ─────────────────────────────────────────────────────────────────────
# GRÁFICOS PRINCIPALES
# ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Flujos de Caja",
    "🏗️ CAPEX & Deuda",
    "💰 RCOP & Remuneración",
    "📊 Barrido RCOP",
    "🔢 Tabla Detallada",
])

# ── TAB 1: FLUJOS ────────────────────────────────────────────────────
with tab1:
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=("FCFF y FCFE Mensual (USD M)", "CFDAS vs Servicio Deuda (USD M)"),
        vertical_spacing=0.12,
    )
    bop = df_fin["bop"].dt.to_pydatetime()
    fig.add_trace(go.Scatter(
        x=bop, y=df_fin["fcff"]/1e6,
        name="FCFF", line=dict(color=AZUL, width=1.5),
        fill="tozeroy", fillcolor=f"rgba(16,6,159,0.08)"
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=bop, y=df_fin["fcfe"]/1e6,
        name="FCFE", line=dict(color=CYAN, width=1.5),
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        x=bop, y=df_fin["cfdas"]/1e6,
        name="CFDAS", marker_color=f"rgba(16,6,159,0.3)"
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=bop, y=df_fin["servicio_total"]/1e6,
        name="Servicio Deuda", line=dict(color=ROJO, width=1.5),
    ), row=2, col=1)
    fig.update_layout(height=520, template="plotly_white",
                      legend=dict(orientation="h", y=-0.1),
                      font=dict(family="Arial"))
    fig.update_yaxes(title_text="USD M")
    st.plotly_chart(fig, use_container_width=True)

    # DSCR
    dscr = df_fin.dropna(subset=["dscr_t1"])
    if not dscr.empty:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=dscr["bop"].dt.to_pydatetime(), y=dscr["dscr_t1"],
            name="DSCR T1", line=dict(color=AZUL)
        ))
        fig2.add_hline(y=1.20, line_dash="dash", line_color=ROJO,
                       annotation_text="DSCR mínimo 1.20x")
        fig2.update_layout(title="DSCR Mensual — Tramo 1",
                           height=280, template="plotly_white",
                           font=dict(family="Arial"))
        st.plotly_chart(fig2, use_container_width=True)

# ── TAB 2: CAPEX & DEUDA ─────────────────────────────────────────────
with tab2:
    col_a, col_b = st.columns(2)
    with col_a:
        fig3 = go.Figure()
        bop = df_cap["bop"].dt.to_pydatetime()
        fig3.add_trace(go.Bar(x=bop, y=df_cap["capex_total_e1"]/1e6,
                              name="CAPEX E1", marker_color=AZUL))
        fig3.add_trace(go.Bar(x=bop, y=df_cap["capex_total_e2"]/1e6,
                              name="CAPEX E2", marker_color=CYAN))
        fig3.update_layout(barmode="stack", title="Desembolso CAPEX mensual (USD M)",
                           height=350, template="plotly_white",
                           font=dict(family="Arial"))
        st.plotly_chart(fig3, use_container_width=True)

    with col_b:
        fig4 = go.Figure()
        bop = df_fin["bop"].dt.to_pydatetime()
        fig4.add_trace(go.Scatter(x=bop, y=df_fin["saldo_t1"]/1e6,
                                  name="Saldo T1", line=dict(color=AZUL, width=2),
                                  fill="tozeroy", fillcolor="rgba(16,6,159,0.10)"))
        fig4.add_trace(go.Scatter(x=bop, y=df_fin["saldo_t2"]/1e6,
                                  name="Saldo T2", line=dict(color=CYAN, width=2),
                                  fill="tozeroy", fillcolor="rgba(0,181,226,0.10)"))
        fig4.update_layout(title="Saldo de Deuda (USD M)",
                           height=350, template="plotly_white",
                           font=dict(family="Arial"))
        st.plotly_chart(fig4, use_container_width=True)

    # Depreciación
    fig5 = go.Figure()
    fig5.add_trace(go.Scatter(x=df_cap["bop"].dt.to_pydatetime(),
                              y=df_cap["depreciacion_total"]/1e6,
                              name="Depreciación", line=dict(color=AZUL),
                              fill="tozeroy", fillcolor="rgba(16,6,159,0.06)"))
    fig5.update_layout(title="Depreciación mensual acumulada (USD M)",
                       height=250, template="plotly_white",
                       font=dict(family="Arial"))
    st.plotly_chart(fig5, use_container_width=True)

# ── TAB 3: RCOP & REMUNERACIÓN ───────────────────────────────────────
with tab3:
    fig6 = go.Figure()
    bop = df_c["bop"].dt.to_pydatetime()
    fig6.add_trace(go.Scatter(
        x=bop, y=df_c["ingresos"]/1e6,
        name="RCOP mensual", line=dict(color=AZUL, width=2),
        fill="tozeroy", fillcolor="rgba(16,6,159,0.10)"
    ))
    fig6.add_trace(go.Scatter(
        x=bop, y=df_c["opex"]/1e6,
        name="OPEX mensual", line=dict(color=ROJO, width=1.5, dash="dot"),
    ))
    fig6.update_layout(
        title=f"Remuneración RCOP mensual (USD M) | VPN = USD {res['rcop_vpn']/1e6:.0f}M",
        height=380, template="plotly_white", font=dict(family="Arial")
    )
    st.plotly_chart(fig6, use_container_width=True)

    # Acumulado
    df_c_plot = df_c.copy()
    df_c_plot["rcop_acumulado"] = df_c_plot["ingresos"].cumsum()
    fig7 = go.Figure()
    fig7.add_trace(go.Scatter(
        x=df_c_plot["bop"].dt.to_pydatetime(),
        y=df_c_plot["rcop_acumulado"]/1e6,
        name="RCOP acumulado",
        line=dict(color=CYAN, width=2),
    ))
    fig7.add_hline(y=res["rcop_vpn"]/1e6, line_dash="dash", line_color=AZUL,
                   annotation_text=f"VPN RCOP = USD {res['rcop_vpn']/1e6:.0f}M")
    fig7.update_layout(title="RCOP Acumulado nominal (USD M)",
                       height=280, template="plotly_white",
                       font=dict(family="Arial"))
    st.plotly_chart(fig7, use_container_width=True)

# ── TAB 4: BARRIDO ───────────────────────────────────────────────────
with tab4:
    df_b = st.session_state.df_barrido
    if df_b is None:
        st.info("Presiona **Barrido Completo RCOP** en la barra lateral para ejecutar el análisis.")
    else:
        df_b_valid = df_b.dropna(subset=["rcop_vpn"])

        fig8 = make_subplots(rows=1, cols=2,
                             subplot_titles=("RCOP VPN por % Deuda",
                                             "WACC y Ke por % Deuda"))
        fig8.add_trace(go.Scatter(
            x=df_b_valid["pct_deuda"] * 100,
            y=df_b_valid["rcop_vpn"] / 1e6,
            mode="lines+markers",
            name="RCOP VPN (USD M)",
            line=dict(color=AZUL, width=2),
            marker=dict(size=8,
                        color=[AZUL if e == "Sí" else ROJO
                               for e in df_b_valid["elegible"]])
        ), row=1, col=1)
        fig8.add_vline(x=pct_deuda * 100, line_dash="dash", line_color=ROJO,
                       row=1, col=1)

        fig8.add_trace(go.Scatter(
            x=df_b_valid["pct_deuda"] * 100,
            y=df_b_valid["wacc_anual"] * 100,
            name="WACC (%)",
            line=dict(color=AZUL, width=2),
        ), row=1, col=2)
        fig8.add_trace(go.Scatter(
            x=df_b_valid["pct_deuda"] * 100,
            y=df_b_valid["ke_anual"] * 100,
            name="Ke (%)",
            line=dict(color=CYAN, width=2),
        ), row=1, col=2)

        fig8.update_layout(height=400, template="plotly_white",
                           font=dict(family="Arial"),
                           legend=dict(orientation="h", y=-0.15))
        fig8.update_xaxes(title_text="% Deuda")
        fig8.update_yaxes(title_text="USD M", row=1, col=1)
        fig8.update_yaxes(title_text="%", row=1, col=2)
        st.plotly_chart(fig8, use_container_width=True)

        # Tabla del barrido
        def _fmt_saldo(v):
            if v is None: return "—"
            return "✓  0" if abs(v) < 1_000 else f"✗  {v/1e6:.2f}M"

        def _fmt_vpn(v):
            if v is None: return "—"
            return "✓  ≈0" if abs(v) < 1_000 else f"✗  {v/1e6:.3f}M"

        st.dataframe(
            df_b_valid.assign(**{
                "% Deuda":       (df_b_valid["pct_deuda"] * 100).map("{:.0f}%".format),
                "RCOP (USD M)":  (df_b_valid["rcop_vpn"] / 1e6).map("{:.1f}".format),
                "WACC":          (df_b_valid["wacc_anual"] * 100).map("{:.2f}%".format),
                "Ke":            (df_b_valid["ke_anual"] * 100).map("{:.2f}%".format),
                "VPN FCFE":      df_b_valid["vpn_fcfe"].map(_fmt_vpn),
                "Deuda T1 paga": df_b_valid["saldo_final_t1"].map(_fmt_saldo),
                "Deuda T2 paga": df_b_valid["saldo_final_t2"].map(_fmt_saldo),
                "Elegible":      df_b_valid["elegible"],
            })[[
                "% Deuda", "RCOP (USD M)", "WACC", "Ke",
                "VPN FCFE", "Deuda T1 paga", "Deuda T2 paga", "Elegible"
            ]],
            hide_index=True,
            use_container_width=True,
        )

# ── TAB 5: TABLA ────────────────────────────────────────────────────
with tab5:
    st.markdown("**Flujos mensuales completos**")
    tabla = df_fin[["periodo", "bop", "cfdas", "desembolso_total",
                    "saldo_total", "servicio_total", "intereses_total",
                    "imp_ganancias", "imp_dcb", "fcff", "fcfe"]].copy()
    tabla["bop"] = tabla["bop"].dt.strftime("%b-%Y")
    for col in tabla.columns[2:]:
        tabla[col] = tabla[col].map(lambda x: f"{x/1e6:.2f}M" if abs(x) > 1000 else f"{x:,.0f}")
    tabla.columns = ["Período", "Fecha", "CFDAS", "Desembolso",
                     "Saldo Deuda", "Servicio", "Intereses",
                     "Imp. Ganancias", "Imp. DCB", "FCFF", "FCFE"]
    st.dataframe(tabla, hide_index=True, height=500, use_container_width=True)

    # Exportar
    csv = df_fin.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Descargar CSV completo",
                       data=csv,
                       file_name="AMBA_I_MEF_resultado.csv",
                       mime="text/csv")

# ─────────────────────────────────────────────────────────────────────
# FOOTER IDOM
# ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="idom-footer">
    <span>IDOM Consulting · Engineering · Architecture &nbsp;|&nbsp; Proyecto AMBA I · Contrato T4199-P001-T014</span>
    <span>Motor Python v1.0 &nbsp;|&nbsp; USD constantes · <a href="https://www.idom.com" style="color:{CYAN}; text-decoration:none;">www.idom.com</a></span>
</div>
""", unsafe_allow_html=True)
