"""Calculo de vigencia de los certificados.

Reglas:
- Trabajo en alturas: vigencia 1 ano.
- Espacios confinados: vigencia 3 anos.
La vigencia se cuenta desde la FECHA FIN del certificado mas reciente de cada
categoria. Un certificado esta "proximo a vencer" si su vencimiento cae dentro
de los proximos `MESES_ALERTA` meses.
"""

from datetime import date

import pandas as pd
from dateutil.relativedelta import relativedelta

from .config import ABREVIATURA, COL_VENCIMIENTO, MESES_ALERTA, VIGENCIA_ANIOS

# Estados posibles de un certificado.
VIGENTE = "VIGENTE"
PROXIMO = "PROXIMO"
VENCIDO = "VENCIDO"


def categoria(programa: str) -> str | None:
    """Clasifica el programa en ALTURAS o ESPACIOS (o None si no aplica)."""
    p = str(programa).upper()
    if "ALTURA" in p:
        return "ALTURAS"
    if "ESPACIO" in p:
        return "ESPACIOS"
    return None


def analizar(df_certificados: pd.DataFrame, hoy: date | None = None,
             meses_alerta: int = MESES_ALERTA) -> dict[str, dict]:
    """Evalua, por categoria, el certificado mas reciente.

    Devuelve un dict { 'ALTURAS': {...}, 'ESPACIOS': {...} } solo con las
    categorias presentes. Cada valor incluye fecha_fin, vence, estado y dias.
    """
    hoy = hoy or date.today()
    umbral_proximo = hoy + relativedelta(months=meses_alerta)

    if df_certificados.empty:
        return {}

    df = df_certificados.copy()
    df["categoria"] = df["PROGRAMA"].map(categoria)
    df["fecha_fin"] = pd.to_datetime(df["FECHA FIN"], format="%d/%m/%Y", errors="coerce")

    resultado: dict[str, dict] = {}
    for cat, anios in VIGENCIA_ANIOS.items():
        sub = df[(df["categoria"] == cat) & df["fecha_fin"].notna()]
        if sub.empty:
            continue
        reciente = sub.loc[sub["fecha_fin"].idxmax()]
        fecha_fin = reciente["fecha_fin"].date()
        vence = fecha_fin + relativedelta(years=anios)

        if vence < hoy:
            estado = VENCIDO
        elif vence <= umbral_proximo:
            estado = PROXIMO
        else:
            estado = VIGENTE

        resultado[cat] = {
            "programa": reciente["PROGRAMA"],
            "nivel": reciente.get("NIVEL", ""),
            "fecha_fin": fecha_fin,
            "vence": vence,
            "estado": estado,
            "dias_restantes": (vence - hoy).days,
        }
    return resultado


def _fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


# Nombres legibles por categoria para las observaciones.
NOMBRE_CATEGORIA = {"ALTURAS": "ALTURAS", "ESPACIOS": "ESPACIOS"}


def resumen(analisis: dict[str, dict]) -> dict:
    """Convierte el analisis por categoria en las columnas de salida.

    Devuelve un dict con:
      - TIPO: ALT, ESC, ALT-ESC o NINGUNO
      - Vencimiento Alturas / Vencimiento Espacios: fecha de vencimiento o ""
      - OBSERVACIONES: VIGENTE / VIGENTES / ALTURAS VENCIDO / ESPACIOS VENCIDO
      - _estado: estado global para colorear la fila (VENCIDO/PROXIMO/VIGENTE/NINGUNO)
    """
    base = {
        "TIPO": "NINGUNO",
        COL_VENCIMIENTO["ALTURAS"]: "",
        COL_VENCIMIENTO["ESPACIOS"]: "",
        "OBSERVACIONES": "Sin certificados",
        "_estado": "NINGUNO",
    }
    if not analisis:
        return base

    presentes = [c for c in VIGENCIA_ANIOS if c in analisis]

    # TIPO: abreviaturas de las categorias presentes (ALT, ESC, ALT-ESC).
    base["TIPO"] = "-".join(ABREVIATURA[c] for c in presentes)

    # Fechas de vencimiento por categoria.
    for c in presentes:
        base[COL_VENCIMIENTO[c]] = _fmt(analisis[c]["vence"])

    vencidas = [c for c in presentes if analisis[c]["estado"] == VENCIDO]
    proximas = [c for c in presentes if analisis[c]["estado"] == PROXIMO]

    # OBSERVACIONES: si hay vencidas las nombra; si no, VIGENTE / VIGENTES.
    if vencidas:
        base["OBSERVACIONES"] = "; ".join(f"{NOMBRE_CATEGORIA[c]} VENCIDO" for c in vencidas)
    else:
        base["OBSERVACIONES"] = "VIGENTES" if len(presentes) > 1 else "VIGENTE"

    # Estado global para el color de la fila (vencido manda sobre proximo).
    if vencidas:
        base["_estado"] = VENCIDO
    elif proximas:
        base["_estado"] = PROXIMO
    else:
        base["_estado"] = VIGENTE

    return base
