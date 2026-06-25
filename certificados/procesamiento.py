"""Procesamiento masivo: del texto pegado a la tabla de salida.

Une todas las piezas: interpreta lo que el usuario pega desde el Excel, consulta
cada cedula, evalua la vigencia y arma un DataFrame con las columnas nuevas
listo para copiar de vuelta al Excel.
"""

from datetime import date
from typing import Callable

import pandas as pd

from .config import COL_VENCIMIENTO, COLUMNAS_ENTRADA, COLUMNAS_SALIDA, MESES_ALERTA
from .consulta import consultar_cedula, validar_cedula
from .parsing import tabla_certificados
from .vigencia import analizar, resumen


def parsear_pegado(texto: str, columnas: list[str] | None = None) -> pd.DataFrame:
    """Convierte el texto pegado (separado por tabs) en un DataFrame.

    - Separa por tabulaciones (como copia Excel). Si una fila no tiene tabs,
      cae a separar por 2+ espacios.
    - Ignora una posible fila de encabezado (si contiene la palabra CEDULA).
    - Ajusta cada fila al numero de columnas esperado.
    """
    columnas = columnas or COLUMNAS_ENTRADA
    filas = []
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        celdas = linea.split("\t") if "\t" in linea else linea.split("  ")
        celdas = [c.strip() for c in celdas if c.strip() != ""]
        if not celdas:
            continue
        # Saltar encabezado pegado por error.
        if any("CEDULA" in c.upper() for c in celdas):
            continue
        # Ajustar al numero de columnas (rellena o recorta).
        celdas = (celdas + [""] * len(columnas))[:len(columnas)]
        filas.append(celdas)

    return pd.DataFrame(filas, columns=columnas)


def evaluar_cedula(cedula, tipo_documento: str = "CC", hoy: date | None = None,
                   meses_alerta: int = MESES_ALERTA) -> dict:
    """Consulta y evalua una sola cedula. Devuelve las columnas de salida."""
    hoy = hoy or date.today()
    try:
        cedula_limpia = validar_cedula(cedula)
    except ValueError:
        return {
            "TIPO": "",
            COL_VENCIMIENTO["ALTURAS"]: "",
            COL_VENCIMIENTO["ESPACIOS"]: "",
            "OBSERVACIONES": f"Cedula invalida: {cedula!r}",
            "_estado": "ERROR",
            "_segundos": 0.0,
        }

    consulta = consultar_cedula(cedula_limpia, tipo_documento=tipo_documento)
    if not consulta["encontrado"]:
        return {
            "TIPO": "NINGUNO",
            COL_VENCIMIENTO["ALTURAS"]: "",
            COL_VENCIMIENTO["ESPACIOS"]: "",
            "OBSERVACIONES": "No se encontraron certificados",
            "_estado": "NINGUNO",
            "_segundos": consulta["segundos_consulta"],
        }

    df_cert = tabla_certificados(consulta["html"])
    analisis = analizar(df_cert, hoy=hoy, meses_alerta=meses_alerta)
    fila = resumen(analisis)
    fila["_segundos"] = consulta["segundos_consulta"]
    return fila


def procesar(
    df_entrada: pd.DataFrame,
    tipo_documento: str = "CC",
    hoy: date | None = None,
    meses_alerta: int = MESES_ALERTA,
    progreso: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """Procesa todas las filas de entrada y agrega las columnas de salida.

    `progreso(i, total)` es un callback opcional para mostrar avance (Streamlit).
    Devuelve el DataFrame de entrada + las columnas de COLUMNAS_SALIDA.
    """
    hoy = hoy or date.today()
    salidas = []
    total = len(df_entrada)

    for i, (_, fila) in enumerate(df_entrada.iterrows(), 1):
        evaluacion = evaluar_cedula(
            fila["CEDULA"], tipo_documento=tipo_documento, hoy=hoy, meses_alerta=meses_alerta
        )
        salidas.append(evaluacion)
        if progreso:
            progreso(i, total)

    df_salida = pd.DataFrame(salidas)
    # Columnas de salida + la interna _estado (para colorear, se oculta al mostrar).
    columnas = [c for c in COLUMNAS_SALIDA if c in df_salida.columns]
    if "_estado" in df_salida.columns:
        columnas.append("_estado")
    resultado = pd.concat(
        [df_entrada.reset_index(drop=True), df_salida[columnas].reset_index(drop=True)],
        axis=1,
    )
    return resultado
