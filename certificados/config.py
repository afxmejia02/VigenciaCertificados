"""Configuracion central del proyecto.

Aqui viven las constantes que se reutilizan en todos los modulos: la URL del
servicio del Ministerio, las reglas de vigencia y los nombres de las columnas
de entrada y salida. Centralizarlas facilita ajustarlas en un solo lugar.
"""

# --- Servicio del Ministerio de Trabajo (Centros de Entrenamiento) ---
URL_CONSULTA = "https://app2.mintrabajo.gov.co/CentrosEntrenamiento/consulta_ext.aspx"

# Tipos de documento validos segun el formulario del sitio.
TIPOS_DOCUMENTO = ("CC", "CE", "PA", "PE", "PP", "RC", "TI")

# --- Reglas de negocio ---
# Vigencia (en anos) de cada categoria de certificado.
VIGENCIA_ANIOS = {
    "ALTURAS": 1,
    "ESPACIOS": 3,
}

# Un certificado se marca "proximo a vencer" si vence dentro de estos meses.
MESES_ALERTA = 3

# Abreviaturas usadas en la columna TIPO de salida.
ABREVIATURA = {
    "ALTURAS": "ALT",
    "ESPACIOS": "ESC",
}

# --- Columnas ---
# Columnas que trae cada fila pegada desde el Excel (en orden).
COLUMNAS_ENTRADA = ["ITEM", "CEDULA", "NOMBRE", "CARGO"]

# Columnas nuevas que genera el programa (en orden), para pegar de vuelta.
COLUMNAS_SALIDA = ["TIPO", "Vencimiento Alturas", "Vencimiento Espacios", "OBSERVACIONES"]

# Nombres de las columnas de vencimiento por categoria.
COL_VENCIMIENTO = {
    "ALTURAS": "Vencimiento Alturas",
    "ESPACIOS": "Vencimiento Espacios",
}
