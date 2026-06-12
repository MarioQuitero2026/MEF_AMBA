"""
AMBA I — Motor Financiero Python
Módulo: financiacion.py
Tabla de amortización con DSCR sculpting para T1 y T2.
Optimizador de RCOP con VPN FCFE = 0 y Deuda Final = 0.
Equivalente a 09_Financiación + 12_RCOP + macros BarridoRCOP/OptimizarPunto.
"""
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from params import Params, DEFAULT_PARAMS
from timeline import build_timeline
from flujos import calcular_cfdas


# ─────────────────────────────────────────────────────────────────────
# TABLA DE AMORTIZACIÓN CON DSCR SCULPTING
# ─────────────────────────────────────────────────────────────────────

def calcular_financiacion(
    rcop_vpn: float,
    pct_deuda: float,
    p: Params = DEFAULT_PARAMS,
    tl: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Calcula la tabla de financiación completa con sculpting para T1 y T2.

    La deuda se calcula de modo que DSCR = CFDAS / Servicio Deuda = dscr_objetivo.
    La amortización sculpted garantiza que el saldo final sea 0 al fin de cada etapa.

    Retorna DataFrame con columnas de deuda, servicio, FCFE y métricas.
    """
    if tl is None:
        tl = build_timeline(p)

    df_cfdas = calcular_cfdas(rcop_vpn, p, tl)
    n = len(tl)

    kd_m = p.deuda.kd_mensual
    dscr_obj = p.deuda.dscr_objetivo
    rigi = p.controles.rigi
    capitalizar = p.controles.capitalizar_intereses

    # Límites de período para cada tramo
    # T1: construcción E1 + O&M E1
    # T2: construcción E2 + O&M E2 (comienza cuando termina construcción E1)
    mask_const_e1 = tl["en_construccion_e1"].values
    mask_oym_e1   = tl["en_oym_e1"].values
    mask_const_e2 = tl["en_construccion_e2"].values
    mask_oym_e2   = tl["en_oym_e2"].values

    # Períodos de desembolso y repago por tramo
    t_ini_const_e1 = int(tl.loc[mask_const_e1, "periodo"].iloc[0])
    t_fin_const_e1 = int(tl.loc[mask_const_e1, "periodo"].iloc[-1])
    t_ini_oym_e1   = int(tl.loc[mask_oym_e1,   "periodo"].iloc[0])
    t_fin_oym_e1   = int(tl.loc[mask_oym_e1,   "periodo"].iloc[-1])

    t_ini_const_e2 = int(tl.loc[mask_const_e2, "periodo"].iloc[0])
    t_fin_const_e2 = int(tl.loc[mask_const_e2, "periodo"].iloc[-1])
    t_ini_oym_e2   = int(tl.loc[mask_oym_e2,   "periodo"].iloc[0])
    t_fin_oym_e2   = int(tl.loc[mask_oym_e2,   "periodo"].iloc[-1])

    cfdas = df_cfdas["cfdas"].values.copy()
    capex_vec = df_cfdas["capex"].values.copy()

    # Arrays de resultado
    desembolso_t1    = np.zeros(n)
    saldo_t1         = np.zeros(n)
    intereses_t1     = np.zeros(n)
    amort_t1         = np.zeros(n)
    servicio_t1      = np.zeros(n)
    commitment_t1    = np.zeros(n)
    originacion_t1   = np.zeros(n)
    dcb_deuda_t1     = np.zeros(n)

    desembolso_t2    = np.zeros(n)
    saldo_t2         = np.zeros(n)
    intereses_t2     = np.zeros(n)
    amort_t2         = np.zeros(n)
    servicio_t2      = np.zeros(n)

    # ── TRAMO 1 ─────────────────────────────────────────────────────
    # Desembolso proporcional al CAPEX E1 durante construcción
    capex_e1_total = df_cfdas["capex"].values[mask_const_e1].sum()

    for t in range(t_ini_const_e1, t_fin_const_e1 + 1):
        if capex_e1_total > 0:
            desembolso_t1[t] = capex_vec[t] * pct_deuda
        saldo_prev = saldo_t1[t - 1] if t > 0 else 0.0
        interes = (saldo_prev + desembolso_t1[t]) * kd_m
        intereses_t1[t] = interes
        if capitalizar:
            saldo_t1[t] = saldo_prev + desembolso_t1[t] + interes
        else:
            saldo_t1[t] = saldo_prev + desembolso_t1[t]

    # Comisión de originación T1 (en el primer período)
    originacion_t1[t_ini_const_e1] = saldo_t1[t_ini_const_e1] * p.deuda.comision_originacion_t1
    # Commitment fee T1 (sobre monto comprometido no desembolsado)
    deuda_max_t1 = saldo_t1[t_fin_const_e1]
    for t in range(t_ini_const_e1, t_fin_const_e1 + 1):
        saldo_comprometido = deuda_max_t1 - saldo_t1[t]
        commitment_t1[t] = max(saldo_comprometido, 0) * p.deuda.commitment_fee_t1 / 12

    # Impuesto DCB sobre desembolsos de deuda
    for t in range(t_ini_const_e1, t_fin_const_e1 + 1):
        dcb_deuda_t1[t] = desembolso_t1[t] * (p.tributos.tasa_creditos + p.tributos.tasa_debitos)

    # DSCR sculpting durante O&M E1
    # Amortización sculpted: servicio = CFDAS / dscr_obj
    for t in range(t_ini_oym_e1, t_fin_oym_e1 + 1):
        saldo_prev = saldo_t1[t - 1] if t > 0 else 0.0
        interes = saldo_prev * kd_m
        intereses_t1[t] = interes
        # Servicio máximo que el CFDAS puede sostener dado el DSCR objetivo
        servicio_max = cfdas[t] / dscr_obj if dscr_obj > 0 else 0
        amort = max(servicio_max - interes, 0)
        # No amortizar más que el saldo
        amort = min(amort, saldo_prev)
        amort_t1[t] = amort
        servicio_t1[t] = amort + interes
        saldo_t1[t] = saldo_prev - amort

    # ── TRAMO 2 ─────────────────────────────────────────────────────
    capex_e2_total = df_cfdas["capex"].values[mask_const_e2].sum()
    for t in range(t_ini_const_e2, t_fin_const_e2 + 1):
        if capex_e2_total > 0:
            desembolso_t2[t] = capex_vec[t] * pct_deuda
        saldo_prev = saldo_t2[t - 1] if t > 0 else 0.0
        interes = (saldo_prev + desembolso_t2[t]) * kd_m
        intereses_t2[t] = interes
        if capitalizar:
            saldo_t2[t] = saldo_prev + desembolso_t2[t] + interes
        else:
            saldo_t2[t] = saldo_prev + desembolso_t2[t]

    # DSCR sculpting T2
    for t in range(t_ini_oym_e2, t_fin_oym_e2 + 1):
        saldo_prev = saldo_t2[t - 1] if t > 0 else 0.0
        interes = saldo_prev * kd_m
        intereses_t2[t] = interes
        servicio_max = cfdas[t] / dscr_obj if dscr_obj > 0 else 0
        amort = max(servicio_max - interes, 0)
        amort = min(amort, saldo_prev)
        amort_t2[t] = amort
        servicio_t2[t] = amort + interes
        saldo_t2[t] = saldo_prev - amort

    # ── FLUJO DEL INVERSIONISTA (FCFE) ──────────────────────────────
    intereses_total  = intereses_t1 + intereses_t2
    amort_total      = amort_t1 + amort_t2
    desembolso_total = desembolso_t1 + desembolso_t2
    servicio_total   = servicio_t1 + servicio_t2
    saldo_final_t1   = saldo_t1[-1]
    saldo_final_t2   = saldo_t2[-1]

    # Recalcular CFDAS/FCFF con los intereses REALES para el escudo fiscal
    df_cfdas_real = calcular_cfdas(rcop_vpn, p, tl, intereses_reales=intereses_total)

    fcff = df_cfdas_real["fcff"].values
    imp_ganancias_real = df_cfdas_real["imp_ganancias"].values
    imp_dcb_real       = df_cfdas_real["imp_dcb"].values
    efecto_iva         = df_cfdas_real["iva_capex"].values
    fcfe = (fcff
            + desembolso_total
            - servicio_total
            - imp_dcb_real
            - efecto_iva)

    # ── MÉTRICAS ────────────────────────────────────────────────────
    ke_m = p.wacc.ke_mensual(pct_deuda, rigi, p.controles.beta_fija)
    wacc_m = p.wacc.wacc_mensual(pct_deuda, p.deuda.kd_after_tax(rigi), rigi, p.controles.beta_fija)

    periodos = np.arange(n)
    descuento_ke   = (1 + ke_m) ** (-periodos)
    descuento_wacc = (1 + wacc_m) ** (-periodos)

    vpn_fcfe = np.sum(fcfe * descuento_ke)
    vpn_fcff = np.sum(fcff * descuento_wacc)

    # ── DATAFRAME RESULTADO ─────────────────────────────────────────
    df = tl[["periodo", "bop", "eop"]].copy()
    df["cfdas"]             = cfdas
    df["fcff"]              = fcff
    df["desembolso_t1"]     = desembolso_t1
    df["saldo_t1"]          = saldo_t1
    df["intereses_t1"]      = intereses_t1
    df["amort_t1"]          = amort_t1
    df["servicio_t1"]       = servicio_t1
    df["desembolso_t2"]     = desembolso_t2
    df["saldo_t2"]          = saldo_t2
    df["intereses_t2"]      = intereses_t2
    df["amort_t2"]          = amort_t2
    df["servicio_t2"]       = servicio_t2
    df["saldo_total"]       = saldo_t1 + saldo_t2
    df["servicio_total"]    = servicio_total
    df["desembolso_total"]  = desembolso_total
    df["intereses_total"]   = intereses_total
    df["imp_ganancias"]     = imp_ganancias_real
    df["imp_dcb"]           = imp_dcb_real
    df["fcfe"]              = fcfe
    df["dscr_t1"]           = np.where(servicio_t1 > 0, cfdas / servicio_t1, np.nan)
    df["dscr_t2"]           = np.where(servicio_t2 > 0, cfdas / servicio_t2, np.nan)

    # Metadatos agregados
    df.attrs["vpn_fcfe"]        = vpn_fcfe
    df.attrs["vpn_fcff"]        = vpn_fcff
    df.attrs["saldo_final_t1"]  = saldo_final_t1
    df.attrs["saldo_final_t2"]  = saldo_final_t2
    df.attrs["ke_m"]            = ke_m
    df.attrs["wacc_m"]          = wacc_m
    df.attrs["pct_deuda"]       = pct_deuda
    df.attrs["rcop_vpn"]        = rcop_vpn

    return df


# ─────────────────────────────────────────────────────────────────────
# OPTIMIZADOR RCOP
# ─────────────────────────────────────────────────────────────────────

def optimizar_rcop(
    pct_deuda: float,
    p: Params = DEFAULT_PARAMS,
    tl: pd.DataFrame = None,
    rcop_min: float = 100_000_000,
    rcop_max: float = 3_000_000_000,
    tol: float = 1.0,
    verbose: bool = False,
) -> dict:
    """
    Encuentra el RCOP (en VPN) que hace VPN FCFE = 0 dado un % de deuda fijo.
    Equivalente a OptimizarPunto_v5_2 del VBA.

    Usa brentq de scipy (más robusto que Newton para funciones no suaves).
    """
    if tl is None:
        tl = build_timeline(p)

    def objetivo(rcop_vpn: float) -> float:
        df = calcular_financiacion(rcop_vpn, pct_deuda, p, tl)
        return df.attrs["vpn_fcfe"]

    # Verificar que la función cambia de signo en el intervalo
    f_min = objetivo(rcop_min)
    f_max = objetivo(rcop_max)

    if verbose:
        print(f"  RCOP_min={rcop_min:,.0f} → VPN FCFE={f_min:,.0f}")
        print(f"  RCOP_max={rcop_max:,.0f} → VPN FCFE={f_max:,.0f}")

    if f_min * f_max > 0:
        raise ValueError(
            f"No hay cambio de signo en [{rcop_min:,.0f}, {rcop_max:,.0f}]. "
            f"f_min={f_min:,.0f}, f_max={f_max:,.0f}"
        )

    rcop_opt = brentq(objetivo, rcop_min, rcop_max, xtol=tol, full_output=False)
    df_opt = calcular_financiacion(rcop_opt, pct_deuda, p, tl)

    return {
        "rcop_vpn":       rcop_opt,
        "vpn_fcfe":       df_opt.attrs["vpn_fcfe"],
        "vpn_fcff":       df_opt.attrs["vpn_fcff"],
        "saldo_final_t1": df_opt.attrs["saldo_final_t1"],
        "saldo_final_t2": df_opt.attrs["saldo_final_t2"],
        "pct_deuda":      pct_deuda,
        "ke_m":           df_opt.attrs["ke_m"],
        "wacc_m":         df_opt.attrs["wacc_m"],
        "df":             df_opt,
    }


def barrido_rcop(
    p: Params = DEFAULT_PARAMS,
    tl: pd.DataFrame = None,
    pct_deuda_range: np.ndarray = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Barrido completo de % deuda → RCOP óptimo para cada punto.
    Equivalente a BarridoRCOP_v5_2 del VBA.
    Retorna DataFrame con resultados del barrido.
    """
    if tl is None:
        tl = build_timeline(p)
    if pct_deuda_range is None:
        pct_deuda_range = np.arange(0.0, 0.91, 0.05)

    resultados = []
    for pct_d in pct_deuda_range:
        try:
            res = optimizar_rcop(pct_d, p, tl, verbose=False)
            ke_anual  = (1 + res["ke_m"]) ** 12 - 1
            wacc_anual = (1 + res["wacc_m"]) ** 12 - 1
            elegible = (abs(res["vpn_fcfe"]) < 1.0 and
                        abs(res["saldo_final_t1"]) < 1_000 and
                        abs(res["saldo_final_t2"]) < 1_000)
            resultados.append({
                "pct_deuda":       pct_d,
                "pct_equity":      1 - pct_d,
                "rcop_vpn":        res["rcop_vpn"],
                "vpn_fcfe":        res["vpn_fcfe"],
                "vpn_fcff":        res["vpn_fcff"],
                "saldo_final_t1":  res["saldo_final_t1"],
                "saldo_final_t2":  res["saldo_final_t2"],
                "ke_anual":        ke_anual,
                "wacc_anual":      wacc_anual,
                "elegible":        "Sí" if elegible else "No",
            })
            if verbose:
                print(f"  D={pct_d:.0%}  RCOP={res['rcop_vpn']/1e6:.1f}M  "
                      f"VPN FCFE={res['vpn_fcfe']:,.0f}  Elegible={'Sí' if elegible else 'No'}")
        except Exception as e:
            if verbose:
                print(f"  D={pct_d:.0%}  ERROR: {e}")
            resultados.append({
                "pct_deuda": pct_d, "pct_equity": 1 - pct_d,
                "rcop_vpn": None, "vpn_fcfe": None, "vpn_fcff": None,
                "saldo_final_t1": None, "saldo_final_t2": None,
                "ke_anual": None, "wacc_anual": None, "elegible": "Error",
            })

    return pd.DataFrame(resultados)


# ─────────────────────────────────────────────────────────────────────
# TIR
# ─────────────────────────────────────────────────────────────────────

def calcular_tir(flujos: np.ndarray, periodos_por_anio: int = 12) -> float:
    """TIR anualizada a partir de flujos mensuales."""
    import numpy_financial as npf
    tir_mensual = npf.irr(flujos)
    if np.isnan(tir_mensual):
        return np.nan
    return (1 + tir_mensual) ** periodos_por_anio - 1


if __name__ == "__main__":
    from params import Params
    import time

    p = Params()
    tl = build_timeline(p)

    print("=" * 60)
    print("Punto único — RCOP óptimo a 80% deuda")
    print("=" * 60)
    t0 = time.time()
    res = optimizar_rcop(pct_deuda=0.80, p=p, tl=tl, verbose=True)
    print(f"\nRCOP VPN óptimo:  USD {res['rcop_vpn']/1e6:.2f}M")
    print(f"VPN FCFE:         USD {res['vpn_fcfe']:,.0f}")
    print(f"Saldo final T1:   USD {res['saldo_final_t1']:,.0f}")
    print(f"Saldo final T2:   USD {res['saldo_final_t2']:,.0f}")
    print(f"Ke anual:         {(1+res['ke_m'])**12-1:.2%}")
    print(f"WACC anual:       {(1+res['wacc_m'])**12-1:.2%}")
    print(f"Tiempo:           {time.time()-t0:.2f}s")

    print("\n" + "=" * 60)
    print("Barrido RCOP (0% a 90% deuda, paso 10%)")
    print("=" * 60)
    df_barrido = barrido_rcop(p, tl, pct_deuda_range=np.arange(0.0, 0.91, 0.10))
    print(df_barrido[["pct_deuda", "rcop_vpn", "vpn_fcfe",
                       "ke_anual", "wacc_anual", "elegible"]].to_string())

    # TIR
    df_opt = res["df"]
    tir_fcff = calcular_tir(df_opt["fcff"].values)
    tir_fcfe = calcular_tir(df_opt["fcfe"].values)
    print(f"\nTIR Proyecto (FCFF): {tir_fcff:.2%}")
    print(f"TIR Equity  (FCFE): {tir_fcfe:.2%}")
