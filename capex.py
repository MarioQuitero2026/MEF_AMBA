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
    capex_lote_usd: float,
    tl: pd.DataFrame,
    curva_s: bool = False,
    capex_total_usd: float = 0.0,
) -> np.ndarray:
    """
    Distribuye el CAPEX de un lote en su ventana de construcción.
    Si curva_s=False: distribución uniforme dentro del período de construcción.
    Si curva_s=True: distribución por curva S (pct_curva_s del CAPEX global).
    Retorna array de longitud len(tl) con el CAPEX mensual del lote.
    """
    n = len(tl)
    capex_vec = np.zeros(n)

    if lote.duracion_construccion == 0 or capex_lote_usd == 0:
        return capex_vec

    inicio = lote.inicio_construccion
    fin = inicio + relativedelta(months=lote.duracion_construccion)

    mask = (tl["bop"] >= inicio) & (tl["bop"] < fin)
    periodos_activos = tl.loc[mask, "periodo"].values

    if len(periodos_activos) == 0:
        return capex_vec

    if curva_s:
        # Distribución proporcional al pct_curva_s dentro del período
        monto = lote.pct_curva_s * capex_total_usd
        capex_vec[periodos_activos] = monto / len(periodos_activos)
    else:
        # Distribución uniforme
        capex_vec[periodos_activos] = capex_lote_usd / len(periodos_activos)

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
    capex_global = p.controles.capex_global
    capex_total = p.capex.capex_total(rigi)
    iva_bienes = p.tributos.iva_bienes_cap(rigi)

    df = tl[["periodo", "bop", "eop", "anio", "factor_index_ipc_m",
             "factor_deflactor_ipc_m"]].copy()

    # ── CAPEX por lote ──────────────────────────────────────────────────
    for etapa, lotes in [("e1", LOTES_E1), ("e2", LOTES_E2)]:
        total_etapa = np.zeros(n)
        for i, lote in enumerate(lotes, 1):
            capex_lote = lote.pct_capex * capex_total
            vec = _distribuir_capex_lote(
                lote, capex_lote, tl,
                curva_s=capex_global,
                capex_total_usd=capex_total,
            )
            col = f"capex_{etapa}_l{i}"
            df[col] = vec
            total_etapa += vec

        # Supervisión y fees (% del CAPEX)
        supervision = total_etapa * p.capex.tasa_supervision
        df[f"supervision_{etapa}"] = supervision
        df[f"capex_total_{etapa}"] = total_etapa + supervision

    df["capex_total_bruto"] = df["capex_total_e1"] + df["capex_total_e2"]

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
    garantia_base = capex_total * p.capex.pct_garantia_habilitacion
    prima_mensual = garantia_base * p.capex.prima_anual_carta_credito / 12
    # Activa durante construcción E1 + E2
    mask_construccion = tl["en_construccion_e1"] | tl["en_construccion_e2"]
    df["garantia_hab_comercial"] = np.where(mask_construccion, prima_mensual, 0.0)

    # Garantía del anticipo (misma prima sobre el valor del anticipo)
    prima_anticipo = p.capex.valor_garantia_anticipo * p.capex.prima_anual_carta_credito / 12
    df["garantia_anticipo"] = np.where(mask_construccion, prima_anticipo, 0.0)

    # ── Depreciación lineal por lote ─────────────────────────────────────
    vida_util = (p.capex.capex_total_rigi  # dummy para seleccionar vida_util
                 if rigi else p.capex.capex_total_sin_rigi)

    dep_e1 = np.zeros(n)
    dep_e2 = np.zeros(n)

    for etapa_lotes, dep_vec, lotes in [
        (LOTES_E1, dep_e1, LOTES_E1),
        (LOTES_E2, dep_e2, LOTES_E2),
    ]:
        for i, lote in enumerate(lotes, 1):
            capex_lote = lote.pct_capex * capex_total
            vida_meses = lote.vida_util_rigi * 12 if rigi else lote.vida_util_sin_rigi * 12
            if vida_meses == 0:
                continue
            dep_mensual = capex_lote / vida_meses
            # Depreciación comienza al finalizar la construcción del lote
            inicio_dep = lote.inicio_construccion + relativedelta(months=lote.duracion_construccion)
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
