import os
import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def extraer_buenas_pro_de_hoy():
    """
    Extrae buenas pro del SEACE usando ventana móvil de 30 días.
    
    Lógica estricta:
    1. Usa playwright-stealth para evadir WAF
    2. Busca con ventana móvil: Fecha Inicio = hace 30 días, Fecha Fin = hoy
    3. Por cada fila, hace clic en el ícono del ojo (Ver Ficha)
    4. Valida en la tabla de documentos: busca "Otorgamiento de la Buena Pro" y verifica que su fecha <= hoy
    5. Si pasa validación, navega a página 2 de documentos (si existe) y descarga el .zip
    6. Retorna lista de diccionarios con datos + ruta del .zip
    
    Returns:
        list: Lista de diccionarios con información validada y ruta del ZIP descargado.
    """
    base_path = os.path.dirname(os.path.dirname(__file__))
    descargas_path = os.path.join(base_path, "data", "descargas_temporales")
    os.makedirs(descargas_path, exist_ok=True)

    # Ventana móvil: 30 días atrás hasta hoy
    today = datetime.now()
    fecha_inicio_dt = today - timedelta(days=30)
    fecha_inicio = fecha_inicio_dt.strftime("%d/%m/%Y")
    fecha_fin = today.strftime("%d/%m/%Y")
    
    # Para validación: aceptar cualquier fecha <= hoy (que ya haya pasado)
    fecha_hoy_str = today.strftime("%d/%m/%Y")

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # Modo visible para depuración
            args=['--disable-blink-features=AutomationControlled'],
            slow_mo=500  # Ralentizar para visualización
        )
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        # Aplicar playwright-stealth para evitar detección WAF
        stealth_config = Stealth()
        await stealth_config.apply_stealth_async(page)

        try:
            print(f"[SEACE] Navegando al buscador...")
            await page.goto("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml", timeout=90000)
            await page.wait_for_load_state('load')
            await asyncio.sleep(3)
            
            print(f"[SEACE] Accediendo al buscador de procedimientos...")
            await page.get_by_role("link", name="Buscador de Procedimientos de").click()
            await page.wait_for_load_state('networkidle', timeout=60000)
            await asyncio.sleep(5)  # Esperar más tiempo a que cargue el formulario

            print(f"[SEACE] Configurando filtros (Ventana móvil: {fecha_inicio} a {fecha_fin})...")
            
            # Esperar a que el dropdown de Tipo esté visible
            tipo_label = page.locator("[id=\"tbBuscador:idFormBuscarProceso:j_idt192_label\"]")
            await tipo_label.wait_for(state='visible', timeout=30000)
            await asyncio.sleep(2)
            
            # Seleccionar Tipo: Obra
            print(f"  → Tipo: Obra")
            await tipo_label.click()
            await asyncio.sleep(1)
            await page.locator("[id=\"tbBuscador:idFormBuscarProceso:j_idt192_panel\"]").get_by_text("Obra", exact=True).click()
            await asyncio.sleep(1)
            print(f"  ✓ Tipo: Obra")
            
            # Expandir "Búsqueda Avanzada" para acceder a las fechas
            print(f"  → Abriendo Búsqueda Avanzada")
            await page.get_by_text("Búsqueda Avanzada").click()
            await asyncio.sleep(2)

            # Configurar Fecha Inicio
            print(f"  → Fecha inicio: {fecha_inicio}")
            await page.locator("[id=\"tbBuscador:idFormBuscarProceso:dfechaInicio_input\"]").click()
            await page.locator("[id=\"tbBuscador:idFormBuscarProceso:dfechaInicio_input\"]").fill(fecha_inicio)
            await asyncio.sleep(0.5)
            
            # Configurar Fecha Fin
            print(f"  → Fecha fin: {fecha_fin}")
            await page.locator("[id=\"tbBuscador:idFormBuscarProceso:dfechaFin_input\"]").click()
            await page.locator("[id=\"tbBuscador:idFormBuscarProceso:dfechaFin_input\"]").fill(fecha_fin)
            await asyncio.sleep(1)
            print(f"  ✓ Fechas configuradas")

            # Buscar
            print(f"\n[SEACE] Ejecutando búsqueda...")
            await page.get_by_role("button", name="Buscar").click()
            await page.wait_for_load_state('load')
            await asyncio.sleep(5)  # Esperar más tiempo para que carguen los resultados

            # Procesar páginas de resultados
            page_number = 1
            while True:
                print(f"\n[PÁGINA {page_number}] Procesando resultados...")
                
                rows = page.locator("[id=\"tbBuscador:idFormBuscarProceso:dtProcesos\"] tbody tr")
                row_count = await rows.count()

                if row_count == 0:
                    print("  ⚠ No se encontraron resultados.")
                    break

                for i in range(row_count):
                    try:
                        row = rows.nth(i)
                        cells = row.locator("td")
                        cell_count = await cells.count()

                        if cell_count < 12:
                            continue

                        # Extraer datos básicos de la tabla
                        nomenclatura = (await cells.nth(3).inner_text()).strip()
                        print(f"  [{i+1}/{row_count}] Procesando: {nomenclatura}")

                        data = {
                            'N°': (await cells.nth(0).inner_text()).strip(),
                            'Nombre o Sigla de la Entidad': (await cells.nth(1).inner_text()).strip(),
                            'Fecha y Hora de Publicacion': (await cells.nth(2).inner_text()).strip(),
                            'Nomenclatura': nomenclatura,
                            'Reiniciado Desde': (await cells.nth(4).inner_text()).strip(),
                            'Objeto de Contratación': (await cells.nth(5).inner_text()).strip(),
                            'Descripción de Objeto': (await cells.nth(6).inner_text()).strip(),
                            'Código SNIP': (await cells.nth(7).inner_text()).strip(),
                            'Código Unico de Inversion': (await cells.nth(8).inner_text()).strip(),
                            'VR / VE / Cuantía de la contratación': (await cells.nth(9).inner_text()).strip(),
                            'Moneda': (await cells.nth(10).inner_text()).strip(),
                            'Versión SEACE': (await cells.nth(11).inner_text()).strip(),
                            'estado_validado': None,
                            'fecha_buena_pro': None,
                            'zip_path': None
                        }

                        # Hacer clic en el ícono del ojo (Ver Ficha / Acciones)
                        ver_ficha_button = row.locator("a[id*='j_idt382'], a[id*='j_idt383'], a[title*='Ver']")
                        if await ver_ficha_button.count() > 0:
                            await ver_ficha_button.first.click(timeout=60000)
                            await page.wait_for_load_state('networkidle', timeout=60000)
                            await asyncio.sleep(2)

                            # VALIDACIÓN ESTRICTA: Buscar en tabla de Documentos por Etapa
                            validacion_exitosa = False
                            fecha_buena_pro = None
                            
                            print(f"      → Buscando etapa 'Otorgamiento de la Buena Pro'...")
                            
                            # Buscar tabla de documentos por etapa
                            doc_rows = page.locator("[id=\"tbFicha:dtDocumentos\"] tbody tr, [id*='dtDocumentos'] tbody tr")
                            doc_count = await doc_rows.count()
                            print(f"      → Filas de documentos encontradas: {doc_count}")
                            
                            if doc_count > 0:
                                for j in range(doc_count):
                                    try:
                                        doc_row = doc_rows.nth(j)
                                        doc_text = await doc_row.inner_text()
                                        
                                        # Buscar fila con "Otorgamiento de la Buena Pro" en columna "Etapa"
                                        if "Otorgamiento de la Buena Pro" in doc_text:
                                            print(f"      → Fila encontrada: {doc_text[:100]}...")
                                            cells = doc_row.locator("td")
                                            cell_count = await cells.count()
                                            print(f"      → Número de celdas: {cell_count}")
                                            
                                            # Imprimir contenido de todas las celdas para debug
                                            for k in range(min(cell_count, 6)):
                                                cell_content = await cells.nth(k).inner_text()
                                                print(f"        Celda {k}: {cell_content.strip()[:50]}")
                                            
                                            if cell_count >= 4:
                                                # Estructura: Nro | Etapa | Documento | Archivo | Fecha | Acciones
                                                # Extraer la fecha (columna ~4)
                                                fecha_cell_text = await cells.nth(4).inner_text()
                                                fecha_cell_text = fecha_cell_text.strip()
                                                print(f"      → Contenido de celda de fecha: '{fecha_cell_text}'")
                                                
                                                # Extraer fecha DD/MM/YYYY
                                                if '/' in fecha_cell_text:
                                                    fecha_parts = fecha_cell_text.split()
                                                    if fecha_parts:
                                                        fecha_buena_pro = fecha_parts[0]
                                                        print(f"      → Fecha Otorgamiento encontrada: {fecha_buena_pro}")
                                                        
                                                        # Validar que la fecha sea hoy o anterior (ya pasó)
                                                        try:
                                                            fecha_bp_obj = datetime.strptime(fecha_buena_pro, "%d/%m/%Y")
                                                            if fecha_bp_obj <= today:
                                                                validacion_exitosa = True
                                                                data['estado_validado'] = 'Adjudicado'
                                                                data['fecha_buena_pro'] = fecha_buena_pro
                                                                print(f"      ✓ VALIDACIÓN APROBADA: Fecha {fecha_buena_pro} <= hoy")
                                                            else:
                                                                print(f"      ✗ VALIDACIÓN RECHAZADA: Fecha {fecha_buena_pro} es futura")
                                                        except:
                                                            print(f"      ✗ Error al parsear fecha: {fecha_buena_pro}")
                                                        break
                                    except Exception as e:
                                        print(f"      Error al procesar fila documento {j}: {e}")
                                        continue
                            else:
                                print(f"      ⚠ No se encontró tabla de documentos")

                            # Solo descargar si pasa la validación
                            if validacion_exitosa:
                                print(f"      → Buscando documento para descarga...")
                                
                                # Verificar si hay paginación en la tabla de documentos
                                paginator = page.locator("[id=\"tbFicha:dtDocumentos_paginator_bottom\"]")
                                if await paginator.count() > 0:
                                    # Verificar si hay una página 2
                                    page_2_button = paginator.locator("a:has-text('2'), span:has-text('2')")
                                    if await page_2_button.count() > 0:
                                        print(f"      → Navegando a página 2 de documentos...")
                                        await page_2_button.first.click()
                                        await asyncio.sleep(2)
                                
                                # Buscar el documento de Otorgamiento en la página actual
                                doc_table = page.locator("[id=\"tbFicha:dtDocumentos\"] tbody tr, [id*='dtDocumentos'] tbody tr")
                                doc_count = await doc_table.count()
                                
                                download_found = False
                                for j in range(doc_count):
                                    try:
                                        doc_row = doc_table.nth(j)
                                        doc_text = await doc_row.inner_text()
                                        
                                        # Buscar "Documentos de Otorgamiento" o el archivo .zip
                                        if "Otorgamiento" in doc_text or "Buena Pro" in doc_text:
                                            # Buscar enlace de descarga (puede ser icono PDF o ZIP)
                                            download_link = doc_row.locator("a[href*='SdescargarArchivoAlfresco?fileCode=']")
                                            
                                            if await download_link.count() > 0:
                                                # Buscar específicamente el .zip (normalmente tiene más KB)
                                                link_text = await download_link.first.inner_text()
                                                
                                                # Intentar descargar
                                                try:
                                                    async with page.expect_download(timeout=90000) as download_info:
                                                        await download_link.first.click(timeout=30000)
                                                    
                                                    download = await download_info.value
                                                    zip_filename = download.suggested_filename
                                                    
                                                    # Solo guardar si es .zip
                                                    if zip_filename.lower().endswith('.zip'):
                                                        zip_path = os.path.join(descargas_path, zip_filename)
                                                        await download.save_as(zip_path)
                                                        data['zip_path'] = zip_path
                                                        print(f"      ✓ Descargado: {zip_filename}")
                                                        download_found = True
                                                        break
                                                    else:
                                                        print(f"      ⚠ Archivo no es .zip: {zip_filename}")
                                                except Exception as e:
                                                    print(f"      Error al descargar: {e}")
                                    except Exception as e:
                                        print(f"      Error al procesar documento {j}: {e}")
                                        continue
                                
                                if not download_found:
                                    print(f"      ⚠ No se encontró archivo .zip para descargar")
                            else:
                                print(f"      ✗ Descarga omitida: No pasó validación de fecha")

                            # Regresar a la lista
                            back_button = page.locator("button[name=\"tbFicha:j_idt22\"], button:has-text('Regresar')")
                            if await back_button.count() > 0:
                                await back_button.first.click(timeout=60000)
                                await page.wait_for_load_state('networkidle', timeout=60000)
                                await asyncio.sleep(1)

                        # Solo agregar a resultados si pasó la validación
                        if data['estado_validado'] == 'Adjudicado' and data['fecha_buena_pro']:
                            results.append(data)
                            print(f"      ✓ Agregado a resultados")
                        else:
                            print(f"      ✗ No agregado: No cumple criterios de validación")

                    except Exception as e:
                        print(f"  ✗ Error al procesar fila {i}: {e}")
                        try:
                            back_button = page.locator("button[name=\"tbFicha:j_idt22\"], button:has-text('Regresar')")
                            if await back_button.is_visible(timeout=2000):
                                await back_button.first.click()
                                await page.wait_for_load_state('networkidle')
                        except:
                            pass
                        continue

                # Verificar paginación
                try:
                    next_button = page.locator("[id=\"tbBuscador:idFormBuscarProceso:dtProcesos_paginator_bottom\"] .ui-paginator-next")
                    if await next_button.is_visible():
                        button_class = await next_button.get_attribute("class")
                        if "ui-state-disabled" not in button_class:
                            print(f"[SEACE] Avanzando a página {page_number + 1}...")
                            await next_button.click()
                            await page.wait_for_load_state('networkidle')
                            await asyncio.sleep(2)
                            page_number += 1
                        else:
                            break
                    else:
                        break
                except Exception as e:
                    print(f"[SEACE] Fin de paginación: {e}")
                    break

        except Exception as e:
            print(f"\n[ERROR] Error general durante extracción: {e}")
            try:
                await page.screenshot(path=os.path.join(descargas_path, "error_screenshot.png"))
            except:
                pass
        finally:
            await context.close()
            await browser.close()

    print(f"\n[SEACE] ✓ Extracción completada")
    print(f"        Total procesados con validación exitosa: {len(results)}")
    return results


async def extraer_licitaciones_hoy():
    """
    Extrae licitaciones del SEACE que terminan hoy y tienen estado 'Adjudicado'.
    
    Returns:
        list: Lista de diccionarios con información de cada licitación y ruta del ZIP descargado.
    """
    base_path = os.path.dirname(os.path.dirname(__file__))
    descargas_path = os.path.join(base_path, "data", "descargas_temporales")
    os.makedirs(descargas_path, exist_ok=True)

    today = datetime.now().strftime("%d/%m/%Y")
    fecha_inicio = "01/01/2026"  # Aperturadas desde inicio de 2026

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # Modo visible para depuración
            slow_mo=500  # Ralentizar acciones para visualización
        )
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        # Aplicar playwright-stealth para evitar detección
        stealth_config = Stealth()
        await stealth_config.apply_stealth_async(page)

        try:
            print(f"Navegando al SEACE...")
            # Navegar al buscador
            await page.goto("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml", timeout=90000)
            await page.wait_for_load_state('load')
            await asyncio.sleep(3)
            
            # Tomar screenshot inicial
            await page.screenshot(path=os.path.join(descargas_path, "screenshot_inicial.png"))
            
            print(f"Accediendo al buscador de procedimientos...")
            # Buscar el enlace más flexiblemente
            link_buscador = page.locator("a:has-text('Buscador de Procedimientos de Selección')")
            await link_buscador.wait_for(state='visible', timeout=30000)
            await link_buscador.click()
            await page.wait_for_load_state('load')
            await asyncio.sleep(3)
            
            await page.screenshot(path=os.path.join(descargas_path, "screenshot_buscador.png"))

            print(f"Configurando filtros de búsqueda...")
            
            # Seleccionar tipo: Obra - usar selector más flexible
            print(f"  - Tipo: Obra")
            # Buscar el dropdown por label text o por el contenido
            tipo_dropdown = page.locator("label:has-text('Tipo')").locator("..").locator("div[role='button']")
            if await tipo_dropdown.count() == 0:
                # Intentar selector alternativo
                tipo_dropdown = page.locator("[id*='idFormBuscarProceso'][id$='_label']:has-text('TODOS')")
            
            await tipo_dropdown.wait_for(state='visible', timeout=30000)
            await tipo_dropdown.first.click()
            await asyncio.sleep(1)
            
            # Seleccionar "Obra" del panel
            obra_option = page.locator("li[data-label='Obra'], div[role='option']:has-text('Obra')").first
            await obra_option.wait_for(state='visible', timeout=10000)
            await obra_option.click()
            await asyncio.sleep(1)

            # Seleccionar estado: Adjudicado
            print(f"  - Estado: Adjudicado")
            estado_dropdown = page.locator("label:has-text('Estado')").locator("..").locator("div[role='button']")
            if await estado_dropdown.count() == 0:
                # Intentar con el segundo dropdown (el de estado)
                estado_dropdown = page.locator("[id*='idFormBuscarProceso'][id$='_label']").nth(1)
            
            await estado_dropdown.wait_for(state='visible', timeout=30000)
            await estado_dropdown.first.click()
            await asyncio.sleep(1)
            
            # Seleccionar "Adjudicado" del panel
            adjudicado_option = page.locator("li[data-label='Adjudicado'], div[role='option']:has-text('Adjudicado')").first
            await adjudicado_option.wait_for(state='visible', timeout=10000)
            await adjudicado_option.click()
            await asyncio.sleep(1)

            # Establecer fechas: desde 01/01/2026 hasta hoy
            print(f"  - Fecha inicio: {fecha_inicio}")
            fecha_inicio_input = page.locator("input[id*='dfechaInicio']")
            await fecha_inicio_input.wait_for(state='visible', timeout=30000)
            await fecha_inicio_input.fill(fecha_inicio)
            await asyncio.sleep(0.5)
            
            print(f"  - Fecha fin: {today}")
            fecha_fin_input = page.locator("input[id*='dfechaFin']")
            await fecha_fin_input.wait_for(state='visible', timeout=30000)
            await fecha_fin_input.fill(today)
            await asyncio.sleep(1)
            
            await page.screenshot(path=os.path.join(descargas_path, "screenshot_antes_buscar.png"))

            # Buscar
            print(f"\nIniciando búsqueda...")
            boton_buscar = page.locator("button:has-text('Buscar'), input[value='Buscar']")
            await boton_buscar.wait_for(state='visible', timeout=30000)
            await boton_buscar.first.click()
            await page.wait_for_load_state('load')
            await asyncio.sleep(3)
            
            await page.screenshot(path=os.path.join(descargas_path, "screenshot_resultados.png"))

            # Procesar páginas de resultados
            page_number = 1
            while True:
                print(f"Procesando página {page_number}...")
                
                # Extraer filas de la tabla
                rows = page.locator("[id=\"tbBuscador:idFormBuscarProceso:dtProcesos\"] tbody tr")
                row_count = await rows.count()

                if row_count == 0:
                    print("No se encontraron resultados.")
                    break

                for i in range(row_count):
                    try:
                        row = rows.nth(i)
                        cells = row.locator("td")
                        cell_count = await cells.count()

                        # Verificar que la fila tenga suficientes columnas
                        if cell_count < 12:
                            continue

                        # Extraer datos de la fila
                        data = {
                            'N°': (await cells.nth(0).inner_text()).strip(),
                            'Nombre o Sigla de la Entidad': (await cells.nth(1).inner_text()).strip(),
                            'Fecha y Hora de Publicacion': (await cells.nth(2).inner_text()).strip(),
                            'Nomenclatura': (await cells.nth(3).inner_text()).strip(),
                            'Reiniciado Desde': (await cells.nth(4).inner_text()).strip(),
                            'Objeto de Contratación': (await cells.nth(5).inner_text()).strip(),
                            'Descripción de Objeto': (await cells.nth(6).inner_text()).strip(),
                            'Código SNIP': (await cells.nth(7).inner_text()).strip(),
                            'Código Unico de Inversion': (await cells.nth(8).inner_text()).strip(),
                            'VR / VE / Cuantía de la contratación': (await cells.nth(9).inner_text()).strip(),
                            'Moneda': (await cells.nth(10).inner_text()).strip(),
                            'Versión SEACE': (await cells.nth(11).inner_text()).strip(),
                            'zip_path': None
                        }

                        print(f"  Procesando: {data['Nomenclatura']}")

                        # Hacer clic en 'Ver Ficha'
                        ver_ficha_button = row.locator("a[id*='j_idt383']")
                        if await ver_ficha_button.count() > 0:
                            await ver_ficha_button.click(timeout=60000)
                            await page.wait_for_load_state('networkidle', timeout=60000)
                            await asyncio.sleep(2)

                            # Buscar el documento de "Otorgamiento de la Buena Pro"
                            # Primero verificar si hay paginación en la tabla de documentos
                            doc_table = page.locator("[id=\"tbFicha:dtDocumentos\"] tbody tr")
                            doc_count = await doc_table.count()
                            
                            download_found = False
                            for j in range(doc_count):
                                try:
                                    doc_row = doc_table.nth(j)
                                    doc_text = await doc_row.inner_text()
                                    
                                    if "Otorgamiento de la Buena Pro" in doc_text:
                                        # Buscar enlace de descarga que apunte a Alfresco
                                        download_link = doc_row.locator("a[href*='SdescargarArchivoAlfresco?fileCode=']")
                                        
                                        if await download_link.count() > 0:
                                            async with page.expect_download(timeout=90000) as download_info:
                                                await download_link.first.click(timeout=30000)
                                            
                                            download = await download_info.value
                                            zip_filename = download.suggested_filename
                                            zip_path = os.path.join(descargas_path, zip_filename)
                                            await download.save_as(zip_path)
                                            data['zip_path'] = zip_path
                                            print(f"    ✓ Descargado: {zip_filename}")
                                            download_found = True
                                            break
                                except Exception as e:
                                    print(f"    Error al procesar documento {j}: {e}")
                                    continue
                            
                            if not download_found:
                                print(f"    ⚠ No se encontró documento de descarga")

                            # Regresar a la lista
                            back_button = page.locator("button[name=\"tbFicha:j_idt22\"]")
                            if await back_button.count() > 0:
                                await back_button.click(timeout=60000)
                                await page.wait_for_load_state('networkidle', timeout=60000)
                                await asyncio.sleep(1)

                        results.append(data)

                    except Exception as e:
                        print(f"  Error al procesar fila {i}: {e}")
                        # Intentar regresar si estamos en una ficha
                        try:
                            back_button = page.locator("button[name=\"tbFicha:j_idt22\"]")
                            if await back_button.is_visible(timeout=2000):
                                await back_button.click()
                                await page.wait_for_load_state('networkidle')
                        except:
                            pass
                        continue

                # Verificar si hay página siguiente
                try:
                    next_button = page.locator("[id=\"tbBuscador:idFormBuscarProceso:dtProcesos_paginator_bottom\"] .ui-paginator-next")
                    if await next_button.is_visible():
                        button_class = await next_button.get_attribute("class")
                        if "ui-state-disabled" not in button_class:
                            print(f"Avanzando a página {page_number + 1}...")
                            await next_button.click()
                            await page.wait_for_load_state('networkidle')
                            await asyncio.sleep(2)
                            page_number += 1
                        else:
                            print("No hay más páginas.")
                            break
                    else:
                        print("No hay más páginas.")
                        break
                except Exception as e:
                    print(f"Error al verificar paginación: {e}")
                    break

        except Exception as e:
            print(f"Error general durante la extracción: {e}")
            # Capturar screenshot del error
            try:
                await page.screenshot(path=os.path.join(descargas_path, "screenshot_error.png"))
                print(f"  Screenshot guardado en: screenshot_error.png")
            except:
                pass
        finally:
            await context.close()
            await browser.close()

    print(f"\n✓ Extracción completada: {len(results)} licitaciones procesadas")
    return results
