# Extrae datos del PDF de Buena Pro: RUC ganador, monto ofertado,
# total postores y plazo de ejecucion. Sin IA, solo regex sobre texto.

import os, re, zipfile, shutil
from collections import Counter

try:
    import pdfplumber
except ImportError:
    pdfplumber = None
    print("WARN: instala pdfplumber -> pip install pdfplumber")


# ── Patrones regex ─────────────────────────────────────────────────────────

# RUC peruano: 11 digitos, empieza con 10 o 20
_RE_RUC = re.compile(r"\b((?:10|20)\d{9})\b")

# Palabras que indican que la linea habla del ganador
_CTX_GANADOR = ["ganador", "buena pro", "adjudicado", "postor ganador",
                "postor seleccionado", "proveedor ganador"]

# Monto ofertado / adjudicado del ganador
_RE_MONTO = re.compile(
    r"(?:monto|precio)\s+(?:ofertado|adjudicado|contratado)[^0-9]{0,20}([\d,\.]+)",
    re.IGNORECASE,
)

# Total de postores que presentaron propuesta
_RE_POSTORES = re.compile(
    r"(?:total\s+de\s+postores|n[°º]\s*de\s+postores|n[uú]mero\s+de\s+postores"
    r"|postores\s+(?:que\s+)?(?:present|valid|habili))[^0-9]{0,30}(\d+)",
    re.IGNORECASE,
)

# Plazo de ejecucion en dias
_RE_PLAZO = re.compile(
    r"plazo\s+de\s+ejecuci[oó]n[^0-9]{0,30}(\d+)\s*d[ií]a",
    re.IGNORECASE,
)


# ── Extraccion de texto ────────────────────────────────────────────────────

def _leer_pdf(pdf_path: str) -> str:
    if not pdfplumber:
        return ""
    try:
        partes = []
        with pdfplumber.open(pdf_path) as pdf:
            for p in pdf.pages:
                partes.append(p.extract_text() or "")
        return "\n".join(partes)
    except Exception as e:
        print(f"    WARN leer_pdf: {e}")
        return ""


# ── Extraccion de campos ───────────────────────────────────────────────────

def _extraer_ruc(texto: str) -> str:
    # Busca RUC en lineas con contexto de ganador; fallback: RUC mas frecuente
    lineas = texto.splitlines()
    for idx, linea in enumerate(lineas):
        ll = linea.lower()
        ventana = " ".join(lineas[max(0, idx-3):idx+4]).lower()
        if any(p in ll or p in ventana for p in _CTX_GANADOR):
            m = _RE_RUC.search(linea)
            if m:
                return m.group(1)
    # fallback
    todos = _RE_RUC.findall(texto)
    return Counter(todos).most_common(1)[0][0] if todos else ""


def _extraer_monto(texto: str) -> str:
    m = _RE_MONTO.search(texto)
    return m.group(1).strip() if m else ""


def _extraer_postores(texto: str) -> str:
    m = _RE_POSTORES.search(texto)
    return m.group(1).strip() if m else ""


def _extraer_plazo(texto: str) -> str:
    m = _RE_PLAZO.search(texto)
    return m.group(1).strip() if m else ""


# ── Funcion principal ──────────────────────────────────────────────────────

def procesar_zip_buena_pro(zip_path: str, nomenclatura: str, descargas_path: str) -> dict:
    # Extrae PDFs del ZIP, lee el Reporte y saca los campos clave
    resultado = {
        "pdf_folder": "", "pdf_count": 0,
        "ruc_ganador": "", "fuente_ruc": "no_encontrado",
        "monto_ofertado_ganador": "", "total_postores": "", "plazo_ejecucion_dias": "",
    }

    if not zip_path or not os.path.exists(zip_path):
        return resultado

    # Carpeta destino por nomenclatura
    safe = nomenclatura.replace("/", "_").replace(":", "_")
    carpeta = os.path.join(descargas_path, "pdfs", safe)
    os.makedirs(carpeta, exist_ok=True)

    # Extraer solo PDFs del ZIP
    pdfs = []
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for m in z.namelist():
                if m.lower().endswith(".pdf"):
                    dest = os.path.join(carpeta, os.path.basename(m))
                    with z.open(m) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    pdfs.append(dest)
                    print(f"    PDF: {os.path.basename(dest)}")
    except Exception as e:
        print(f"    ERROR descomprimiendo ZIP: {e}")
        return resultado

    # Borrar ZIP
    try:
        os.remove(zip_path)
    except Exception:
        pass

    # Quedarse solo con el Reporte (nombre empieza con "1" o contiene "reporte")
    reporte = None
    for p in pdfs:
        nb = os.path.basename(p).lower()
        if nb.startswith("1") or "reporte" in nb:
            reporte = p
        else:
            try:
                os.remove(p)
            except Exception:
                pass

    if reporte is None and pdfs:
        reporte = pdfs[0]  # fallback: usar el primero disponible

    resultado["pdf_folder"] = carpeta
    resultado["pdf_count"]  = 1 if reporte else 0

    if not reporte:
        print("    No se encontro PDF de Reporte")
        return resultado

    # Leer texto del PDF
    texto = _leer_pdf(reporte)
    if not texto.strip():
        print("    WARN: PDF sin texto extraible (¿escaneado?)")
        return resultado

    # Extraer campos
    ruc    = _extraer_ruc(texto)
    monto  = _extraer_monto(texto)
    post   = _extraer_postores(texto)
    plazo  = _extraer_plazo(texto)

    resultado.update({
        "ruc_ganador":          ruc,
        "fuente_ruc":           "regex" if ruc else "no_encontrado",
        "monto_ofertado_ganador": monto,
        "total_postores":       post,
        "plazo_ejecucion_dias": plazo,
    })
    print(f"    RUC: {ruc} | Monto: {monto} | Postores: {post} | Plazo: {plazo}d")
    return resultado


def limpiar_carpeta_pdf(pdf_folder: str) -> None:
    # Borra la carpeta de PDFs una vez guardado el JSON
    if pdf_folder and os.path.exists(pdf_folder):
        try:
            shutil.rmtree(pdf_folder)
            print(f"    Carpeta PDF eliminada: {os.path.basename(pdf_folder)}")
        except Exception as e:
            print(f"    WARN eliminar carpeta: {e}")
