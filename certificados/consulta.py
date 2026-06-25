"""Consulta al servicio del Ministerio de Trabajo.

La pagina es ASP.NET WebForms, por lo que el flujo es:
1. GET a la pagina para capturar los campos ocultos (__VIEWSTATE, etc.).
2. POST reenviando esos campos + tipo de documento + cedula, en la misma sesion.
3. La respuesta llega en consulta_lista.aspx con las tablas de resultado.
"""

import re
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import TIPOS_DOCUMENTO, URL_CONSULTA

# El sitio del Estado a veces tiene problemas de cadena de certificados;
# usamos verify=False y silenciamos solo esa advertencia.
requests.packages.urllib3.disable_warnings()

# Timeout por defecto (conexion, lectura) en segundos.
TIMEOUT_POR_DEFECTO = (15, 45)


def _nueva_sesion() -> requests.Session:
    """Crea una sesion con reintentos automaticos ante fallos de red."""
    sesion = requests.Session()
    sesion.headers["User-Agent"] = "Mozilla/5.0"
    reintentos = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.5,  # espera 0s, 1.5s, 3s, ... entre intentos
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
    )
    adaptador = HTTPAdapter(max_retries=reintentos)
    sesion.mount("https://", adaptador)
    sesion.mount("http://", adaptador)
    return sesion


def validar_cedula(cedula) -> str:
    """Normaliza y valida una cedula. Devuelve solo digitos o lanza ValueError."""
    limpia = str(cedula).strip().replace(".", "").replace(",", "").replace(" ", "")
    # Excel a veces entrega numeros como "13747537.0".
    if limpia.endswith(".0"):
        limpia = limpia[:-2]
    if not limpia.isdigit():
        raise ValueError(f"La cedula debe contener solo digitos: {cedula!r}")
    if not (4 <= len(limpia) <= 25):
        raise ValueError(f"Longitud de cedula no valida ({len(limpia)} digitos): {cedula!r}")
    return limpia


def _campo_oculto(html: str, name: str) -> str:
    """Extrae el value de un input hidden de ASP.NET."""
    m = re.search(r'id="' + re.escape(name) + r'"[^>]*value="([^"]*)"', html)
    return m.group(1) if m else ""


def consultar_cedula(cedula, tipo_documento: str = "CC", timeout=TIMEOUT_POR_DEFECTO) -> dict:
    """Consulta el Ministerio de Trabajo a partir de una cedula.

    Devuelve un dict con:
      - cedula, tipo_documento
      - encontrado: bool (True si la pagina devolvio resultados)
      - html: HTML crudo de la respuesta (para parsear despues)
      - mensaje: texto cuando no hay resultados
      - segundos_consulta: cuanto tardo el sitio en responder (GET + POST)
    """
    cedula = validar_cedula(cedula)
    tipo_documento = tipo_documento.upper().strip()
    if tipo_documento not in TIPOS_DOCUMENTO:
        raise ValueError(
            f"tipo_documento invalido {tipo_documento!r}. Use uno de {list(TIPOS_DOCUMENTO)}"
        )

    sesion = _nueva_sesion()

    inicio = time.perf_counter()

    # 1) GET para capturar los campos ocultos.
    inicial = sesion.get(URL_CONSULTA, timeout=timeout, verify=False)
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
    resp = sesion.post(URL_CONSULTA, data=datos, timeout=timeout, verify=False)
    resp.raise_for_status()
    html = resp.text

    segundos = time.perf_counter() - inicio
    encontrado = "no se encontraron resultados" not in html.lower()

    return {
        "cedula": cedula,
        "tipo_documento": tipo_documento,
        "encontrado": encontrado,
        "html": html,
        "mensaje": "" if encontrado else "No se encontraron resultados para la consulta.",
        "segundos_consulta": segundos,
    }
