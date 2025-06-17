import asyncio
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


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://chem.echa.europa.eu/", wait_until="networkidle")

        try:
            # Esperamos que el label esté visible (asumiendo que es clickeable)
            await page.wait_for_selector(LABEL_SELECTOR, state="visible")

            checkbox = await page.query_selector(INPUT_SELECTOR)
            label = await page.query_selector(LABEL_SELECTOR)

            if not checkbox or not label:
                print("No se encontró el checkbox o el label correspondiente.")
                await browser.close()
                return

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
                print("No se encontró el input de búsqueda o el botón.")
                await browser.close()
                return

            codigo_a_buscar = "627-83-8"  # Cambia por el código que quieras buscar

            await input_search.fill(codigo_a_buscar)
            print(f"Ingresado código '{codigo_a_buscar}' en el campo de búsqueda.")

            # Click en el botón de búsqueda
            await button_search.click()
            print("Botón de búsqueda clickeado.")


            # Esperamos que aparezca la tabla o un mensaje de "no results"
            try:
                # Esperar resultados (timeout corto para no bloquear si no hay resultados)
                await page.wait_for_selector(RESULT_ROWS_SELECTOR)
            except PlaywrightTimeoutError:
                print("No se encontraron resultados para la búsqueda.")
                await browser.close()
                return

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
                print("No se encontró el enlace en la primera fila de resultados.")

            try:
                # Esperar que aparezca el enlace de REACH registrations
                await page.wait_for_selector(REACH_LINK_SELECTOR)
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
                    print("No se encontró el enlace de REACH registrations.")
            except PlaywrightTimeoutError:
                print("El enlace de REACH registrations no apareció a tiempo.")

            try:
                print("Esperando la tabla de dosieres...")
                await page.wait_for_selector(DOSSIER_ROLE_SELECTOR)
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
                            await extraer_info_dossier(page)

                        else:
                            print("⚠️ No se encontró el enlace al dossier en la fila con rol Lead.")
                        break

                if not lead_found:
                    print("⚠️ No se encontró ningún dosier con rol 'Lead'.")

            except PlaywrightTimeoutError:
                print("⏰ La tabla de dosieres no apareció a tiempo.")

        except PlaywrightTimeoutError:
            print("Algún elemento no apareció en el tiempo esperado.")

        await browser.close()


async def extraer_info_dossier(page):
    print("🔍 Intentando acceder al contenido dentro del Shadow DOM e iframe...")

    try:
        await page.wait_for_selector("iucdas-mod-dossier-view-app", state="attached", timeout=10000)
        print("✅ Componente iucdas-mod-dossier-view-app encontrado")

        # 2. Acceder al Shadow DOM del componente
        # Esto requiere JavaScript para atravesar el Shadow DOM
        iframe_src = await page.evaluate("""() => {
            // Obtener el elemento que contiene el Shadow DOM
            const hostElement = document.querySelector('iucdas-mod-dossier-view-app');
            if (!hostElement || !hostElement.shadowRoot) {
                return null;
            }
            
            // Buscar el iframe dentro del Shadow DOM
            const iframe = hostElement.shadowRoot.querySelector('iframe[title="Dossier view"]');
            return iframe ? iframe.src : null;
        }""")

        if not iframe_src:
            print("❌ No se pudo encontrar el iframe dentro del Shadow DOM")
            return

        print(f"✅ URL del iframe encontrada: {iframe_src}")

        # 3. Obtener el frame directamente por su URL
        all_frames = page.frames
        target_frame = None

        for frame in all_frames:
            if frame.url == iframe_src:
                target_frame = frame
                print("✅ Frame encontrado por URL")
                break

        # Si no encontramos el frame por URL exacta, buscamos por coincidencia parcial
        if not target_frame:
            for frame in all_frames:
                if iframe_src in frame.url:
                    target_frame = frame
                    print(f"✅ Frame encontrado por coincidencia parcial: {frame.url}")
                    break

        # 4. Si aún no encontramos el frame, intentamos acceder directamente por índice
        if not target_frame and len(all_frames) > 1:
            # El primer frame (índice 0) suele ser la página principal
            # Intentamos con el segundo frame (índice 1) que suele ser el primer iframe
            target_frame = all_frames[1]
            print(f"⚠️ Usando frame por índice (1): {target_frame.url}")

        if not target_frame:
            print("❌ No se pudo encontrar el frame objetivo")
            return

        # 5. Ahora que tenemos el frame, buscamos el botón de información toxicológica
        print("🔍 Buscando el botón para expandir la sección 'Toxicological information' dentro del iframe...")

        # Esperar a que el contenido del iframe se cargue completamente
        await target_frame.wait_for_load_state("networkidle")

        success = False
        try:
            print(f"🔍 Intentando selector: {TOXICOLOGY_SECTION}")

            # Verificar si el selector existe
            element = await target_frame.query_selector(TOXICOLOGY_SECTION)
            if element:
                # Hacer scroll hasta el elemento para asegurar que es visible
                await element.scroll_into_view_if_needed()
                await target_frame.wait_for_timeout(500)  # Pequeña pausa

                # Hacer clic
                await element.click()
                print(f"✅ Éxito! Botón encontrado y clicado con selector: {TOXICOLOGY_SECTION}")
                success = True

                # Esperar a que se expanda la sección
                await target_frame.wait_for_timeout(2000)

                try:
                    print(f"🔍 Intentando selector: {TOXICOLOGY_NOAEL}")
                    element = await target_frame.query_selector(TOXICOLOGY_NOAEL)
                    if element:
                        await element.click()
                        print(f"✅ Éxito! Botón encontrado y clicado con selector: {TOXICOLOGY_NOAEL}")
                        success = True
                        await target_frame.wait_for_timeout(2000)

                        # NUEVO CÓDIGO: Buscar y hacer clic en el enlace del resumen
                        print("🔍 Buscando el enlace 'S-01 | Summary'...")

                        # Definir varios selectores posibles para el enlace de resumen
                        TOXICOLOGY_NOAEL_SUMMARY = "a.das-leaf.das-docid-IUC5-c5c5dd9c-045f-4d20-a1d4-cd2301d3569a_5f2f0062-0783-425a-a1cb-18b6b744ba6a"

                        summary_found = False
                        try:
                            print(f"🔍 Intentando selector para resumen: {TOXICOLOGY_NOAEL_SUMMARY}")
                            summary_link = await target_frame.query_selector(TOXICOLOGY_NOAEL_SUMMARY)

                            if summary_link:
                                # Hacer scroll hasta el enlace para asegurar que es visible
                                await summary_link.scroll_into_view_if_needed()
                                await target_frame.wait_for_timeout(500)

                                # Hacer clic en el enlace
                                await summary_link.click()
                                print(f"✅ Éxito! Enlace de resumen encontrado y clicado con selector: {TOXICOLOGY_NOAEL_SUMMARY}")
                                summary_found = True
                                await target_frame.wait_for_timeout(2000)

                        except Exception as e:
                            print(f"⚠️ Error con selector de resumen {TOXICOLOGY_NOAEL_SUMMARY}: {str(e)}")

                        if summary_found:
                            print("✅ Navegación al resumen toxicológico completada exitosamente")
                            await extraer_info_summary(page, target_frame)
                        else:
                            print("❌ No se pudo acceder al resumen de información toxicológica")

                except Exception as e:
                    print(f"⚠️ Error con selector {TOXICOLOGY_NOAEL}: {str(e)}")

        except Exception as e:
            print(f"⚠️ Error con selector {TOXICOLOGY_SECTION}: {str(e)}")

    except Exception as e:
        print(f"❌ Error general: {str(e)}")
        import traceback
        traceback.print_exc()
        # Capturar una captura de pantalla en caso de error
        await page.screenshot(path="error_toxicology.png")

async def extraer_info_summary(page, target_frame):
    print("🔍 Extrayendo información del resumen toxicológico...")

    # Esperar a que se cargue el iframe del documento
    await target_frame.wait_for_timeout(2000)

    # Obtener el iframe del documento que aparece después de hacer clic en el resumen
    document_iframe_src = await target_frame.evaluate("""() => {
        const docIframe = document.querySelector('iframe[title="Document view"][data-cy="das-document-iframe"]');
        return docIframe ? docIframe.src : null;
    }""")

    if not document_iframe_src:
        print("❌ No se pudo encontrar la URL del iframe del documento")
        return False

    print(f"✅ Iframe del documento encontrado con URL: {document_iframe_src}")

    # Buscar el frame entre los frames de la página
    document_frame = None
    all_frames = page.frames

    for frame in all_frames:
        if frame.url == document_iframe_src:
            document_frame = frame
            print("✅ Frame del documento encontrado por URL exacta")
            break

    # Si no encontramos el frame por URL exacta, buscamos por coincidencia parcial
    if not document_frame:
        for frame in all_frames:
            if document_iframe_src in frame.url:
                document_frame = frame
                print(f"✅ Frame del documento encontrado por coincidencia parcial: {frame.url}")
                break

    # Si todavía no encontramos el frame, intentamos una solución alternativa
    if not document_frame:
        print("⚠️ Usando método alternativo para acceder al iframe...")
        # Esta es una alternativa más extrema que podría funcionar en algunos casos
        all_iframes = await page.query_selector_all("iframe")
        for iframe in all_iframes:
            src = await iframe.get_attribute("src")
            if src and "document" in src.lower():
                document_frame = await iframe.content_frame()
                if document_frame:
                    print(f"✅ Frame del documento encontrado por atributo src: {src}")
                    break

    # Si no hemos encontrado el frame, no podemos continuar
    if not document_frame:
        print("❌ No se pudo encontrar el iframe del documento")
        return False

    # Esperamos a que el contenido del frame se cargue completamente
    await document_frame.wait_for_load_state("networkidle")
    print("🔍 Extrayendo información del resumen desde el iframe del documento...")

    # Extraer la sección "Description of key information"
    key_info = await document_frame.evaluate("""() => {
        // Buscar la sección por su clase e ID
        const keyInfoSection = document.querySelector('section.das-block.KeyInformation');
        
        if (!keyInfoSection) {
            // Buscar por el título si no encontramos por clase
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
        
        // Si encontramos la sección directamente
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

    with open("key_info_description.html", "w", encoding="utf-8") as f:
        f.write(key_info.get('content'))
    print("💾 HTML guardado en 'key_info_description.html'")

    return True


if __name__ == "__main__":
    asyncio.run(run())