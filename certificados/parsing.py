"""Extraccion y limpieza de las tablas que devuelve el Ministerio.

La respuesta trae varias tablas: una con los datos del usuario y una o mas con
los certificados. Aqui las leemos, las limpiamos y dejamos una sola tabla de
certificados lista para analizar.
"""

import io
import re

import pandas as pd


def _texto(s: str) -> str:
    """Normaliza un texto: quita &nbsp, espacios repetidos y bordes."""
    s = s.replace("\xa0", " ").replace("&nbsp;", " ").replace("&nbsp", " ")
    return re.sub(r"\s+", " ", s).strip()


def _limpiar_tabla(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza textos de una tabla y quita la columna de botones."""
    df = df.copy()
    df.columns = [_texto(str(c)) for c in df.columns]
    for col in df.columns:
        df[col] = df[col].map(lambda x: _texto(x) if isinstance(x, str) else x)
    # Quitar columnas sin nombre o que solo contienen el boton "GENERAR CONSTANCIA".
    a_quitar = [
        c for c in df.columns
        if c.lower().startswith("unnamed")
        or df[c].astype(str).str.contains("GENERAR CONSTANCIA", case=False).all()
    ]
    return df.drop(columns=a_quitar)


def leer_tablas(html: str) -> list[pd.DataFrame]:
    """Lee todas las tablas HTML de la respuesta."""
    try:
        return pd.read_html(io.StringIO(html))
    except ValueError:
        return []


def tabla_certificados(html: str) -> pd.DataFrame:
    """Devuelve una unica tabla con los certificados (PROGRAMA + FECHA FIN).

    Une todas las tablas de certificados (el sitio a veces las parte en varias).
    """
    partes = []
    for tabla in leer_tablas(html):
        limpia = _limpiar_tabla(tabla)
        if "PROGRAMA" in limpia.columns and "FECHA FIN" in limpia.columns:
            partes.append(limpia)
    if not partes:
        return pd.DataFrame()
    return pd.concat(partes, ignore_index=True)


def nombre_usuario(html: str) -> str:
    """Extrae el nombre del usuario de la tabla de cabecera (si esta)."""
    for tabla in leer_tablas(html):
        limpia = _limpiar_tabla(tabla)
        texto = " ".join(str(v) for v in limpia.values.ravel())
        m = re.search(r"NOMBRE DEL USUARIO:\s*(.+?)\s+N[UÚ]MERO", texto, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""
