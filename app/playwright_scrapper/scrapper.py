from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

CHECKBOX_ID = "legal-notice"
LABEL_SELECTOR = f"label[for='{CHECKBOX_ID}']"
INPUT_SELECTOR = f"input#{CHECKBOX_ID}"

# Selectores para el formulario de búsqueda
SEARCH_INPUT_SELECTOR = "form input[name='searchText']"
SEARCH_BUTTON_SELECTOR = "form button[type='submit']"

# Selector rows results
RESULT_ROWS_SELECTOR = "tr.das-lib-tr_items"
# Selector link dentro de la primera fila
FIRST_RESULT_LINK_SELECTOR = f"{RESULT_ROWS_SELECTOR} a.das-strong.das-internal"

REACH_LINK_SELECTOR = "a.das-widget >> label[data-cy='dossierRegistrationCount-label']"

DOSSIER_ROLE_SELECTOR = 'td[data-cy="dossier-owner-js-role"] span'

# Dossier information
TOXICOLOGY_SECTION = "button[data-toc-target='#id_7_Toxicologicalinformation']"
TOXICOLOGY_NOAEL = "button[data-toc-target='#id_75_Repeateddosetoxicity']"


async def run(cas_code):
    browser = None
    result = {
        "status": "started",
        "cas_code": cas_code,
        "data": None,
        "message": "Iniciando scraping..."
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,  # Cambiar a True para evitar problemas de UI en servidor
                args=['--no-sandbox', '--disable-dev-shm-usage']  # Argumentos adicionales para Windows
            )
            context = await browser.new_context()
            page = await context.new_page()

            # Configurar timeouts más largos
            page.set_default_timeout(30000)  # 30 segundos

            await page.goto("https://chem.echa.europa.eu/", wait_until="networkidle")

            # Esperamos que el label esté visible (asumiendo que es clickeable)
            await page.wait_for_selector(LABEL_SELECTOR, state="visible")

            checkbox = await page.query_selector(INPUT_SELECTOR)
            label = await page.query_selector(LABEL_SELECTOR)

            if not checkbox or not label:
                result["status"] = "error"
                result["message"] = "No se encontró el checkbox o el label correspondiente."
                return result

            is_checked = await checkbox.is_checked()

            if not is_checked:
                # Hacemos click en el label para activar el checkbox con Angular
                await label.click()
                print("Checkbox marcado correctamente.")
            else:
                print("El checkbox ya estaba marcado.")

            # Ingresar texto en el input del formulario
            await page.wait_for_selector(SEARCH_INPUT_SELECTOR, state="visible")
            input_search = await page.query_selector(SEARCH_INPUT_SELECTOR)
            button_search = await page.query_selector(SEARCH_BUTTON_SELECTOR)

            if not input_search or not button_search:
                result["status"] = "error"
                result["message"] = "No se encontró el input de búsqueda o el botón."
                return result

            await input_search.fill(cas_code)
            print(f"Ingresado código '{cas_code}' en el campo de búsqueda.")

            # Click en el botón de búsqueda
            await button_search.click()
            print("Botón de búsqueda clickeado.")

            # Esperamos que aparezca la tabla o un mensaje de "no results"
            try:
                # Esperar resultados (timeout corto para no bloquear si no hay resultados)
                await page.wait_for_selector(RESULT_ROWS_SELECTOR, timeout=15000)
            except PlaywrightTimeoutError:
                result["status"] = "no_results"
                result["message"] = "No se encontraron resultados para la búsqueda."
                return result

            # Hay resultados, clicamos el primer enlace
            first_link = await page.query_selector(FIRST_RESULT_LINK_SELECTOR)
            if first_link:
                href = await first_link.get_attribute("href")
                print(f"Primer resultado encontrado, entrando a: {href}")
                await first_link.click()
                # Esperar navegación a la nueva sección
                await page.wait_for_load_state("networkidle")
                print("Navegado a la sección del primer resultado.")
            else:
                result["status"] = "error"
                result["message"] = "No se encontró el enlace en la primera fila de resultados."
                return result

            try:
                # Esperar que aparezca el enlace de REACH registrations
                await page.wait_for_selector(REACH_LINK_SELECTOR, timeout=15000)
                reach_label = await page.query_selector(REACH_LINK_SELECTOR)

                if reach_label:
                    # Subimos al <a> desde el <label> para hacer clic
                    reach_link = await reach_label.evaluate_handle("node => node.closest('a')")
                    href = await reach_link.get_attribute("href")
                    print(f"Entrando al enlace de REACH registrations: {href}")
                    await reach_link.click()
                    await page.wait_for_load_state("networkidle")
                    print("Navegado a la página de REACH registrations.")
                else:
                    result["status"] = "error"
                    result["message"] = "No se encontró el enlace de REACH registrations."
                    return result
            except PlaywrightTimeoutError:
                result["status"] = "error"
                result["message"] = "El enlace de REACH registrations no apareció a tiempo."
                return result

            try:
                print("Esperando la tabla de dosieres...")
                await page.wait_for_selector(DOSSIER_ROLE_SELECTOR, timeout=15000)
                role_spans = await page.query_selector_all(DOSSIER_ROLE_SELECTOR)

                lead_found = False
                for i, span in enumerate(role_spans):
                    role_text = (await span.inner_text()).strip().lower()
                    if "lead" in role_text:
                        print(f"✅ Se encontró un dosier con rol 'Lead' en la fila {i+1}: '{role_text}'")
                        lead_found = True

                        # Encontramos el <tr> de la fila con rol Lead
                        row = await span.evaluate_handle("el => el.closest('tr')")

                        # Dentro de esa fila, buscamos el enlace al dossier
                        dossier_link = await row.query_selector("td[data-cy='dossier-icon'] a")

                        if dossier_link:
                            href = await dossier_link.get_attribute("href")
                            print(f"Entrando al dossier tipo Lead en: {href}")
                            await dossier_link.click()
                            await page.wait_for_load_state("networkidle")
                            print("✅ Navegado al dossier tipo Lead correctamente.")
                            extraction_result = await extraer_info_dossier(page)
                            result["data"] = extraction_result
                            break
                        else:
                            result["status"] = "error"
                            result["message"] = "No se encontró el enlace al dossier en la fila con rol Lead."
                            return result

                if not lead_found:
                    result["status"] = "error"
                    result["message"] = "No se encontró ningún dosier con rol 'Lead'."
                    return result

            except PlaywrightTimeoutError:
                result["status"] = "error"
                result["message"] = "La tabla de dosieres no apareció a tiempo."
                return result

            # Si llegamos aquí, todo fue exitoso
            result["status"] = "success"
            result["message"] = "Scraping completado exitosamente"
            return result

    except Exception as e:
        print(f"Error general durante el scraping: {str(e)}")
        result["status"] = "error"
        result["message"] = f"Error inesperado: {str(e)}"
        return result

    finally:
        # Asegurar que el browser se cierre siempre
        if browser:
            try:
                await browser.close()
                print("Browser cerrado correctamente")
            except Exception as e:
                print(f"Error cerrando browser: {str(e)}")


async def extraer_info_dossier(page):
    print("🔍 Intentando acceder al contenido dentro del Shadow DOM e iframe...")

    extraction_data = {
        "toxicology_accessed": False,
        "summary_data": None,
        "error": None
    }

    try:
        await page.wait_for_selector("iucdas-mod-dossier-view-app", state="attached", timeout=10000)
        print("✅ Componente iucdas-mod-dossier-view-app encontrado")

        # 2. Acceder al Shadow DOM del componente
        iframe_src = await page.evaluate("""() => {
            const hostElement = document.querySelector('iucdas-mod-dossier-view-app');
            if (!hostElement || !hostElement.shadowRoot) {
                return null;
            }
            
            const iframe = hostElement.shadowRoot.querySelector('iframe[title="Dossier view"]');
            return iframe ? iframe.src : null;
        }""")

        if not iframe_src:
            extraction_data["error"] = "No se pudo encontrar el iframe dentro del Shadow DOM"
            return extraction_data

        print(f"✅ URL del iframe encontrada: {iframe_src}")

        # 3. Obtener el frame directamente por su URL
        all_frames = page.frames
        target_frame = None

        for frame in all_frames:
            if frame.url == iframe_src:
                target_frame = frame
                print("✅ Frame encontrado por URL")
                break

        if not target_frame:
            for frame in all_frames:
                if iframe_src in frame.url:
                    target_frame = frame
                    print(f"✅ Frame encontrado por coincidencia parcial: {frame.url}")
                    break

        if not target_frame and len(all_frames) > 1:
            target_frame = all_frames[1]
            print(f"⚠️ Usando frame por índice (1): {target_frame.url}")

        if not target_frame:
            extraction_data["error"] = "No se pudo encontrar el frame objetivo"
            return extraction_data

        # 5. Buscar el botón de información toxicológica
        await target_frame.wait_for_load_state("networkidle")

        try:
            print(f"🔍 Intentando selector: {TOXICOLOGY_SECTION}")
            element = await target_frame.query_selector(TOXICOLOGY_SECTION)

            if element:
                await element.scroll_into_view_if_needed()
                await target_frame.wait_for_timeout(500)
                await element.click()
                print(f"✅ Éxito! Botón encontrado y clicado con selector: {TOXICOLOGY_SECTION}")
                extraction_data["toxicology_accessed"] = True

                await target_frame.wait_for_timeout(2000)

                # Continuar con la extracción del NOAEL
                try:
                    element = await target_frame.query_selector(TOXICOLOGY_NOAEL)
                    if element:
                        await element.click()
                        print(f"✅ Éxito! Botón NOAEL clicado")
                        await target_frame.wait_for_timeout(2000)

                        # Buscar el enlace del resumen
                        TOXICOLOGY_NOAEL_SUMMARY = "a.das-leaf.das-docid-IUC5-c5c5dd9c-045f-4d20-a1d4-cd2301d3569a_5f2f0062-0783-425a-a1cb-18b6b744ba6a"

                        summary_link = await target_frame.query_selector(TOXICOLOGY_NOAEL_SUMMARY)
                        if summary_link:
                            await summary_link.scroll_into_view_if_needed()
                            await target_frame.wait_for_timeout(500)
                            await summary_link.click()
                            print(f"✅ Enlace de resumen clicado")
                            await target_frame.wait_for_timeout(2000)

                            # Extraer información del resumen
                            summary_result = await extraer_info_summary(page, target_frame)
                            extraction_data["summary_data"] = summary_result

                except Exception as e:
                    extraction_data["error"] = f"Error en NOAEL: {str(e)}"

        except Exception as e:
            extraction_data["error"] = f"Error en toxicología: {str(e)}"

    except Exception as e:
        extraction_data["error"] = f"Error general: {str(e)}"
        # Capturar screenshot en caso de error
        try:
            await page.screenshot(path="error_toxicology.png")
        except:
            pass

    return extraction_data


async def extraer_info_summary(page, target_frame):
    print("🔍 Extrayendo información del resumen toxicológico...")

    summary_data = {
        "iframe_found": False,
        "content_extracted": False,
        "key_info": None,
        "error": None
    }

    try:
        await target_frame.wait_for_timeout(2000)

        # Obtener el iframe del documento
        document_iframe_src = await target_frame.evaluate("""() => {
            const docIframe = document.querySelector('iframe[title="Document view"][data-cy="das-document-iframe"]');
            return docIframe ? docIframe.src : null;
        }""")

        if not document_iframe_src:
            summary_data["error"] = "No se pudo encontrar la URL del iframe del documento"
            return summary_data

        summary_data["iframe_found"] = True
        print(f"✅ Iframe del documento encontrado con URL: {document_iframe_src}")

        # Buscar el frame del documento
        document_frame = None
        all_frames = page.frames

        for frame in all_frames:
            if frame.url == document_iframe_src:
                document_frame = frame
                break

        if not document_frame:
            for frame in all_frames:
                if document_iframe_src in frame.url:
                    document_frame = frame
                    break

        if not document_frame:
            summary_data["error"] = "No se pudo encontrar el iframe del documento"
            return summary_data

        await document_frame.wait_for_load_state("networkidle")
        print("🔍 Extrayendo información del resumen desde el iframe del documento...")

        # Extraer la información clave
        key_info = await document_frame.evaluate("""() => {
            const keyInfoSection = document.querySelector('section.das-block.KeyInformation');
            
            if (!keyInfoSection) {
                const allSections = document.querySelectorAll('section.das-block');
                for (const section of allSections) {
                    if (section.querySelector('h3.das-block_label')?.innerText.includes('Description of key information')) {
                        const contentDiv = section.querySelector('.das-field_value_html');
                        if (contentDiv) {
                            return {
                                found: true,
                                content: contentDiv.innerHTML,
                                textContent: contentDiv.innerText
                            };
                        }
                    }
                }
                return { found: false, error: 'Sección de información clave no encontrada' };
            }
            
            const contentDiv = keyInfoSection.querySelector('.das-field_value_html');
            if (!contentDiv) {
                return { found: false, error: 'Div de contenido no encontrado dentro de la sección' };
            }
            
            return {
                found: true,
                content: contentDiv.innerHTML,
                textContent: contentDiv.innerText
            };
        }""")

        if key_info.get('found'):
            summary_data["content_extracted"] = True
            summary_data["key_info"] = {
                "html_content": key_info.get('content'),
                "text_content": key_info.get('textContent')
            }

            # Guardar el HTML (opcional, comentar si no se necesita en API)
            try:
                with open("key_info_description.html", "w", encoding="utf-8") as f:
                    f.write(key_info.get('content', ''))
                print("💾 HTML guardado en 'key_info_description.html'")
            except Exception as file_error:
                print(f"⚠️ No se pudo guardar el archivo: {file_error}")

        else:
            summary_data["error"] = key_info.get('error', 'Error desconocido al extraer información')

    except Exception as e:
        summary_data["error"] = f"Error general en extracción de resumen: {str(e)}"

    return summary_data


if __name__ == "__main__":
    import sys
    import asyncio

    # 🛠️ Compatibilidad con Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    if len(sys.argv) < 2:
        print("❌ Falta argumento")
        sys.exit(1)

    asyncio.run(run(sys.argv[1]))
