"""
Extractor simple y directo de Buenas Pro del SEACE
Inspirado en el enfoque sync de Playwright
"""
import os
import zipfile
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

URL_SEACE = "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"


def extraer_buenas_pro() -> list:
    """
    Extrae buenas pro del SEACE de forma simple y directa.
    
    Returns:
        Lista de diccionarios con los datos extraídos
    """
    # Calcular fechas
    today = datetime.now()
    fecha_inicio = "01/01/2026"  # Desde inicio de año
    fecha_fin = today.strftime("%d/%m/%Y")
    
    results = []
    base_path = os.path.dirname(__file__)
    descargas_path = os.path.join(base_path, "data", "descargas_temporales")
    os.makedirs(descargas_path, exist_ok=True)
    
    print("="*70)
    print("EXTRACTOR SIMPLE DE BUENAS PRO - SEACE")
    print("="*70)
    print(f"Fecha: {fecha_fin}")
    print(f"Ventana: {fecha_inicio} a {fecha_fin}")
    print("-"*70)
    
    with sync_playwright() as playwright:
        # Lanzar navegador
        browser: Browser = playwright.chromium.launch(
            headless=False,
            slow_mo=500
        )
        context: BrowserContext = browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        page: Page = context.new_page()
        
        try:
            # 1. Navegar al SEACE
            print("\n[1] Navegando al SEACE...")
            page.goto(URL_SEACE, timeout=90000)
            page.wait_for_load_state('load')
            page.wait_for_timeout(3000)
            
            # 2. Entrar al buscador de procedimientos
            print("[2] Accediendo al buscador...")
            page.get_by_role("link", name="Buscador de Procedimientos de").click()
            page.wait_for_load_state('networkidle', timeout=60000)
            page.wait_for_timeout(5000)
            
            # 3. Seleccionar Tipo: Obra (con múltiples intentos)
            print("[3] Configurando Tipo: Obra...")
            
            # Intentar varios selectores posibles para el dropdown de Tipo
            tipo_selectors = [
                "#tbBuscador\\:idFormBuscarProceso\\:j_idt192_label",
                "#tbBuscador\\:idFormBuscarProceso\\:j_idt193_label",
                "#tbBuscador\\:idFormBuscarProceso\\:j_idt194_label",
                "label[id*='idFormBuscarProceso'][id$='_label']"
            ]
            
            tipo_clicked = False
            for selector in tipo_selectors:
                try:
                    tipo_label = page.locator(selector).first
                    if tipo_label.is_visible(timeout=5000):
                        tipo_label.click()
                        page.wait_for_timeout(1000)
                        tipo_clicked = True
                        print(f"    Clic en tipo con selector: {selector}")
                        break
                except:
                    continue
            
            if not tipo_clicked:
                print("    ERROR: No se pudo encontrar el dropdown de Tipo")
                return []
            
            # Seleccionar Obra del panel
            page.get_by_text("Obra", exact=True).first.click()
            page.wait_for_timeout(1000)
            
            # 4. Expandir Búsqueda Avanzada
            print("[4] Abriendo Búsqueda Avanzada...")
            page.get_by_text("Búsqueda Avanzada").click()
            page.wait_for_timeout(2000)
            
            # 5. Configurar fechas (buscar de forma flexible)
            print(f"[5] Configurando fechas: {fecha_inicio} - {fecha_fin}...")
            
            # Buscar campo de fecha inicio
            fecha_inicio_input = page.locator("input[id*='dfechaInicio_input']").first
            fecha_inicio_input.fill(fecha_inicio)
            page.wait_for_timeout(500)
            
            # Buscar campo de fecha fin
            fecha_fin_input = page.locator("input[id*='dfechaFin_input']").first
            fecha_fin_input.fill(fecha_fin)
            page.wait_for_timeout(1000)
            
            # 6. Buscar
            print("[6] Ejecutando búsqueda...")
            page.get_by_role("button", name="Buscar").click()
            page.wait_for_load_state('load')
            page.wait_for_timeout(5000)
            
            # 7. Procesar resultados página por página
            page_num = 1
            while True:
                print(f"\n[PÁGINA {page_num}] Procesando...")
                
                # Obtener filas de la tabla (selector más flexible)
                rows = page.locator("table[id*='dtProcesos'] tbody tr").first.locator("xpath=..").locator("tr")
                row_count = rows.count()
                
                if row_count == 0:
                    print("  No hay más resultados")
                    break
                
                print(f"  Encontradas {row_count} filas")
                
                for i in range(row_count):
                    try:
                        row = rows.nth(i)
                        cells = row.locator("td")
                        
                        if cells.count() < 12:
                            continue
                        
                        # Extraer datos básicos
                        nomenclatura = cells.nth(3).inner_text().strip()
                        print(f"  [{i+1}] {nomenclatura}")
                        
                        data = {
                            'N°': cells.nth(0).inner_text().strip(),
                            'Entidad': cells.nth(1).inner_text().strip(),
                            'Fecha Publicacion': cells.nth(2).inner_text().strip(),
                            'Nomenclatura': nomenclatura,
                            'Objeto': cells.nth(5).inner_text().strip(),
                            'Descripcion': cells.nth(6).inner_text().strip(),
                            'Monto': cells.nth(9).inner_text().strip(),
                            'Moneda': cells.nth(10).inner_text().strip(),
                            'fecha_buena_pro': None,
                            'zip_path': None,
                            'pdf_folder': None,
                            'pdf_count': 0
                        }
                        
                        # Click en Ver Ficha
                        ver_ficha = row.locator("a[id*='j_idt382'], a[id*='j_idt383']").first
                        ver_ficha.click(timeout=60000)
                        page.wait_for_load_state('networkidle', timeout=60000)
                        page.wait_for_timeout(2000)
                        
                        # PASO 1: Cambiar paginación a 15 elementos por página
                        print(f"      --> Cambiando paginación a 15 elementos...")
                        paginacion_select = page.locator("select.ui-paginator-rpp-options")
                        if paginacion_select.count() > 0:
                            paginacion_select.first.select_option("15")
                            page.wait_for_timeout(2000)  # Esperar a que recargue la tabla
                            print(f"      --> Paginación cambiada a 15")
                        
                        # PASO 2: Buscar en tabla de documentos (ahora con 15 elementos)
                        doc_rows = page.locator("table[id*='dtDocumentos'] tbody tr")
                        doc_count = doc_rows.count()
                        print(f"      Documentos encontrados: {doc_count}")
                        
                        # PASO 3: Buscar "Otorgamiento de la Buena Pro"
                        validado = False
                        for j in range(doc_count):
                            doc_row = doc_rows.nth(j)
                            doc_text = doc_row.inner_text()
                            
                            if "Otorgamiento de la Buena Pro" in doc_text:
                                print(f"      --> Encontrado: Otorgamiento de la Buena Pro")
                                cells_doc = doc_row.locator("td")
                                
                                # Extraer fecha (última columna típicamente)
                                if cells_doc.count() >= 4:
                                    fecha_text = cells_doc.nth(-1).inner_text().strip()  # Última columna
                                    if '/' in fecha_text:
                                        fecha_buena_pro = fecha_text.split()[0]
                                        data['fecha_buena_pro'] = fecha_buena_pro
                                        
                                        # Validar fecha <= hoy
                                        try:
                                            fecha_obj = datetime.strptime(fecha_buena_pro, "%d/%m/%Y")
                                            if fecha_obj <= today:
                                                validado = True
                                                print(f"      OK: Fecha {fecha_buena_pro} <= hoy")
                                            else:
                                                print(f"      SKIP: Fecha {fecha_buena_pro} es futura")
                                        except:
                                            print(f"      ERROR: No se pudo parsear fecha")
                                
                                # PASO 4: Descargar ZIP directamente desde esta fila
                                if validado:
                                    # Buscar el enlace con el onclick que contiene descargaDocGeneral
                                    download_links = doc_row.locator("a[onclick*='descargaDocGeneral']")
                                    if download_links.count() > 0:
                                        try:
                                            print(f"      --> Descargando ZIP...")
                                            with page.expect_download(timeout=90000) as download_info:
                                                download_links.first.click()
                                            
                                            download = download_info.value
                                            filename = download.suggested_filename
                                            
                                            if filename.lower().endswith('.zip'):
                                                filepath = os.path.join(descargas_path, filename)
                                                download.save_as(filepath)
                                                data['zip_path'] = filepath
                                                print(f"      OK: Descargado {filename}")
                                                
                                                # PASO 5: Descomprimir y extraer PDF
                                                try:
                                                    pdf_folder = os.path.join(descargas_path, "pdfs", nomenclatura.replace('/', '_'))
                                                    os.makedirs(pdf_folder, exist_ok=True)
                                                    
                                                    with zipfile.ZipFile(filepath, 'r') as zip_ref:
                                                        # Extraer solo PDFs
                                                        pdf_files = [f for f in zip_ref.namelist() if f.lower().endswith('.pdf')]
                                                        for pdf_file in pdf_files:
                                                            zip_ref.extract(pdf_file, pdf_folder)
                                                        
                                                        data['pdf_folder'] = pdf_folder
                                                        data['pdf_count'] = len(pdf_files)
                                                        print(f"      OK: Extraídos {len(pdf_files)} PDFs a {pdf_folder}")
                                                except Exception as e:
                                                    print(f"      ERROR al descomprimir: {e}")
                                        except Exception as e:
                                            print(f"      ERROR descarga: {e}")
                                break
                        
                        # Solo agregar si validó y descargó
                        if validado and data.get('zip_path'):
                            results.append(data)
                        
                        # Regresar a lista
                        back_btn = page.locator("button[name*='j_idt']").filter(has_text="Regresar").first
                        if back_btn.count() == 0:
                            back_btn = page.get_by_role("button", name="Regresar").first
                        
                        if back_btn.count() > 0:
                            back_btn.click()
                            page.wait_for_load_state('networkidle', timeout=60000)
                            page.wait_for_timeout(1000)
                    
                    except Exception as e:
                        print(f"  ERROR en fila {i}: {e}")
                        # Intentar regresar
                        try:
                            page.get_by_role("button", name="Regresar").first.click()
                            page.wait_for_timeout(1000)
                        except:
                            pass
                        continue
                
                # Verificar siguiente página
                try:
                    next_btn = page.locator("a.ui-paginator-next").first
                    if next_btn.is_visible():
                        btn_class = next_btn.get_attribute("class")
                        if "ui-state-disabled" not in btn_class:
                            print(f"[SIGUIENTE] Página {page_num + 1}...")
                            next_btn.click()
                            page.wait_for_load_state('networkidle')
                            page.wait_for_timeout(2000)
                            page_num += 1
                        else:
                            break
                    else:
                        break
                except:
                    break
        
        finally:
            browser.close()
    
    print("\n" + "="*70)
    print(f"COMPLETADO: {len(results)} procesos validados y descargados")
    print("="*70)
    
    return results


if __name__ == "__main__":
    import json
    
    resultados = extraer_buenas_pro()
    
    # Resumen
    print("\n" + "="*70)
    print("RESUMEN DE RESULTADOS")
    print("="*70)
    for i, r in enumerate(resultados, 1):
        print(f"\n{i}. {r['Nomenclatura']}")
        print(f"   Entidad: {r['Entidad']}")
        print(f"   Fecha BP: {r['fecha_buena_pro']}")
        print(f"   ZIP: {r['zip_path']}")
        print(f"   PDFs extraidos: {r['pdf_count']}")
        if r['pdf_folder']:
            print(f"   Carpeta: {r['pdf_folder']}")
    
    # Guardar JSON
    with open("data/adjudicaciones_procesadas.json", 'w', encoding='utf-8') as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    
    print(f"\nResultados guardados en: data/adjudicaciones_procesadas.json")
