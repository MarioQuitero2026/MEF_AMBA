"""
AMBA I — Motor Financiero Python
Módulo: params.py
Todos los supuestos del modelo. Equivalente a 01_Inputs + 00_Controles.
Ningún valor hardcodeado fuera de este archivo.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List


# ─────────────────────────────────────────────
# SELECTORES (equivalente a 00_Controles)
# ─────────────────────────────────────────────
@dataclass
class Controles:
    rigi: bool = True                    # True = CON RIGI, False = SIN RIGI
    capex_global: bool = True            # True = CAPEX global, False = por lote
    inflacion_rcop: bool = True          # True = RCOP indexado a IPC
    inflacion_ti: bool = False           # False = Tarifa TI sin inflación (selector 4 = 1)
    capitalizar_intereses: bool = True   # True = intereses capitalizados en construcción
    beta_fija: bool = False              # False = Hamada re-leveraging, True = beta fija


# ─────────────────────────────────────────────
# MACRO
# ─────────────────────────────────────────────
@dataclass
class Macro:
    inflacion_usd_corto: float = 0.027       # % EA
    inflacion_usd_largo: float = 0.020       # % EA (a partir de 2028)
    tipo_cambio_corto: float = 1_753         # ARS/USD corto plazo
    tipo_cambio_largo: float = 1_980         # ARS/USD largo plazo
    tasa_impositiva: float = 0.25            # Impuesto ganancias base

    # IPIM Argentina por año (para indexación ARS)
    ipim_anual: Dict[int, float] = field(default_factory=lambda: {
        2026: 0.30, 2027: 0.16, 2028: 0.12, 2029: 0.09,
        2030: 0.07, 2031: 0.06, 2032: 0.05, 2033: 0.04,
        2034: 0.03, 2035: 0.03,
    })

    # Inflación USD por año
    inflacion_usd_anual: Dict[int, float] = field(default_factory=lambda: {
        2026: 0.027, 2027: 0.027, 2028: 0.02, 2029: 0.02,
        2030: 0.02,  2031: 0.02,  2032: 0.02, 2033: 0.02,
        2034: 0.02,  2035: 0.02,  2036: 0.02, 2037: 0.02,
        2038: 0.02,  2039: 0.02,  2040: 0.02, 2041: 0.02,
        2042: 0.02,  2043: 0.02,  2044: 0.02, 2045: 0.02,
        2046: 0.02,
    })


# ─────────────────────────────────────────────
# CRONOGRAMA
# ─────────────────────────────────────────────
@dataclass
class Cronograma:
    inicio_proyecto: date = date(2026, 6, 1)     # BoP período 0

    # Etapa 1
    inicio_construccion_e1: date = date(2027, 1, 1)
    duracion_construccion_e1: int = 42            # meses
    inicio_oym_e1: date = date(2030, 7, 1)
    duracion_oym_e1: int = 180

    # Etapa 2
    inicio_construccion_e2: date = date(2030, 7, 31)
    duracion_construccion_e2: int = 10
    inicio_oym_e2: date = date(2031, 5, 31)
    duracion_oym_e2: int = 180

    duracion_total: int = 231                     # meses totales del modelo


# ─────────────────────────────────────────────
# LOTES  (Etapa 1: L1-L6 activos, L7-L10 = 0)
# ─────────────────────────────────────────────
@dataclass
class LoteConfig:
    pct_capex: float          # % del CAPEX total asignado al lote
    pct_curva_s: float        # % para CAPEX global (Curva S)
    inicio_construccion: date
    duracion_construccion: int   # meses
    pct_remuneracion: float      # % del RCOP total
    duracion_remuneracion: int   # meses (84 = 7 años)
    inicio_remuneracion: date
    vida_util_rigi: int = 9      # años depreciación CON RIGI
    vida_util_sin_rigi: int = 15 # años depreciación SIN RIGI


# Etapa 1 — 6 lotes activos
LOTES_E1: List[LoteConfig] = [
    LoteConfig(0.1346, 0.04, date(2027,  1,  1),  7, 0.10, 84, date(2027, 10,  1), 9, 15),
    LoteConfig(0.1346, 0.10, date(2027,  8,  1),  7, 0.10, 84, date(2028,  5,  1), 9, 15),
    LoteConfig(0.1346, 0.16, date(2028,  3,  1),  7, 0.15, 84, date(2028, 12,  1), 9, 15),
    LoteConfig(0.1346, 0.18, date(2028, 10,  1),  7, 0.10, 84, date(2029,  7,  1), 9, 15),
    LoteConfig(0.1346, 0.11, date(2029,  5,  1),  7, 0.05, 84, date(2030,  2,  1), 9, 15),
    LoteConfig(0.1346, 0.06, date(2029, 12,  1),  7, 0.15, 84, date(2030,  9,  1), 9, 15),
]

# Etapa 2 — 4 lotes activos
LOTES_E2: List[LoteConfig] = [
    LoteConfig(0.0577, 0.06, date(2030,  7,  1),  3, 0.10, 84, date(2030, 12,  1), 9, 15),
    LoteConfig(0.0577, 0.12, date(2030, 10,  1),  3, 0.05, 84, date(2031,  3,  1), 9, 15),
    LoteConfig(0.0385, 0.11, date(2031,  1,  1),  2, 0.05, 84, date(2031,  5,  1), 9, 15),
    LoteConfig(0.0385, 0.06, date(2031,  3,  1),  2, 0.15, 84, date(2031,  7,  1), 9, 15),
]


# ─────────────────────────────────────────────
# CAPEX
# ─────────────────────────────────────────────
@dataclass
class Capex:
    capex_total_rigi: float     = 848_653_187.12    # USD sin IVA, CON RIGI
    capex_total_sin_rigi: float = 898_020_241.66    # USD sin IVA, SIN RIGI
    aporte_financiero: float    = 50_000_000        # USD (subsidio del Estado)
    aporte_especie: float       = 50_000_000        # USD
    tasa_supervision: float     = 0.0325            # % del CAPEX
    pct_iva_capex: float        = 0.90              # % del CAPEX sujeto a IVA

    # Garantías
    pct_garantia_habilitacion: float = 0.10         # % del CAPEX
    prima_anual_carta_credito: float = 0.008
    valor_garantia_anticipo: float   = 50_000_000

    # Escalones del aporte financiero
    escalones_aporte: List = field(default_factory=lambda: [
        (date(2027,  1,  1), 0.108),
        (date(2027,  8, 31), 0.108),
        (date(2028,  3, 31), 0.108),
        (date(2028, 10, 31), 0.108),
        (date(2029,  6, 30), 0.168),
        (date(2030,  2, 28), 0.200),
        (date(2030, 10, 31), 0.200),
    ])

    def capex_total(self, rigi: bool) -> float:
        return self.capex_total_rigi if rigi else self.capex_total_sin_rigi

    def capex_neto(self, rigi: bool) -> float:
        """CAPEX descontando aportes del Estado"""
        return self.capex_total(rigi) - self.aporte_financiero - self.aporte_especie


# ─────────────────────────────────────────────
# TRIBUTOS
# ─────────────────────────────────────────────
@dataclass
class Tributos:
    # CON RIGI
    iva_general_rigi: float     = 0.00
    iva_bienes_cap_rigi: float  = 0.00
    tasa_ganancias_rigi: float  = 0.25
    pct_deduccion_dcb_rigi: float = 1.00   # 100% de débitos/créditos deducible en ganancias

    # SIN RIGI
    iva_general_sin_rigi: float    = 0.21
    iva_bienes_cap_sin_rigi: float = 0.105
    tasa_ganancias_sin_rigi: float = 0.25  # tasa base (escalonada en ARS)
    pct_deduccion_dcb_sin_rigi: float = 0.33
    plazo_quebrantos_sin_rigi: int = 5     # años

    # Débitos y créditos (ambos escenarios)
    tasa_debitos: float  = 0.006
    tasa_creditos: float = 0.006

    def iva(self, rigi: bool) -> float:
        return self.iva_general_rigi if rigi else self.iva_general_sin_rigi

    def iva_bienes_cap(self, rigi: bool) -> float:
        return self.iva_bienes_cap_rigi if rigi else self.iva_bienes_cap_sin_rigi

    def pct_deduccion_dcb(self, rigi: bool) -> float:
        return self.pct_deduccion_dcb_rigi if rigi else self.pct_deduccion_dcb_sin_rigi


# ─────────────────────────────────────────────
# OPEX
# ─────────────────────────────────────────────
@dataclass
class Opex:
    pct_capex_operado: float     = 0.80     # % del CAPEX operado por concesionario
    seguros_polizas: float       = 0.0025   # % del CAPEX
    personal: float              = 0.0040
    mantenimiento: float         = 0.0050
    operacion_sistema: float     = 0.0020
    logistica: float             = 0.0010
    impuestos_operacion: float   = 0.0015
    # Rotaciones capital de trabajo (días)
    rot_cxc: int = 30
    rot_cxp: int = 30
    rot_inventarios: int = 30
    # Tarifa TI (a completar cuando se defina)
    tarifa_ti_e1_mensual: float = 0.0
    tarifa_ti_e2_mensual: float = 0.0

    def total_pct_capex(self) -> float:
        return (self.seguros_polizas + self.personal + self.mantenimiento +
                self.operacion_sistema + self.logistica + self.impuestos_operacion)


# ─────────────────────────────────────────────
# DEUDA
# ─────────────────────────────────────────────
@dataclass
class Deuda:
    pct_deuda: float         = 0.80          # % leverage objetivo
    kd_anual: float          = 0.12          # Costo nominal anual
    dscr_objetivo: float     = 1.20          # DSCR mínimo para sculpting
    # Tramo 1
    commitment_fee_t1: float = 0.005
    comision_originacion_t1: float = 0.017
    fecha_originacion_t1: date = date(2027, 1, 1)
    # Tramo 2
    commitment_fee_t2: float = 0.005
    comision_originacion_t2: float = 0.017
    fecha_originacion_t2: date = date(2030, 7, 31)

    @property
    def kd_mensual(self) -> float:
        return (1 + self.kd_anual) ** (1/12) - 1

    def kd_after_tax(self, rigi: bool, tasa_imp: float = 0.25) -> float:
        if rigi:
            return self.kd_anual * (1 - tasa_imp)  # 12% * 0.75 = 9%
        else:
            return self.kd_anual * (1 - tasa_imp * 0.33 / 0.25)  # ajuste SIN RIGI


# ─────────────────────────────────────────────
# EQUITY
# ─────────────────────────────────────────────
@dataclass
class Equity:
    aporte_inicial_pct: float   = 0.25      # % del equity total aportado al inicio
    mes_pago_dividendos: int    = 12        # pago anual
    pct_caja_dividendos: float  = 0.80
    impuesto_utilidades: float  = 0.07


# ─────────────────────────────────────────────
# WACC / CAPM
# ─────────────────────────────────────────────
@dataclass
class WaccParams:
    rf: float                  = 0.0286     # Risk-free (UST 10Y, Damodaran feb-2026)
    rm_menos_rf: float         = 0.07567    # Premio riesgo mercado (S&P 500 histórico)
    beta_desapalancada: float  = 0.30       # Damodaran Power sector feb-2026
    riesgo_pais_rigi: float    = 0.08       # CON RIGI
    riesgo_pais_sin_rigi: float = 0.10      # SIN RIGI
    tasa_impositiva: float     = 0.25

    # Beta fija por escenario (cuando beta_fija = True en Controles)
    beta_fija_rigi: float      = 0.825
    beta_fija_sin_rigi: float  = 0.755

    def beta_apalancada(self, pct_deuda: float, rigi: bool, fija: bool = False) -> float:
        """Hamada re-leveraging: βL = βU * (1 + (1-T) * D/E)"""
        if fija:
            return self.beta_fija_rigi if rigi else self.beta_fija_sin_rigi
        pct_equity = 1 - pct_deuda
        if pct_equity <= 0:
            return self.beta_desapalancada * (1 + (1 - self.tasa_impositiva) * 99)
        d_e = pct_deuda / pct_equity
        return self.beta_desapalancada * (1 + (1 - self.tasa_impositiva) * d_e)

    def ke_anual(self, pct_deuda: float, rigi: bool, fija: bool = False) -> float:
        """CAPM: Ke = RF + β * (Rm - Rf) + Riesgo País"""
        beta = self.beta_apalancada(pct_deuda, rigi, fija)
        rp = self.riesgo_pais_rigi if rigi else self.riesgo_pais_sin_rigi
        return self.rf + beta * self.rm_menos_rf + rp

    def wacc_anual(self, pct_deuda: float, kd_after_tax: float,
                   rigi: bool, fija: bool = False) -> float:
        """WACC = Ke*%E + Kd_at*%D"""
        pct_equity = 1 - pct_deuda
        ke = self.ke_anual(pct_deuda, rigi, fija)
        return ke * pct_equity + kd_after_tax * pct_deuda

    def wacc_mensual(self, pct_deuda: float, kd_after_tax: float,
                     rigi: bool, fija: bool = False) -> float:
        return (1 + self.wacc_anual(pct_deuda, kd_after_tax, rigi, fija)) ** (1/12) - 1

    def ke_mensual(self, pct_deuda: float, rigi: bool, fija: bool = False) -> float:
        return (1 + self.ke_anual(pct_deuda, rigi, fija)) ** (1/12) - 1


# ─────────────────────────────────────────────
# OBJETO RAÍZ — agrupa todos los parámetros
# ─────────────────────────────────────────────
@dataclass
class Params:
    controles:  Controles  = field(default_factory=Controles)
    macro:      Macro      = field(default_factory=Macro)
    cronograma: Cronograma = field(default_factory=Cronograma)
    capex:      Capex      = field(default_factory=Capex)
    tributos:   Tributos   = field(default_factory=Tributos)
    opex:       Opex       = field(default_factory=Opex)
    deuda:      Deuda      = field(default_factory=Deuda)
    equity:     Equity     = field(default_factory=Equity)
    wacc:       WaccParams = field(default_factory=WaccParams)


# Instancia por defecto lista para importar
DEFAULT_PARAMS = Params()
