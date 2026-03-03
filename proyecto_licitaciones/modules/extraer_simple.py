# Extractor de Buenas Pro del SEACE
# Flujo: pagina 1 -> ultima, fila a fila
# Guarda en JSON tras cada fila; salta nomenclaturas ya confirmadas con BP

import os, json, re, sys
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, Download

# Modulo de procesamiento de PDFs (extrae RUC / razon social)
_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # proyecto_licitaciones/
if _base not in sys.path:
    sys.path.insert(0, _base)
from modules.pdf_processor import procesar_zip_buena_pro, limpiar_carpeta_pdf

# ── Configuracion ──────────────────────────────────────────────────────────
URL          = ("https://prod2.seace.gob.pe/seacebus-uiwd-pub/"
                "buscadorPublico/buscadorPublico.xhtml")
FECHA_INICIO = "01/01/2026"

# Selectores fijos confirmados con codegen
SEL_FICHA    = "[id$=':grafichaSel']"
SEL_REGRESAR = "tbFicha:j_idt22"   # name= del boton Regresar
SEL_PAG      = "[id*='dtProcesos_paginator'] .ui-paginator-current"
SEL_PREV     = "[id*='dtProcesos_paginator'] .ui-paginator-prev"
SEL_NEXT     = "[id*='dtProcesos_paginator'] .ui-paginator-next"
SEL_LAST     = "[id*='dtProcesos_paginator'] .ui-paginator-last"
SEL_FIRST    = "[id*='dtProcesos_paginator'] .ui-paginator-first"


# ── Utilidades basicas ─────────────────────────────────────────────────────

def log(msg):
    print(msg)

def esperar(page, ms=1500):
    page.wait_for_timeout(ms)

def disabled(locator) -> bool:
    # Retorna True si el elemento tiene clase ui-state-disabled
    return "ui-state-disabled" in (locator.get_attribute("class") or "")


# ── Paginador ──────────────────────────────────────────────────────────────

def _texto_pag(page) -> str:
    # Lee el span del paginador de resultados
    try:
        return page.locator(SEL_PAG).first.inner_text(timeout=3000)
    except Exception:
        return ""

def pagina_actual(page) -> int:
    m = re.search(r"(\d+)\s*/\s*\d+", _texto_pag(page))
    return int(m.group(1)) if m else 0

def ir_a_pagina(page, objetivo: int):
    # Navega a la pagina objetivo usando clic directo o First+Next
    if objetivo <= 0 or pagina_actual(page) == objetivo:
        return
    log(f"    [nav] -> pag {objetivo}")

    # Intento 1: clic directo en el numero visible
    try:
        sp = page.locator(
            "[id*='dtProcesos_paginator'] .ui-paginator-page"
        ).filter(has_text=re.compile(rf"^{objetivo}$"))
        if sp.count() > 0 and sp.first.is_visible(timeout=2000):
            sp.first.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            esperar(page, 1200)
            if pagina_actual(page) == objetivo:
                return
    except Exception:
        pass

    # Intento 2: ir a pag 1 y avanzar con Next hasta llegar
    try:
        btn = page.locator(SEL_FIRST).first
        if not disabled(btn):
            btn.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            esperar(page, 800)
    except Exception:
        pass

    for _ in range(400):
        if pagina_actual(page) >= objetivo:
            break
        try:
            btn = page.locator(SEL_NEXT).first
            if disabled(btn):
                break
            btn.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            esperar(page, 700)
        except Exception:
            break

    log(f"    [nav] llegue a pag {pagina_actual(page)}")


# ── JSON persistente ───────────────────────────────────────────────────────

def guardar(registro: dict, json_path: str):
    # Agrega o actualiza el registro en el JSON; guarda inmediatamente
    data = []
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    idx = next((i for i, r in enumerate(data)
                if r.get("Nomenclatura") == registro.get("Nomenclatura")), None)
    if idx is not None:
        data[idx] = registro
    else:
        data.append(registro)
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def actualizar_n(nomenclatura: str, nuevo_n: str, json_path: str):
    # Solo actualiza el campo N de un registro existente (el numero se desplaza en SEACE)
    if not os.path.exists(json_path):
        return
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        idx = next((i for i, r in enumerate(data)
                    if r.get("Nomenclatura") == nomenclatura), None)
        if idx is not None and data[idx].get("N") != nuevo_n:
            data[idx]["N"] = nuevo_n
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"    WARN actualizar_n: {e}")


# ── Seleccion de Obra en dropdown ─────────────────────────────────────────

def seleccionar_obra(page) -> bool:
    log("[3] Seleccionando Obra...")
    page.locator("[id='tbBuscador:idFormBuscarProceso']").wait_for(
        state="visible", timeout=15000
    )
    esperar(page, 1000)

    def _click_obra(did: str) -> bool:
        # Abre el dropdown did y elige la opcion Obra
        css = did.replace(":", "\\:")
        t = page.locator(f"#{css} .ui-selectonemenu-trigger")
        if t.count() == 0 or not t.first.is_visible(timeout=3000):
            return False
        t.first.click()
        esperar(page, 700)
        op = page.locator(f"[id='{did}_panel'] li[data-label='Obra']")
        if op.count() == 0:
            return False
        op.first.click()
        esperar(page, 900)
        return True

    # ID conocido; si cambia se busca dinamicamente
    if _click_obra("tbBuscador:idFormBuscarProceso:j_idt192"):
        return True

    log("    j_idt192 no funciono, buscando dinamicamente...")
    for el in page.locator(
        "[id='tbBuscador:idFormBuscarProceso'] .ui-selectonemenu"
    ).all():
        if el.locator("select option[value='64']").count() > 0:
            did = el.get_attribute("id") or ""
            if did and _click_obra(did):
                return True

    log("  ERROR: dropdown Obra no encontrado")
    return False


# ── Lectura de cronograma ──────────────────────────────────────────────────

def buena_pro_vigente(page, hoy: datetime) -> tuple:
    # Revisa cronograma de la ficha; retorna (tiene_bp, fecha_str | None)
    try:
        filas = page.locator("[id='tbFicha:dtCronograma_data'] tr").filter(
            has_text="Otorgamiento de la Buena Pro"
        )
        if filas.count() == 0:
            return False, None
        texto = filas.first.locator("td").nth(2).inner_text(timeout=5000).strip()
        m = re.search(r"\d{2}/\d{2}/\d{4}", texto)
        if not m:
            return False, None
        dt = datetime.strptime(m.group(), "%d/%m/%Y")
        ok = dt <= hoy
        log(f"    BP fecha: {m.group()} {'<= hoy OK' if ok else '(futura)'}")
        return ok, m.group()
    except Exception as e:
        log(f"    ERROR cronograma: {e}")
        return False, None


# ── Descarga del ZIP ───────────────────────────────────────────────────────

def descargar_zip(page, descargas_path: str, nomenclatura: str) -> str | None:
    try:
        # Mostrar 10 filas en documentos para asegurar que aparece la fila BP
        combo = page.locator(
            "[id='tbFicha:dtDocumentos_paginator_bottom'] select.ui-paginator-rpp-options"
        )
        if combo.count() > 0:
            combo.select_option("10")
            page.wait_for_load_state("networkidle", timeout=15000)
            esperar(page, 900)

        fila = page.locator("[id='tbFicha:dtDocumentos_data'] tr").filter(
            has_text="Otorgamiento de la Buena Pro"
        ).last
        link = fila.locator("a").filter(has_text=re.compile(r"\(\d+\s*KB\)"))
        if link.count() == 0:
            log("    Sin link (N KB) en fila BP")
            return None

        with page.expect_download(timeout=90000) as dl:
            link.last.click()
        d: Download = dl.value
        fname = d.suggested_filename or f"{nomenclatura.replace('/','_')}.zip"
        ruta = os.path.join(descargas_path, fname)
        d.save_as(ruta)
        log(f"    ZIP: {fname} ({os.path.getsize(ruta)//1024} KB)")
        page.wait_for_timeout(5000)
        return ruta
    except Exception as e:
        log(f"    ERROR descarga: {e}")
        return None


# ── Regresar a lista ───────────────────────────────────────────────────────

def regresar(page):
    try:
        btn = page.locator(f"button[name='{SEL_REGRESAR}']")
        if btn.count() > 0:
            btn.first.click()
        else:
            page.get_by_role("button", name="Regresar").first.click()
        page.wait_for_load_state("networkidle", timeout=30000)
        esperar(page, 1200)
    except Exception as e:
        log(f"    WARN regresar: {e}")


# ── Procesamiento de una pagina ────────────────────────────────────────────

def procesar_pagina(page, hoy, descargas, results, pagina,
                    ya_con_bp, skip_por_fecha, json_path):
    total = page.locator(SEL_FICHA).count()
    log(f"\n[PAG {pagina}] {total} botones de ficha")
    if total == 0:
        return

    for i in range(total):
        # Leer celdas de la fila antes de abrir ficha
        try:
            btn    = page.locator(SEL_FICHA).nth(i)
            fila   = btn.locator("xpath=ancestor::tr[1]")
            celdas = fila.locator("td")
            n = celdas.count()
            if n < 5:   # omitir filas de pie/cabecera sin datos reales
                continue
            num          = celdas.nth(0).inner_text(timeout=5000).strip()
            entidad      = celdas.nth(1).inner_text(timeout=5000).strip()
            fecha_pub    = celdas.nth(2).inner_text(timeout=5000).strip()
            nomenclatura = celdas.nth(3).inner_text(timeout=5000).strip()
            objeto       = celdas.nth(5).inner_text(timeout=5000).strip() if n > 5  else ""
            descripcion  = celdas.nth(6).inner_text(timeout=5000).strip() if n > 6  else ""
            monto        = celdas.nth(9).inner_text(timeout=5000).strip() if n > 9  else ""
            moneda       = celdas.nth(10).inner_text(timeout=5000).strip() if n > 10 else ""
            # Departamento del codigo nomenclatura: AS-SM-1-2026 -> "SM"
            dm = re.match(r"[A-Z]{2}-([A-Z]{2})-", nomenclatura)
            departamento = dm.group(1) if dm else ""
        except Exception as e:
            log(f"  [{i+1}] ERROR leyendo fila: {e}")
            continue

        log(f"\n  [{i+1}/{total}] {nomenclatura} | {entidad[:50]}")

        # SKIP PERMANENTE: ya tiene BP confirmada
        if nomenclatura in ya_con_bp:
            # El numero N se desplaza cuando hay nuevas licitaciones -> actualizar
            actualizar_n(nomenclatura, num, json_path)
            log("    SKIP permanente (BP ya confirmada)")
            continue

        # SKIP TEMPORAL: la fecha de BP aun no llego
        if nomenclatura in skip_por_fecha:
            actualizar_n(nomenclatura, num, json_path)
            log("    SKIP temporal (fecha BP futura, aun no toca)")
            continue

        # Abrir ficha del proceso
        try:
            page.locator(SEL_FICHA).nth(i).click(timeout=30000)
            page.wait_for_load_state("networkidle", timeout=60000)
            esperar(page, 2000)
        except Exception as e:
            log(f"    ERROR abriendo ficha: {e}")
            continue

        tiene_bp = False
        fecha_bp = pdf_folder = None
        pdf_count = 0
        ruc = fuente = monto_ofertado = total_postores = plazo_dias = ""

        try:
            _, fecha_bp = buena_pro_vigente(page, hoy)  # solo obtener fecha, no usar bool
            if fecha_bp:  # si existe fila BP en cronograma, intentar descargar
                zip_path = descargar_zip(page, descargas, nomenclatura)
                if zip_path:
                    info           = procesar_zip_buena_pro(zip_path, nomenclatura, descargas)
                    pdf_folder     = info.get("pdf_folder")
                    pdf_count      = info.get("pdf_count", 0)
                    ruc            = info.get("ruc_ganador", "")
                    fuente         = info.get("fuente_ruc", "")
                    monto_ofertado = info.get("monto_ofertado_ganador", "")
                    total_postores = info.get("total_postores", "")
                    plazo_dias     = info.get("plazo_ejecucion_dias", "")
            # tiene_bp = True solo si se descargo ZIP y se extrajo RUC
            tiene_bp = bool(ruc)
        finally:
            # JSF resetea la tabla a pag 1 tras Regresar -> volver a pagina actual
            regresar(page)
            ir_a_pagina(page, pagina)

        reg = {
            "N": num,
            "Entidad": entidad,
            "departamento_entidad": departamento,
            "Fecha_Publicacion": fecha_pub,
            "Nomenclatura": nomenclatura,
            "Objeto": objeto,
            "Descripcion": descripcion,
            "Monto": monto,
            "Moneda": moneda,
            "tiene_buena_pro": tiene_bp,
            "fecha_buena_pro": fecha_bp,
            "ruc_ganador": ruc,
            "razon_social_ganador": "",     # lo llenara osce_scraper
            "fuente_ruc": fuente,
            "monto_ofertado_ganador": monto_ofertado,
            "total_postores": total_postores,
            "plazo_ejecucion_dias": plazo_dias,
            # Campos que llenara osce_scraper (SUNAT)
            "telefono": "",
            "email": "",
            "domicilio": "",
            "estado": "",
            "condicion": "",
            "tipo_contribuyente": "",
            "pdf_folder": str(pdf_folder) if pdf_folder else "",
            "pdf_count": pdf_count,
            "procesado_en": datetime.now().isoformat(timespec="seconds"),
        }
        results.append(reg)
        if tiene_bp:
            ya_con_bp.add(nomenclatura)
            skip_por_fecha.discard(nomenclatura)  # ya no es skip temporal
        guardar(reg, json_path)
        log(f"    Guardado: {nomenclatura}")

        # Limpiar PDFs del disco ahora que el JSON esta guardado
        if tiene_bp and pdf_folder:
            limpiar_carpeta_pdf(pdf_folder)


# ── Funcion principal ──────────────────────────────────────────────────────

def extraer_buenas_pro() -> list:
    hoy       = datetime.now()
    base      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # proyecto_licitaciones/
    descargas = os.path.join(base, "data", "descargas_temporales")
    json_path = os.path.join(base, "data", "adjudicaciones_procesadas.json")
    os.makedirs(descargas, exist_ok=True)

    # Cargar JSON existente y construir conjuntos de skip
    results = []
    ya_con_bp      = set()   # BP confirmada -> skip permanente
    skip_por_fecha = set()   # BP futura     -> skip temporal
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                results = json.load(f)
            for r in results:
                nom = r.get("Nomenclatura", "")
                if r.get("tiene_buena_pro") is True:
                    ya_con_bp.add(nom)
                elif r.get("fecha_buena_pro"):
                    # Skip temporal solo si la fecha BP aun no llego
                    try:
                        fecha_bp = datetime.strptime(r["fecha_buena_pro"], "%d/%m/%Y")
                        if fecha_bp > hoy:
                            skip_por_fecha.add(nom)
                    except Exception:
                        pass
            log(f"  JSON cargado: {len(results)} registros | "
                f"{len(ya_con_bp)} BP confirmadas (skip permanente) | "
                f"{len(skip_por_fecha)} con fecha futura (skip temporal)")
        except Exception as e:
            log(f"  WARN JSON: {e}")

    print("=" * 62)
    print("  EXTRACTOR BUENAS PRO - SEACE")
    print(f"  Ventana: {FECHA_INICIO} -> {hoy.strftime('%d/%m/%Y')}")
    print(f"  JSON  : {json_path}")
    print("=" * 62)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, slow_mo=300)
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            accept_downloads=True,
        )
        page = ctx.new_page()
        try:
            # 1. Navegar al portal SEACE
            page.goto(URL, timeout=90000)
            page.wait_for_load_state("networkidle", timeout=60000)
            esperar(page, 2000)

            # 2. Abrir buscador de procedimientos
            page.get_by_role("link", name="Buscador de Procedimientos de").click()
            page.wait_for_load_state("networkidle", timeout=60000)
            esperar(page, 3000)

            # 3. Elegir tipo Obra
            if not seleccionar_obra(page):
                log("ABORT: no se pudo seleccionar Obra")
                return results

            # 4. Busqueda avanzada + rango de fechas
            page.get_by_text("Búsqueda Avanzada").click()
            esperar(page, 1500)
            for fid, valor in [
                ("tbBuscador:idFormBuscarProceso:dfechaInicio_input", FECHA_INICIO),
                ("tbBuscador:idFormBuscarProceso:dfechaFin_input",    hoy.strftime("%d/%m/%Y")),
            ]:
                loc = page.locator(f"[id='{fid}']")
                loc.click()
                loc.click(click_count=3)
                loc.fill(valor)
                esperar(page, 500)

            # 5. Ejecutar busqueda
            page.get_by_role("button", name="Buscar").click()
            page.wait_for_load_state("networkidle", timeout=60000)
            esperar(page, 3000)

            # 6. Aumentar filas por pagina al maximo disponible
            try:
                combo = page.locator(
                    "[id*='dtProcesos_paginator'] select.ui-paginator-rpp-options"
                ).first
                vals = [
                    int(o.get_attribute("value"))
                    for o in combo.locator("option").all()
                    if (o.get_attribute("value") or "").isdigit()
                ]
                if vals:
                    mx = max(vals)
                    combo.select_option(str(mx))
                    page.wait_for_load_state("networkidle", timeout=30000)
                    esperar(page, 2000)
                    log(f"  Filas/pag: {mx}")
            except Exception as e:
                log(f"  WARN filas/pag: {e}")

            # 7. Recorrer todas las paginas de adelante hacia atras
            pagina = pagina_actual(page) or 1
            while True:
                procesar_pagina(
                    page, hoy, descargas, results, pagina,
                    ya_con_bp, skip_por_fecha, json_path
                )
                # Avanzar a la siguiente pagina
                try:
                    btn_next = page.locator(SEL_NEXT).first
                    if not btn_next.is_visible(timeout=3000) or disabled(btn_next):
                        log("\n  Fin: ultima pagina procesada.")
                        break
                    btn_next.click()
                    page.wait_for_load_state("networkidle", timeout=30000)
                    esperar(page, 2000)
                    pagina = pagina_actual(page)
                except Exception as e:
                    log(f"  WARN paginador: {e}")
                    break

        except Exception as e:
            log(f"\nERROR GENERAL: {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

    con_bp = sum(1 for r in results if r.get("tiene_buena_pro"))
    print("=" * 62)
    print(f"  TOTAL: {len(results)} registros | Con BP: {con_bp}")
    print("=" * 62)
    return results


if __name__ == "__main__":
    extraer_buenas_pro()
