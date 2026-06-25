# Consulta de vigencia de certificados

Aplicación en **Streamlit** que automatiza la revisión de certificados de
**Trabajo en Alturas** y **Espacios Confinados** en el servicio público de
Centros de Entrenamiento del Ministerio de Trabajo.

En lugar de buscar cédula por cédula a mano, pegas las celdas copiadas del
Excel y el programa consulta cada cédula, evalúa la vigencia y devuelve las
columnas listas para copiar de vuelta.

## Reglas de vigencia

- **Alturas:** vigencia de **1 año** desde la última `FECHA FIN`.
- **Espacios confinados:** vigencia de **3 años** desde la última `FECHA FIN`.
- **Próximo a vencer:** si vence dentro de los próximos **3 meses** (configurable).

## Columnas

**Entrada** (pegas del Excel, en orden):

```
ITEM | CEDULA | NOMBRE | CARGO
```

**Salida** (genera el programa):

| Columna | Significado |
|---|---|
| `SI/NO` | `SI` si ningún certificado está vencido; `NO` si hay alguno vencido o no tiene certificados |
| `TIPO` | Qué tiene vigente/registrado: `ALT`, `ESC`, `ALT-ESC` o `NINGUNO` |
| `FECHA FIN VIGENCIA` | Fecha de vencimiento por tipo (p. ej. `ALT 18/04/2027 \| ESC 16/11/2028`) |
| `OBSERVACIONES` | `VIGENTES`, o el detalle de lo vencido / próximo a vencer |

## Instalación

```bash
pip install -r requirements.txt
```

## Ejecución (local)

```bash
streamlit run app.py
```

Se abre en el navegador (por defecto http://localhost:8501).

## Estructura

```
certificados-web/
├── app.py                  # Interfaz Streamlit
├── certificados/           # Lógica (paquete)
│   ├── config.py           # Constantes y reglas de negocio
│   ├── consulta.py         # Consulta al Ministerio (scraping ASP.NET)
│   ├── parsing.py          # Limpieza y extracción de tablas HTML
│   ├── vigencia.py         # Cálculo de vigencia y estados
│   └── procesamiento.py    # Pegado -> proceso masivo -> tabla de salida
├── requirements.txt
└── README.md
```

## Notas

- Las consultas usan `verify=False` porque el sitio del Estado a veces presenta
  problemas en la cadena de certificados TLS.
- El servicio del Ministerio no tiene captcha, pero conviene no abusar: las
  consultas se hacen una por una.
