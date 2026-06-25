"""Paquete para consultar y evaluar certificados del Ministerio de Trabajo."""

from .consulta import consultar_cedula, validar_cedula
from .parsing import tabla_certificados, nombre_usuario
from .vigencia import analizar, resumen, categoria
from .procesamiento import parsear_pegado, evaluar_cedula, procesar

__all__ = [
    "consultar_cedula",
    "validar_cedula",
    "tabla_certificados",
    "nombre_usuario",
    "analizar",
    "resumen",
    "categoria",
    "parsear_pegado",
    "evaluar_cedula",
    "procesar",
]
