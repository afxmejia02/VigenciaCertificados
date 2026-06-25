"""Consulta de certificados en el Ministerio de Trabajo (Centros de Entrenamiento).

Consulta el servicio publico:
  https://app2.mintrabajo.gov.co/CentrosEntrenamiento/consulta_ext.aspx

Es una pagina ASP.NET WebForms, asi que el flujo es:
1. GET a la pagina para capturar los campos ocultos (__VIEWSTATE, etc.).
2. POST reenviando esos campos + tipo de documento + cedula, en la misma sesion.
3. La respuesta llega en consulta_lista.aspx; se parsean las tablas de resultado.

Dependencias:  pip install requests pandas lxml
"""

import io
import re
import sys
import time
import requests
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

# Vigencia (en anos) de cada tipo de certificado.
VIGENCIA_ANIOS = {"ALTURAS": 1, "ESPACIOS": 3}

# Las llamadas usan verify=False porque el sitio del Estado a veces tiene
# problemas de cadena de certificados. Silenciamos solo esa advertencia.
requests.packages.urllib3.disable_warnings()

URL = "https://app2.mintrabajo.gov.co/CentrosEntrenamiento/consulta_ext.aspx"

# Tipos de documento validos segun el formulario del sitio.
TIPOS_DOCUMENTO = {"CC", "CE", "PA", "PE", "PP", "RC", "TI"}


def validar_cedula(cedula: str) -> str:
    """Normaliza y valida el formato de una cedula (solo digitos)."""
    limpia = str(cedula).strip().replace(".", "").replace(",", "").replace(" ", "")
    if not limpia.isdigit():
        raise ValueError(f"La cedula debe contener solo digitos: {cedula!r}")
    if not (4 <= len(limpia) <= 25):
        raise ValueError(f"Longitud de cedula no valida ({len(limpia)} digitos): {cedula!r}")
    return limpia


def _campo_oculto(html: str, name: str) -> str:
    """Extrae el value de un input hidden de ASP.NET."""
    m = re.search(r'id="' + re.escape(name) + r'"[^>]*value="([^"]*)"', html)
    return m.group(1) if m else ""


def consultar_cedula(cedula: str, tipo_documento: str = "CC") -> dict:
    """Consulta el Ministerio de Trabajo a partir de una cedula.

    Devuelve un dict con:
      - cedula, tipo_documento
      - encontrado: bool
      - tablas: lista de DataFrames con los resultados (si los hay)
      - mensaje: texto del sitio cuando no hay resultados
      - html: HTML crudo de la respuesta (util para depurar)
    """
    cedula = validar_cedula(cedula)
    tipo_documento = tipo_documento.upper().strip()
    if tipo_documento not in TIPOS_DOCUMENTO:
        raise ValueError(f"tipo_documento invalido {tipo_documento!r}. Use uno de {sorted(TIPOS_DOCUMENTO)}")

    sesion = requests.Session()
    sesion.headers["User-Agent"] = "Mozilla/5.0"

    # Cronometrar el tiempo que tarda el sitio en responder (GET + POST).
    inicio = time.perf_counter()

    # 1) GET para capturar los campos ocultos.
    inicial = sesion.get(URL, timeout=20, verify=False)
    inicial.raise_for_status()

    # 2) POST con la cedula + campos ocultos.
    datos = {
        "__VIEWSTATE": _campo_oculto(inicial.text, "__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": _campo_oculto(inicial.text, "__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": _campo_oculto(inicial.text, "__EVENTVALIDATION"),
        "ctl00$contenido$tipo_documentoTextBox": tipo_documento,
        "ctl00$contenido$valor_consulta": cedula,
        "ctl00$contenido$consultar": "Consultar",
    }
    resp = sesion.post(URL, data=datos, timeout=30, verify=False, allow_redirects=True)
    resp.raise_for_status()
    html = resp.text

    segundos_consulta = time.perf_counter() - inicio

    # 3) Interpretar la respuesta.
    if "no se encontraron resultados" in html.lower():
        return {
            "cedula": cedula,
            "tipo_documento": tipo_documento,
            "encontrado": False,
            "tablas": [],
            "mensaje": "No se encontraron resultados para la consulta realizada.",
            "html": html,
            "segundos_consulta": segundos_consulta,
        }

    # Hay resultados: intentar leer las tablas.
    try:
        tablas = pd.read_html(io.StringIO(html))
    except ValueError:
        tablas = []

    return {
        "cedula": cedula,
        "tipo_documento": tipo_documento,
        "encontrado": bool(tablas),
        "tablas": tablas,
        "mensaje": "",
        "html": html,
        "segundos_consulta": segundos_consulta,
    }


def _limpiar_tabla(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia una tabla: normaliza textos y quita la columna de botones."""
    def _texto(s: str) -> str:
        s = s.replace("\xa0", " ").replace("&nbsp;", " ").replace("&nbsp", " ")
        return re.sub(r"\s+", " ", s).strip()

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


def imprimir_tablas(resultado: dict) -> None:
    """Imprime en consola, de forma legible, solo las tablas de la consulta."""
    if not resultado["encontrado"]:
        print(resultado["mensaje"])
        return

    # Mostrar columnas completas sin truncar.
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", None)
    pd.set_option("display.max_colwidth", None)

    for i, tabla in enumerate(resultado["tablas"], 1):
        limpia = _limpiar_tabla(tabla)
        print(f"\n===== Tabla {i} =====")
        print(limpia.to_string(index=False))


def _categoria(programa: str) -> str | None:
    """Clasifica el programa en ALTURAS o ESPACIOS (o None si no aplica)."""
    p = str(programa).upper()
    if "ALTURA" in p:
        return "ALTURAS"
    if "ESPACIO" in p:
        return "ESPACIOS"
    return None


def tabla_certificados(resultado: dict) -> pd.DataFrame:
    """Une todas las tablas de certificados (las que tienen PROGRAMA y FECHA FIN)."""
    partes = []
    for tabla in resultado.get("tablas", []):
        limpia = _limpiar_tabla(tabla)
        if "PROGRAMA" in limpia.columns and "FECHA FIN" in limpia.columns:
            partes.append(limpia)
    if not partes:
        return pd.DataFrame()
    return pd.concat(partes, ignore_index=True)


def analizar_vigencia(resultado: dict, hoy: date | None = None) -> list[dict]:
    """Para cada tipo de certificado, evalua si el mas reciente sigue vigente.

    Alturas: vigencia 1 ano.  Espacios confinados: vigencia 3 anos.
    """
    hoy = hoy or date.today()
    df = tabla_certificados(resultado)
    if df.empty:
        return []

    df = df.copy()
    df["categoria"] = df["PROGRAMA"].map(_categoria)
    df["fecha_fin"] = pd.to_datetime(df["FECHA FIN"], format="%d/%m/%Y", errors="coerce")

    analisis = []
    for categoria, anios in VIGENCIA_ANIOS.items():
        sub = df[(df["categoria"] == categoria) & df["fecha_fin"].notna()]
        if sub.empty:
            continue
        reciente = sub.loc[sub["fecha_fin"].idxmax()]
        fecha_fin = reciente["fecha_fin"].date()
        vence = fecha_fin + relativedelta(years=anios)
        vigente = hoy <= vence
        analisis.append({
            "categoria": categoria,
            "programa": reciente["PROGRAMA"],
            "nivel": reciente.get("NIVEL", ""),
            "fecha_fin": fecha_fin,
            "vence": vence,
            "vigente": vigente,
            "dias_restantes": (vence - hoy).days,
            "vigencia_anios": anios,
        })
    return analisis


def imprimir_vigencia(resultado: dict, hoy: date | None = None) -> None:
    """Imprime el estado de vigencia del certificado mas reciente por tipo."""
    hoy = hoy or date.today()
    analisis = analizar_vigencia(resultado, hoy)
    print(f"\n===== VIGENCIA (fecha actual: {hoy.strftime('%d/%m/%Y')}) =====")
    if not analisis:
        print("No se encontraron certificados de Alturas ni Espacios Confinados.")
        return

    for a in analisis:
        estado = "VIGENTE" if a["vigente"] else "VENCIDO"
        detalle = (
            f"hace {-a['dias_restantes']} dias" if not a["vigente"]
            else f"faltan {a['dias_restantes']} dias"
        )
        print(
            f"- {a['categoria']} (vigencia {a['vigencia_anios']} ano/s): {estado}\n"
            f"    Mas reciente: {a['programa']} | {a['nivel']}\n"
            f"    Fecha fin: {a['fecha_fin'].strftime('%d/%m/%Y')} "
            f"-> vence: {a['vence'].strftime('%d/%m/%Y')} ({detalle})"
        )


if __name__ == "__main__":
    # Asegura que la consola muestre acentos y la "n" correctamente.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    # Cronometrar todo el proceso (consulta + procesamiento).
    inicio_total = time.perf_counter()

    # Cambia este numero por una cedula real para probar.
    resultado = consultar_cedula("111111111", tipo_documento="CC")
    imprimir_tablas(resultado)
    imprimir_vigencia(resultado)

    segundos_total = time.perf_counter() - inicio_total

    print("\n===== TIEMPOS =====")
    print(f"Consulta al sitio: {resultado.get('segundos_consulta', 0):.2f} s")
    print(f"Proceso completo:  {segundos_total:.2f} s")
