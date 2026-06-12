"""
AMBA I — Motor Financiero Python
Módulo: capex.py
CAPEX mensual por lote, garantías, IVA sobre CAPEX, depreciación y
aporte financiero del Estado. Equivalente a 04_CAPEX.
"""
import numpy as np
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
from params import Params, DEFAULT_PARAMS, LoteConfig, LOTES_E1, LOTES_E2
from timeline import build_timeline, periodo_de_fecha


def _distribuir_capex_lote(
    lote: LoteConfig,
    capex_neto_usd: float,
    tl: pd.DataFrame,
    factor_ipc: np.ndarray,
) -> np.ndarray:
    """
    Distribuye el CAPEX de un lote replicando la lógica exacta del Excel:
      capex_nominal[t] = (pct_curva_s × CAPEX_NETO / duración) × factor_ipc[t]

    capex_neto_usd: CAPEX total sin aportes del Estado (748.65M con RIGI).
    factor_ipc: array del Factor Indexación IPC Mensual del timeline (con lag).
    """
    n = len(tl)
    capex_vec = np.zeros(n)

    if lote.duracion_construccion == 0 or lote.pct_curva_s == 0:
        return capex_vec

    inicio = lote.inicio_construccion
    fin = inicio + relativedelta(months=lote.duracion_construccion)
    mask = (tl["bop"] >= inicio) & (tl["bop"] < fin)
    periodos_activos = tl.loc[mask, "periodo"].values

    if len(periodos_activos) == 0:
        return capex_vec

    # Cuota base (sin IPC): pct × CAPEX_NETO / duración meses
    cuota_base = lote.pct_curva_s * capex_neto_usd / lote.duracion_construccion

    for t in periodos_activos:
        capex_vec[t] = cuota_base * factor_ipc[t]

    return capex_vec


def calcular_capex(
    p: Params = DEFAULT_PARAMS,
    tl: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Calcula CAPEX mensual por etapa y lote, garantías, IVA, depreciación
    y aporte financiero.
    Retorna DataFrame con columnas indexadas por período.
    """
    if tl is None:
        tl = build_timeline(p)

    n = len(tl)
    rigi = p.controles.rigi
    # CAPEX neto = CAPEX total - aporte financiero - aporte especie
    # Esta es la base que usa el Excel para distribuir por lote con Curva S
    capex_neto = p.capex.capex_total(rigi) - p.capex.aporte_financiero - p.capex.aporte_especie
    factor_ipc = tl["factor_index_ipc_m"].values
    iva_bienes = p.tributos.iva_bienes_cap(rigi)

    df = tl[["periodo", "bop", "eop", "anio", "factor_index_ipc_m",
             "factor_deflactor_ipc_m"]].copy()

    # ── CAPEX por lote (Curva S indexada por IPC) + Garantías ───────────
    # Prima garantía habilitación = CAPEX_NETO × 10% × 0.8% / 12
    # Prima garantía anticipo = aporte_financiero × 0.8% / 12
    # Ambas se aplican durante la ventana de construcción de cada lote × factor_ipc[t]
    prima_base_hab  = capex_neto * p.capex.pct_garantia_habilitacion * p.capex.prima_anual_carta_credito / 12
    prima_base_anti = p.capex.valor_garantia_anticipo * p.capex.prima_anual_carta_credito / 12

    for etapa, lotes in [("e1", LOTES_E1), ("e2", LOTES_E2)]:
        total_etapa = np.zeros(n)
        for i, lote in enumerate(lotes, 1):
            vec_construccion = _distribuir_capex_lote(lote, capex_neto, tl, factor_ipc)

            # Garantías: mismo período de construcción, misma indexación IPC
            inicio = lote.inicio_construccion
            fin = inicio + relativedelta(months=lote.duracion_construccion)
            mask = (tl["bop"] >= inicio) & (tl["bop"] < fin)
            periodos_activos = tl.loc[mask, "periodo"].values

            vec_garantias = np.zeros(n)
            for t in periodos_activos:
                vec_garantias[t] = (prima_base_hab + prima_base_anti) * factor_ipc[t]

            vec = vec_construccion + vec_garantias
            col = f"capex_{etapa}_l{i}"
            df[col] = vec
            total_etapa += vec
        df[f"capex_total_{etapa}"] = total_etapa

    df["capex_total_bruto"] = df["capex_total_e1"] + df["capex_total_e2"]

    # Supervisión (tratada por separado, fuera del FCFF principal)
    df["supervision"] = df["capex_total_bruto"] * p.capex.tasa_supervision

    # ── IVA sobre CAPEX ──────────────────────────────────────────────────
    df["iva_capex"] = df["capex_total_bruto"] * p.capex.pct_iva_capex * iva_bienes
    df["capex_con_iva"] = df["capex_total_bruto"] + df["iva_capex"]

    # ── Aporte financiero del Estado ─────────────────────────────────────
    aporte_vec = np.zeros(n)
    for fecha_pago, pct in p.capex.escalones_aporte:
        t = periodo_de_fecha(fecha_pago, tl)
        if t >= 0:
            aporte_vec[t] += pct * p.capex.aporte_financiero
    df["aporte_financiero"] = aporte_vec

    # ── CAPEX neto (descontando aporte) ──────────────────────────────────
    df["capex_neto"] = df["capex_total_bruto"] - df["aporte_financiero"]

    # ── Garantías ────────────────────────────────────────────────────────
    # Garantía de habilitación comercial (prima anual sobre % del CAPEX)
    garantia_base = capex_neto * p.capex.pct_garantia_habilitacion
    prima_mensual = garantia_base * p.capex.prima_anual_carta_credito / 12
    # Activa durante construcción E1 + E2
    mask_construccion = tl["en_construccion_e1"] | tl["en_construccion_e2"]
    df["garantia_hab_comercial"] = np.where(mask_construccion, prima_mensual, 0.0)

    # Garantía del anticipo (misma prima sobre el valor del anticipo)
    prima_anticipo = p.capex.valor_garantia_anticipo * p.capex.prima_anual_carta_credito / 12
    df["garantia_anticipo"] = np.where(mask_construccion, prima_anticipo, 0.0)

    # ── Depreciación lineal por lote ─────────────────────────────────────
    # El Excel deprecia el CAPEX NOMINAL TOTAL de cada lote
    # (suma de cuotas con IPC durante la construcción / vida útil en meses)
    dep_e1 = np.zeros(n)
    dep_e2 = np.zeros(n)

    for dep_vec, lotes in [(dep_e1, LOTES_E1), (dep_e2, LOTES_E2)]:
        for lote in lotes:
            if lote.duracion_construccion == 0 or lote.pct_curva_s == 0:
                continue

            # CAPEX nominal total del lote = suma de cuotas durante construcción
            cuota_base = lote.pct_curva_s * capex_neto / lote.duracion_construccion
            inicio_c = lote.inicio_construccion
            fin_c = inicio_c + relativedelta(months=lote.duracion_construccion)
            mask_c = (tl["bop"] >= inicio_c) & (tl["bop"] < fin_c)
            periodos_c = tl.loc[mask_c, "periodo"].values
            capex_nominal_total = sum(cuota_base * factor_ipc[t] for t in periodos_c)

            vida_meses = lote.vida_util_rigi * 12 if rigi else lote.vida_util_sin_rigi * 12
            if vida_meses == 0:
                continue

            dep_mensual = capex_nominal_total / vida_meses

            # Depreciación comienza al finalizar la construcción
            inicio_dep = fin_c
            fin_dep = inicio_dep + relativedelta(months=vida_meses)
            mask_dep = (tl["bop"] >= inicio_dep) & (tl["bop"] < fin_dep)
            dep_vec[tl.loc[mask_dep, "periodo"].values] += dep_mensual

    df["depreciacion_e1"] = dep_e1
    df["depreciacion_e2"] = dep_e2
    df["depreciacion_total"] = dep_e1 + dep_e2

    return df


if __name__ == "__main__":
    from params import Params
    p = Params()
    tl = build_timeline(p)
    df = calcular_capex(p, tl)

    cols_resumen = ["periodo", "bop", "capex_total_e1", "capex_total_e2",
                    "capex_total_bruto", "iva_capex", "aporte_financiero",
                    "depreciacion_total"]
    print(df[cols_resumen][df["capex_total_bruto"] > 0].to_string())
    print(f"\nCAPEX Total E1: USD {df['capex_total_e1'].sum():,.0f}")
    print(f"CAPEX Total E2: USD {df['capex_total_e2'].sum():,.0f}")
    print(f"CAPEX Total:    USD {df['capex_total_bruto'].sum():,.0f}")
    print(f"IVA total:      USD {df['iva_capex'].sum():,.0f}")
    print(f"Depreciación:   USD {df['depreciacion_total'].sum():,.0f}")
