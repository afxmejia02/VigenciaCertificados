"""Interfaz Streamlit para consultar certificados en masa.

Uso:
    streamlit run app.py

Flujo:
1. Pegas las celdas copiadas del Excel (ITEM, CEDULA, NOMBRE, CARGO).
2. El programa consulta cada cedula en el Ministerio y evalua la vigencia.
3. Muestra una tabla con las columnas nuevas (SI/NO, TIPO, FECHA FIN
   VIGENCIA, OBSERVACIONES) lista para copiar de vuelta al Excel.
"""

import io
import time
from datetime import date

import pandas as pd
import streamlit as st

from certificados.config import (
    COLUMNAS_ENTRADA,
    COLUMNAS_SALIDA,
    MESES_ALERTA,
    TIPOS_DOCUMENTO,
)

from certificados.procesamiento import parsear_pegado, procesar

def _to_excel(styler) -> bytes:
    """Serializa un Styler a Excel en memoria, conservando los colores de fila."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        styler.to_excel(writer, index=False, sheet_name="Resultado")
    return buffer.getvalue()


st.set_page_config(page_title="Vigencia de certificados", page_icon="✅", layout="wide")

st.title("Consulta de vigencia de certificados")
st.caption(
    "Centros de Entrenamiento - Ministerio de Trabajo. "
    "Pega las celdas del Excel y obtén el estado de vigencia."
)

# --- Barra lateral: parametros ---
with st.sidebar:
    st.header("Parámetros")
    tipo_documento = st.selectbox("Tipo de documento", TIPOS_DOCUMENTO, index=0)
    meses_alerta = st.number_input(
        "Alerta 'próximo a vencer' (meses)", min_value=1, max_value=24, value=MESES_ALERTA
    )
    st.markdown("**Vigencias:** Alturas = 1 año · Espacios = 3 años")

# --- Entrada de datos ---
st.subheader("1. Pega las celdas del Excel")
st.caption(f"Columnas esperadas (en orden): {', '.join(COLUMNAS_ENTRADA)}")

ejemplo = "1\t13747537\tJHONNY JESUS PEREZ BARRIONUEVO\tSUPERVISOR"
texto = st.text_area(
    "Datos pegados",
    height=200,
    placeholder=f"Ejemplo:\n{ejemplo}",
    label_visibility="collapsed",
)

procesar_click = st.button("Procesar", type="primary")

# --- Procesamiento ---
if procesar_click:
    if not texto.strip():
        st.warning("Pega primero los datos copiados del Excel.")
        st.stop()

    df_entrada = parsear_pegado(texto)
    if df_entrada.empty:
        st.warning("No se detectaron filas válidas en el texto pegado.")
        st.stop()

    st.info(f"Se detectaron {len(df_entrada)} cédula(s). Consultando...")

    barra = st.progress(0.0)
    estado = st.empty()

    def _avance(i: int, total: int) -> None:
        barra.progress(i / total)
        estado.write(f"Procesando {i} de {total}...")

    inicio = time.perf_counter()
    resultado = procesar(
        df_entrada,
        tipo_documento=tipo_documento,
        hoy=date.today(),
        meses_alerta=int(meses_alerta),
        progreso=_avance,
    )
    segundos = time.perf_counter() - inicio

    barra.empty()
    estado.empty()

    # Guardar en sesion para no perderlo al reordenar/descargar.
    st.session_state["resultado"] = resultado
    st.session_state["segundos"] = segundos

# --- Resultados ---
if "resultado" in st.session_state:
    resultado = st.session_state["resultado"]
    segundos = st.session_state["segundos"]
    total = len(resultado)

    st.subheader("2. Resultado")

    # Estado interno (para colorear) separado de las columnas visibles.
    estados = resultado["_estado"] if "_estado" in resultado else pd.Series("", index=resultado.index)
    df_vis = resultado.drop(columns=["_estado"], errors="ignore")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cédulas", total)
    c2.metric("Tiempo total", f"{segundos:.1f} s")
    c3.metric("Promedio x cédula", f"{segundos / total:.2f} s" if total else "—")
    n_vencidos = int((estados == "VENCIDO").sum())
    n_proximos = int((estados == "PROXIMO").sum())
    c4.metric("Vencidos / próximos", f"{n_vencidos} / {n_proximos}")

    st.caption("🔴 Rojo: certificado vencido · 🟡 Amarillo: próximo a vencer")

    # Colorea la fila completa segun el estado.
    COLORES = {
        "VENCIDO": "background-color: #f8d7da",   # rojo claro
        "PROXIMO": "background-color: #fff3cd",   # amarillo claro
        "ERROR": "background-color: #e2e3e5",     # gris
    }

    def _color_fila(fila):
        estilo = COLORES.get(estados.loc[fila.name], "")
        return [estilo] * len(fila)

    estilo = df_vis.style.apply(_color_fila, axis=1)

    st.dataframe(estilo, use_container_width=True, hide_index=True)

    # --- Copiar / descargar ---
    st.subheader("3. Copiar de vuelta al Excel")

    solo_nuevas = st.checkbox("Mostrar solo las columnas nuevas", value=True)
    cols = COLUMNAS_SALIDA if solo_nuevas else list(df_vis.columns)
    cols = [c for c in cols if c in df_vis.columns]
    tsv = df_vis[cols].to_csv(sep="\t", index=False)

    st.caption("Selecciona el texto y cópialo (Ctrl+C), luego pégalo en el Excel:")
    st.text_area("TSV para pegar", tsv, height=200)

    st.download_button(
        "Descargar Excel (con colores)",
        data=_to_excel(estilo),
        file_name="certificados_resultado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
