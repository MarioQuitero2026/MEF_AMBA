"""
AMBA I — Motor Financiero Python
Módulo: timeline.py
Genera el eje temporal mensual y los factores de indexación IPC / deflactor.
Equivalente a 03_TimeLine + factores en 04_CAPEX, 05_Ingresos, etc.
"""
import numpy as np
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
from params import Params, DEFAULT_PARAMS


def build_timeline(p: Params = DEFAULT_PARAMS) -> pd.DataFrame:
    """
    Construye el DataFrame base del modelo: un registro por período mensual.
    Columnas: periodo, bop, eop, anio, ipc_ea, ipc_em,
              factor_index_ipc_m, factor_deflactor_ipc_m
    """
    n = p.cronograma.duracion_total + 1    # períodos 0..231
    inicio = p.cronograma.inicio_proyecto

    registros = []
    for t in range(n):
        bop = inicio + relativedelta(months=t)
        eop = bop + relativedelta(months=1) - relativedelta(days=1)
        anio = bop.year

        # IPC USD mensual equivalente
        ipc_ea = p.macro.inflacion_usd_anual.get(anio, p.macro.inflacion_usd_largo)
        ipc_em = (1 + ipc_ea) ** (1/12) - 1

        registros.append({
            "periodo": t,
            "bop":     bop,
            "eop":     eop,
            "anio":    anio,
            "ipc_ea":  ipc_ea,
            "ipc_em":  ipc_em,
        })

    df = pd.DataFrame(registros)

    # Factor de indexación acumulado (base = período 0 = 1.0)
    df["factor_index_ipc_m"] = (1 + df["ipc_em"]).cumprod()
    df.loc[0, "factor_index_ipc_m"] = 1.0

    # Factor deflactor (inverso del index)
    df["factor_deflactor_ipc_m"] = 1.0 / df["factor_index_ipc_m"]

    # Flags de etapas (útiles para filtrar en hojas posteriores)
    crono = p.cronograma
    df["en_construccion_e1"] = df["bop"].apply(
        lambda d: crono.inicio_construccion_e1 <= d <
                  crono.inicio_construccion_e1 + relativedelta(months=crono.duracion_construccion_e1)
    )
    df["en_oym_e1"] = df["bop"].apply(
        lambda d: crono.inicio_oym_e1 <= d <
                  crono.inicio_oym_e1 + relativedelta(months=crono.duracion_oym_e1)
    )
    df["en_construccion_e2"] = df["bop"].apply(
        lambda d: crono.inicio_construccion_e2 <= d <
                  crono.inicio_construccion_e2 + relativedelta(months=crono.duracion_construccion_e2)
    )
    df["en_oym_e2"] = df["bop"].apply(
        lambda d: crono.inicio_oym_e2 <= d <
                  crono.inicio_oym_e2 + relativedelta(months=crono.duracion_oym_e2)
    )

    return df


def periodo_de_fecha(fecha: date, tl: pd.DataFrame) -> int:
    """Devuelve el índice de período correspondiente a una fecha."""
    mask = (tl["bop"] <= fecha) & (tl["eop"] >= fecha)
    if mask.any():
        return int(tl.loc[mask, "periodo"].iloc[0])
    # Si la fecha cae exactamente en bop
    mask2 = tl["bop"] == fecha
    if mask2.any():
        return int(tl.loc[mask2, "periodo"].iloc[0])
    return -1


if __name__ == "__main__":
    tl = build_timeline()
    print(tl[["periodo", "bop", "eop", "anio", "ipc_ea", "ipc_em",
              "factor_index_ipc_m", "factor_deflactor_ipc_m"]].head(20).to_string())
    print(f"\nTotal períodos: {len(tl)}")
    print(f"Inicio: {tl['bop'].iloc[0]}  |  Fin: {tl['eop'].iloc[-1]}")
