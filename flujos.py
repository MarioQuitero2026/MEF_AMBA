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
    Distribuye el RCOP (en VPN) entre los lotes activos según su
    pct_remuneracion y lo indexa por IPC si el selector está activo.

    rcop_vpn: valor presente total de la remuneración COP (USD).
    """
    if tl is None:
        tl = build_timeline(p)
    if df_capex is None:
        df_capex = calcular_capex(p, tl)

    n = len(tl)
    wacc_m = p.wacc.wacc_mensual(
        p.deuda.pct_deuda,
        p.deuda.kd_after_tax(p.controles.rigi),
        p.controles.rigi,
        p.controles.beta_fija,
    )

    df = tl[["periodo", "bop", "eop", "factor_index_ipc_m"]].copy()
    ingresos_e1 = np.zeros(n)
    ingresos_e2 = np.zeros(n)

    for etapa_idx, (lotes, ingresos_vec) in enumerate(
        [(LOTES_E1, ingresos_e1), (LOTES_E2, ingresos_e2)], 1
    ):
        for i, lote in enumerate(lotes, 1):
            if lote.pct_remuneracion == 0 or lote.duracion_remuneracion == 0:
                continue

            # Monto asignado al lote en VP
            vpn_lote = rcop_vpn * lote.pct_remuneracion

            # Períodos activos de remuneración
            inicio = lote.inicio_remuneracion
            fin = inicio + relativedelta(months=lote.duracion_remuneracion)
            mask = (tl["bop"] >= inicio) & (tl["bop"] < fin)
            periodos_act = tl.loc[mask, "periodo"].values

            if len(periodos_act) == 0:
                continue

            # Cuota mensual constante en términos de VP (annuity payment)
            # Convertimos VPN al valor nominal de la cuota uniforme
            # usando la fórmula de anualidad: PMT = VPN * wacc_m / (1-(1+wacc_m)^-n)
            dur = lote.duracion_remuneracion
            if wacc_m > 0:
                factor_anualidad = wacc_m / (1 - (1 + wacc_m) ** (-dur))
            else:
                factor_anualidad = 1 / dur

            # Valor nominal de la cuota en el período de inicio
            cuota_base = vpn_lote * factor_anualidad

            # Actualizar al momento de pago (el VPN fue calculado desde t=0)
            t_inicio = periodo_de_fecha(inicio, tl)
            if t_inicio < 0:
                t_inicio = periodos_act[0]

            # Factor de crecimiento desde t=0 hasta inicio de remuneración
            factor_crec = (1 + wacc_m) ** t_inicio

            for j, t in enumerate(periodos_act):
                # Cuota nominal en el período t
                cuota_nominal = cuota_base * factor_crec

                # Indexación IPC si el selector está activo
                if p.controles.inflacion_rcop:
                    idx_t = tl.loc[tl["periodo"] == t, "factor_index_ipc_m"].values[0]
                    idx_inicio = tl.loc[tl["periodo"] == t_inicio,
                                        "factor_index_ipc_m"].values[0]
                    cuota_nominal *= idx_t / idx_inicio

                ingresos_vec[t] += cuota_nominal

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

    # Garantías (ya calculadas en capex)
    df["opex_e1"] = opex_e1
    df["opex_e2"] = opex_e2
    df["opex_total"] = opex_e1 + opex_e2
    df["opex_con_garantias"] = (df["opex_total"] +
                                 df_capex["garantia_hab_comercial"] +
                                 df_capex["garantia_anticipo"])

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
) -> pd.DataFrame:
    """
    Calcula impuesto a las ganancias e impuesto débitos/créditos bancarios.
    """
    if tl is None:
        tl = build_timeline(p)

    n = len(tl)
    rigi = p.controles.rigi

    df = tl[["periodo", "bop", "eop"]].copy()

    tasa = p.tributos.tasa_ganancias_rigi if rigi else p.tributos.tasa_ganancias_sin_rigi
    pct_dcb = p.tributos.pct_deduccion_dcb(rigi)

    # Escudo fiscal
    escudo_fiscal = intereses.copy()
    ebt = ebit - intereses

    # Quebranto acumulado (sin RIGI: plazo 5 años; con RIGI: indefinido)
    plazo_queb = None if rigi else p.tributos.plazo_quebrantos_sin_rigi
    queb_acum = np.zeros(n)
    imp_ganancias = np.zeros(n)

    for t in range(n):
        base_gravable = ebt[t] - queb_acum[t - 1] if t > 0 else ebt[t]
        if base_gravable < 0:
            queb_acum[t] = abs(base_gravable)
            imp_ganancias[t] = 0.0
        else:
            queb_acum[t] = 0.0
            imp_ganancias[t] = base_gravable * tasa

    # Impuesto débitos y créditos bancarios
    flujo_bruto_gravado = flujos_dcb_entradas + flujos_dcb_salidas
    imp_dcb = (flujos_dcb_entradas * p.tributos.tasa_creditos +
               flujos_dcb_salidas * p.tributos.tasa_debitos)

    # Deducción de imp_dcb sobre ganancias
    deduccion_dcb = imp_dcb * pct_dcb
    imp_ganancias_neto = np.maximum(imp_ganancias - deduccion_dcb, 0)

    # IVA neto = IVA de ventas - IVA recuperado de CAPEX
    iva_ventas = np.zeros(n)   # Sin RIGI: ingresaría IVA en ventas
    if not rigi:
        # IVA a pagar (diferencia entre IVA cobrado en ingresos e IVA pagado en CAPEX)
        iva_neto = iva_ventas - iva_recuperado
    else:
        iva_neto = np.zeros(n)

    df["ebt"] = ebt
    df["impuesto_ganancias_bruto"] = imp_ganancias
    df["deduccion_dcb"] = deduccion_dcb
    df["impuesto_ganancias_neto"] = imp_ganancias_neto
    df["impuesto_dcb"] = imp_dcb
    df["iva_neto"] = iva_neto
    df["total_impuestos"] = imp_ganancias_neto + imp_dcb

    return df


# ─────────────────────────────────────────────────────────────────────
# CFDAS — Cash Flow Disponible Antes del Servicio de la Deuda
# ─────────────────────────────────────────────────────────────────────

def calcular_cfdas(
    rcop_vpn: float,
    p: Params = DEFAULT_PARAMS,
    tl: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Integra ingresos, OPEX, CAPEX e impuestos para obtener el CFDAS.
    Retorna DataFrame completo con todos los componentes del flujo libre.
    """
    if tl is None:
        tl = build_timeline(p)

    df_capex   = calcular_capex(p, tl)
    df_ing     = calcular_ingresos(rcop_vpn, p, tl, df_capex)
    df_opex    = calcular_opex(p, tl, df_capex)

    n = len(tl)

    # EBIT = Ingresos - OPEX - Depreciación
    ingresos   = df_ing["ingresos_rcop_total"].values
    opex_total = df_opex["opex_con_garantias"].values
    dep_total  = df_capex["depreciacion_total"].values
    ebit       = ingresos - opex_total - dep_total

    # Intereses placeholder (se actualizan en financiacion.py tras el sculpting)
    intereses_placeholder = np.zeros(n)

    # Flujos para DCB
    capex_bruto = df_capex["capex_con_iva"].values
    iva_rec     = df_capex["iva_capex"].values  # IVA recuperado progresivamente

    df_imp = calcular_impuestos(
        ebit=ebit,
        intereses=intereses_placeholder,
        flujos_dcb_entradas=ingresos,
        flujos_dcb_salidas=capex_bruto + opex_total,
        iva_capex_periodo=df_capex["iva_capex"].values,
        iva_recuperado=iva_rec,
        p=p,
        tl=tl,
    )

    df = tl[["periodo", "bop", "eop"]].copy()
    df["ingresos"]           = ingresos
    df["opex"]               = opex_total
    df["depreciacion"]       = dep_total
    df["ebit"]               = ebit
    df["capex"]              = df_capex["capex_total_bruto"].values
    df["capex_con_iva"]      = capex_bruto
    df["iva_capex"]          = df_capex["iva_capex"].values
    df["aporte_financiero"]  = df_capex["aporte_financiero"].values
    df["imp_dcb"]            = df_imp["impuesto_dcb"].values
    df["imp_ganancias"]      = df_imp["impuesto_ganancias_neto"].values

    # CFDAS = EBIT + D&A - CAPEX - Impuestos (antes de servicio deuda)
    # Equivalente a: Ingresos - OPEX cash - CAPEX - Impuestos DCB - Imp. Ganancias
    df["cfdas"] = (ingresos
                   - opex_total
                   - df_capex["capex_total_bruto"].values
                   - df["iva_capex"]                    # IVA pagado en construcción
                   + iva_rec                            # IVA recuperado en operación
                   + df["aporte_financiero"]            # subsidio del Estado
                   - df["imp_dcb"]
                   - df["imp_ganancias"])

    # FCFF = EBIT*(1-T) + D&A - CapEx - dWK
    tasa = (p.tributos.tasa_ganancias_rigi if p.controles.rigi
            else p.tributos.tasa_ganancias_sin_rigi)
    df["nopat"]  = ebit * (1 - tasa)
    df["fcff"]   = df["nopat"] + dep_total - df_capex["capex_total_bruto"].values

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
