"""
AMBA I — Motor Financiero Python
Módulo: resultados.py
Consolida los KPIs del modelo. Equivalente a 13_Resultados.
"""
import numpy as np
import pandas as pd
import numpy_financial as npf
from params import Params, DEFAULT_PARAMS
from timeline import build_timeline
from financiacion import calcular_financiacion, calcular_tir, barrido_rcop


def calcular_resultados(
    rcop_vpn: float,
    pct_deuda: float,
    p: Params = DEFAULT_PARAMS,
    tl: pd.DataFrame = None,
) -> dict:
    """
    Corre el modelo completo para un RCOP y % deuda dados.
    Retorna diccionario con todos los KPIs del 13_Resultados.
    """
    if tl is None:
        tl = build_timeline(p)

    df = calcular_financiacion(rcop_vpn, pct_deuda, p, tl)

    # TIR
    tir_proyecto = calcular_tir(df["fcff"].values)
    tir_equity   = calcular_tir(df["fcfe"].values)

    # WACC y Ke anuales
    ke_anual   = (1 + df.attrs["ke_m"])   ** 12 - 1
    wacc_anual = (1 + df.attrs["wacc_m"]) ** 12 - 1

    # Deuda máxima
    deuda_max_t1 = df["saldo_t1"].max()
    deuda_max_t2 = df["saldo_t2"].max()

    # Garantía por mayor exposición (máximo saldo de deuda acumulado)
    garantia_exp = df["saldo_total"].max()

    # Remuneración total nominal (suma de flujos de ingresos RCOP)
    from flujos import calcular_cfdas
    df_c = calcular_cfdas(rcop_vpn, p, tl)
    rem_total_nominal = df_c["ingresos"].sum()
    mes_max_tarifa    = df_c.loc[df_c["ingresos"].idxmax(), "bop"]
    tarifa_max_mensual = df_c["ingresos"].max()

    # CAPEX por etapa
    from capex import calcular_capex
    df_cap = calcular_capex(p, tl)
    capex_e1 = df_cap["capex_total_e1"].sum()
    capex_e2 = df_cap["capex_total_e2"].sum()

    return {
        # Valoración
        "vpn_proyecto":        df.attrs["vpn_fcff"],
        "vpn_equity":          df.attrs["vpn_fcfe"],
        "rcop_vpn":            rcop_vpn,
        "rem_total_nominal":   rem_total_nominal,
        "mes_max_tarifa":      mes_max_tarifa,
        "tarifa_max_mensual":  tarifa_max_mensual,

        # Rentabilidad
        "tir_proyecto":        tir_proyecto,
        "tir_equity":          tir_equity,
        "wacc_anual":          wacc_anual,
        "ke_anual":            ke_anual,

        # Estructura de financiamiento
        "pct_deuda":           pct_deuda,
        "deuda_max_t1":        deuda_max_t1,
        "deuda_max_t2":        deuda_max_t2,
        "garantia_exposicion": garantia_exp,
        "saldo_final_t1":      df.attrs["saldo_final_t1"],
        "saldo_final_t2":      df.attrs["saldo_final_t2"],
        "kd_anual":            p.deuda.kd_anual,

        # CAPEX
        "capex_e1":            capex_e1,
        "capex_e2":            capex_e2,
        "capex_total":         capex_e1 + capex_e2,

        # DataFrames (para gráficos)
        "df_financiacion":     df,
        "df_cfdas":            df_c,
        "df_capex":            df_cap,
        "tl":                  tl,
    }


if __name__ == "__main__":
    from params import Params
    p = Params()
    tl = build_timeline(p)

    rcop_vpn = 813_030_000   # resultado del optimizador
    pct_deuda = 0.80

    res = calcular_resultados(rcop_vpn, pct_deuda, p, tl)

    print("=" * 55)
    print("RESULTADOS AMBA I — MEF Python")
    print("=" * 55)
    print(f"RCOP VPN:             USD {res['rcop_vpn']/1e6:.1f}M")
    print(f"Remuneración nominal: USD {res['rem_total_nominal']/1e6:.1f}M")
    print(f"TIR Proyecto:         {res['tir_proyecto']:.2%}")
    print(f"TIR Equity:           {res['tir_equity']:.2%}")
    print(f"WACC anual:           {res['wacc_anual']:.2%}")
    print(f"Ke anual:             {res['ke_anual']:.2%}")
    print(f"VPN FCFF:             USD {res['vpn_proyecto']/1e6:.1f}M")
    print(f"VPN FCFE:             USD {res['vpn_equity']:,.0f}")
    print(f"Deuda máx T1:         USD {res['deuda_max_t1']/1e6:.1f}M")
    print(f"Deuda máx T2:         USD {res['deuda_max_t2']/1e6:.1f}M")
    print(f"CAPEX E1:             USD {res['capex_e1']/1e6:.1f}M")
    print(f"CAPEX E2:             USD {res['capex_e2']/1e6:.1f}M")
    print(f"Tarifa máx mensual:   USD {res['tarifa_max_mensual']/1e6:.1f}M ({res['mes_max_tarifa'].strftime('%b-%Y')})")
