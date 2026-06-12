"""
AMBA I — Motor Financiero Python
Módulos: ingresos.py, opex.py, impuestos.py, cfdas.py (integrados)
Equivalente a 05_Ingresos + 06_OPEX + 07_Impuestos + 08_CFDAS
"""
import numpy as np
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
from params import Params, DEFAULT_PARAMS, LOTES_E1, LOTES_E2
from timeline import build_timeline, periodo_de_fecha
from capex import calcular_capex


# ─────────────────────────────────────────────────────────────────────
# INGRESOS — RCOP por lote
# ─────────────────────────────────────────────────────────────────────

def calcular_ingresos(
    rcop_vpn: float,
    p: Params = DEFAULT_PARAMS,
    tl: pd.DataFrame = None,
    df_capex: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Distribuye el RCOP entre los lotes activos replicando la lógica exacta del Excel:
      cuota_mensual_lote[t] = (pct_lote * rcop_vpn / dur_meses) * factor_ipc[t]

    El factor_ipc[t] es el Factor Indexación IPC Mensual acumulado del timeline,
    que tiene un lag de 1 período (t=0 y t=1 = 1.0, t=2 = primer incremento).

    rcop_vpn: valor presente total de la remuneración COP (USD).
    """
    if tl is None:
        tl = build_timeline(p)
    if df_capex is None:
        df_capex = calcular_capex(p, tl)

    n = len(tl)
    # Factor IPC indexado por período (array directo del timeline)
    factor_ipc = tl["factor_index_ipc_m"].values

    df = tl[["periodo", "bop", "eop", "factor_index_ipc_m"]].copy()
    ingresos_e1 = np.zeros(n)
    ingresos_e2 = np.zeros(n)

    for lotes, ingresos_vec in [(LOTES_E1, ingresos_e1), (LOTES_E2, ingresos_e2)]:
        for lote in lotes:
            if lote.pct_remuneracion == 0 or lote.duracion_remuneracion == 0:
                continue

            # Cuota base (sin IPC): pct * RCOP_total / duración en meses
            cuota_base = rcop_vpn * lote.pct_remuneracion / lote.duracion_remuneracion

            # Períodos activos de remuneración
            inicio = lote.inicio_remuneracion
            fin = inicio + relativedelta(months=lote.duracion_remuneracion)
            mask = (tl["bop"] >= inicio) & (tl["bop"] < fin)
            periodos_act = tl.loc[mask, "periodo"].values

            if len(periodos_act) == 0:
                continue

            for t in periodos_act:
                if p.controles.inflacion_rcop:
                    # Cuota indexada: cuota_base * factor_ipc[t]
                    # Replicación exacta de la fórmula del Excel
                    ingresos_vec[t] += cuota_base * factor_ipc[t]
                else:
                    ingresos_vec[t] += cuota_base

    df["ingresos_rcop_e1"] = ingresos_e1
    df["ingresos_rcop_e2"] = ingresos_e2
    df["ingresos_rcop_total"] = ingresos_e1 + ingresos_e2

    # Tarifa TI (cuando esté definida)
    tarifa_ti_e1 = np.zeros(n)
    tarifa_ti_e2 = np.zeros(n)
    mask_oym_e1 = tl["en_oym_e1"].values
    mask_oym_e2 = tl["en_oym_e2"].values

    if p.opex.tarifa_ti_e1_mensual > 0:
        tarifa_ti_e1[mask_oym_e1] = p.opex.tarifa_ti_e1_mensual
        if p.controles.inflacion_ti:
            idx_base = tl.loc[tl["en_oym_e1"].values, "factor_index_ipc_m"].iloc[0]
            for t in tl.loc[mask_oym_e1, "periodo"].values:
                idx_t = tl.loc[tl["periodo"] == t, "factor_index_ipc_m"].values[0]
                tarifa_ti_e1[t] *= idx_t / idx_base

    if p.opex.tarifa_ti_e2_mensual > 0:
        tarifa_ti_e2[mask_oym_e2] = p.opex.tarifa_ti_e2_mensual
        if p.controles.inflacion_ti:
            idx_base = tl.loc[tl["en_oym_e2"].values, "factor_index_ipc_m"].iloc[0]
            for t in tl.loc[mask_oym_e2, "periodo"].values:
                idx_t = tl.loc[tl["periodo"] == t, "factor_index_ipc_m"].values[0]
                tarifa_ti_e2[t] *= idx_t / idx_base

    df["tarifa_ti_e1"] = tarifa_ti_e1
    df["tarifa_ti_e2"] = tarifa_ti_e2
    df["ingresos_totales"] = df["ingresos_rcop_total"] + tarifa_ti_e1 + tarifa_ti_e2

    return df


# ─────────────────────────────────────────────────────────────────────
# OPEX
# ─────────────────────────────────────────────────────────────────────

def calcular_opex(
    p: Params = DEFAULT_PARAMS,
    tl: pd.DataFrame = None,
    df_capex: pd.DataFrame = None,
) -> pd.DataFrame:
    """Calcula OPEX mensual por etapa como % del CAPEX acumulado activado."""
    if tl is None:
        tl = build_timeline(p)
    if df_capex is None:
        df_capex = calcular_capex(p, tl)

    n = len(tl)
    rigi = p.controles.rigi
    capex_total = p.capex.capex_total(rigi)

    df = tl[["periodo", "bop", "eop"]].copy()

    # CAPEX acumulado activado por etapa (base para cálculo del OPEX)
    capex_activ_e1 = df_capex["capex_total_e1"].cumsum().values
    capex_activ_e2 = df_capex["capex_total_e2"].cumsum().values

    pct_total = p.opex.total_pct_capex() * p.opex.pct_capex_operado

    opex_e1 = np.zeros(n)
    opex_e2 = np.zeros(n)
    mask_oym_e1 = tl["en_oym_e1"].values
    mask_oym_e2 = tl["en_oym_e2"].values

    # OPEX solo en período O&M, calculado mensualmente
    for t in range(n):
        if mask_oym_e1[t]:
            opex_e1[t] = capex_activ_e1[t] * pct_total / 12
        if mask_oym_e2[t]:
            opex_e2[t] = capex_activ_e2[t] * pct_total / 12

    # Indexar por IPC si corresponde
    idx = tl["factor_index_ipc_m"].values
    idx_inicio = idx[np.where(mask_oym_e1)[0][0]] if mask_oym_e1.any() else 1.0
    opex_e1 = opex_e1 * (idx / idx_inicio)
    if mask_oym_e2.any():
        idx_inicio_e2 = idx[np.where(mask_oym_e2)[0][0]]
        opex_e2 = opex_e2 * (idx / idx_inicio_e2)

    df["opex_e1"] = opex_e1
    df["opex_e2"] = opex_e2
    df["opex_total"] = opex_e1 + opex_e2
    # Las garantías de habilitación y anticipo ya están incluidas en el CAPEX
    # por lote (dentro de capex_total_e1/e2). No se duplican aquí.
    df["opex_con_garantias"] = df["opex_total"]

    return df


# ─────────────────────────────────────────────────────────────────────
# IMPUESTOS
# ─────────────────────────────────────────────────────────────────────

def calcular_impuestos(
    ebit: np.ndarray,
    intereses: np.ndarray,
    flujos_dcb_entradas: np.ndarray,
    flujos_dcb_salidas: np.ndarray,
    iva_capex_periodo: np.ndarray,
    iva_recuperado: np.ndarray,
    p: Params = DEFAULT_PARAMS,
    tl: pd.DataFrame = None,
    capex_fiscal: np.ndarray = None,
) -> pd.DataFrame:
    """
    Calcula impuesto a las ganancias e impuesto débitos/créditos bancarios.

    LÓGICA EXACTA DEL EXCEL (07_Impuestos):
    - Año fiscal = bloques de 12 períodos desde t=0 (junio a mayo)
    - Base gravable anual = sum(EBIT - Intereses) del bloque
    - Impuesto = base × tasa, pagado al final del bloque (período t_fin-1)
    - Crédito DCB: el DCB acumulado del bloque se deduce del impuesto
    - Quebrantos: solo relevantes en años tardíos con caída de ingresos
    """
    if tl is None:
        tl = build_timeline(p)

    n = len(tl)
    rigi = p.controles.rigi
    tasa = p.tributos.tasa_ganancias_rigi if rigi else p.tributos.tasa_ganancias_sin_rigi
    pct_dcb = p.tributos.pct_deduccion_dcb(rigi)

    df = tl[["periodo", "bop", "eop"]].copy()

    # ── Impuesto débitos y créditos bancarios (mensual) ──────────────────
    imp_dcb = (flujos_dcb_entradas * p.tributos.tasa_creditos +
               np.abs(flujos_dcb_salidas) * p.tributos.tasa_debitos)

    # ── Impuesto a las ganancias (anual por bloque fiscal junio-mayo) ─────
    imp_ganancias = np.zeros(n)
    queb_acum = 0.0
    n_bloques = (n + 11) // 12

    for bloque in range(n_bloques):
        t_ini = bloque * 12
        t_fin = min(t_ini + 12, n)
        t_pago = t_fin - 1

        base_bruta = sum(ebit[t] - intereses[t] for t in range(t_ini, t_fin))

        if base_bruta < 0:
            queb_acum += abs(base_bruta)
            base_neta = 0.0
        else:
            reduccion = min(base_bruta, queb_acum)
            base_neta = base_bruta - reduccion
            queb_acum = max(0.0, queb_acum - base_bruta)

        if base_neta > 0:
            imp_bruto = base_neta * tasa
            dcb_bloque = sum(imp_dcb[t] for t in range(t_ini, t_fin))
            deduccion = dcb_bloque * pct_dcb
            imp_ganancias[t_pago] = max(imp_bruto - deduccion, 0)

    df["ebt"] = ebit - intereses
    df["impuesto_ganancias_neto"] = imp_ganancias
    df["impuesto_dcb"] = imp_dcb
    df["iva_neto"] = np.zeros(n)
    df["total_impuestos"] = imp_ganancias + imp_dcb
    df["deduccion_dcb"] = imp_dcb * pct_dcb

    return df


# ─────────────────────────────────────────────────────────────────────
# CFDAS — Cash Flow Disponible Antes del Servicio de la Deuda
# ─────────────────────────────────────────────────────────────────────

def calcular_cfdas(
    rcop_vpn: float,
    p: Params = DEFAULT_PARAMS,
    tl: pd.DataFrame = None,
    intereses_reales: np.ndarray = None,
    path_excel: str = None,
    datos_impuesto: dict = None,
) -> pd.DataFrame:
    """
    Integra ingresos, OPEX, CAPEX e impuestos para obtener el CFDAS y FCFF.

    - intereses_reales: intereses de la tabla de amortización real (para escudo fiscal)
    - path_excel: ruta al MEF V3 xlsm. Si se provee, usa impuesto exacto de 07_Impuestos
    - datos_impuesto: dict pre-cargado con cargar_impuestos_excel() (reutilizable)
    """
    if tl is None:
        tl = build_timeline(p)

    df_capex   = calcular_capex(p, tl)
    df_ing     = calcular_ingresos(rcop_vpn, p, tl, df_capex)
    df_opex    = calcular_opex(p, tl, df_capex)

    n = len(tl)
    ingresos   = df_ing["ingresos_rcop_total"].values
    opex_total = df_opex["opex_con_garantias"].values
    dep_total  = df_capex["depreciacion_total"].values
    ebit       = ingresos - opex_total - dep_total
    iva_rec    = df_capex["iva_capex"].values

    # ── Impuesto a las ganancias ────────────────────────────────────
    if path_excel is not None or datos_impuesto is not None:
        # Exactitud perfecta: leer valores directamente del Excel
        from impuesto_fiscal import (cargar_impuestos_excel,
                                     calcular_impuesto_ganancias_exacto,
                                     calcular_impuesto_dcb_exacto)
        if datos_impuesto is None:
            datos_impuesto = cargar_impuestos_excel(
                path_excel, n_periodos=n, rigi=p.controles.rigi)
        imp_ganancias_arr = calcular_impuesto_ganancias_exacto(
            ebit, datos_excel=datos_impuesto,
            rigi=p.controles.rigi, n_periodos=n)
        imp_dcb_arr = calcular_impuesto_dcb_exacto(datos_impuesto, n_periodos=n)
    else:
        # Fallback: cálculo interno con bloques fiscales anuales
        intereses_para_impuesto = (intereses_reales
                                   if intereses_reales is not None
                                   else np.zeros(n))
        df_imp = calcular_impuestos(
            ebit=ebit,
            intereses=intereses_para_impuesto,
            flujos_dcb_entradas=ingresos,
            flujos_dcb_salidas=df_capex["capex_con_iva"].values + opex_total,
            iva_capex_periodo=df_capex["iva_capex"].values,
            iva_recuperado=iva_rec,
            p=p, tl=tl,
            capex_fiscal=df_capex["capex_total_bruto"].values,
        )
        imp_ganancias_arr = df_imp["impuesto_ganancias_neto"].values
        imp_dcb_arr       = df_imp["impuesto_dcb"].values

    df = tl[["periodo", "bop", "eop"]].copy()
    df["ingresos"]           = ingresos
    df["opex"]               = opex_total
    df["depreciacion"]       = dep_total
    df["ebit"]               = ebit
    capex_fcff = df_capex["capex_total_bruto"].values
    df["capex"]              = capex_fcff
    df["capex_con_sup"]      = capex_fcff + df_capex["supervision"].values
    df["capex_con_iva"]      = df_capex["capex_con_iva"].values
    df["iva_capex"]          = df_capex["iva_capex"].values
    df["aporte_financiero"]  = df_capex["aporte_financiero"].values
    df["imp_dcb"]            = imp_dcb_arr
    df["imp_ganancias"]      = imp_ganancias_arr

    # CFDAS = EBIT + D&A - CAPEX - Impuestos (antes de servicio deuda)
    # Equivalente a: Ingresos - OPEX cash - CAPEX - Impuestos DCB - Imp. Ganancias
    df["cfdas"] = (ingresos
                   - opex_total
                   - capex_fcff
                   - df["iva_capex"]
                   + iva_rec
                   + df["aporte_financiero"]
                   - df["imp_dcb"]
                   - df["imp_ganancias"])

    # FCFF = NOPAT + D&A - CAPEX (convención estándar, T aplicada mensualmente)
    tasa = (p.tributos.tasa_ganancias_rigi if p.controles.rigi
            else p.tributos.tasa_ganancias_sin_rigi)
    df["nopat"]  = ebit * (1 - tasa)
    df["fcff"]   = df["nopat"] + dep_total - capex_fcff

    return df


if __name__ == "__main__":
    from params import Params
    p = Params()
    tl = build_timeline(p)

    # Usar RCOP del modelo Excel como punto de partida
    rcop_vpn = 1_336_525_554.41
    df = calcular_cfdas(rcop_vpn, p, tl)

    print(df[["periodo", "bop", "ingresos", "opex", "capex",
              "ebit", "cfdas", "fcff"]][
        (df["ingresos"] > 0) | (df["capex"] > 0)
    ].head(40).to_string())

    print(f"\nVPN FCFF @ WACC: necesita módulo financiacion.py")
    print(f"CFDAS acumulado: USD {df['cfdas'].sum():,.0f}")
    print(f"FCFF acumulado:  USD {df['fcff'].sum():,.0f}")
