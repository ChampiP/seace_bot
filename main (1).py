from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

URL: str = (
    "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"
)


def main() -> None:
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch(headless=False, channel="msedge")
        context: BrowserContext = browser.new_context()
        page: Page = context.new_page()
        page.goto(URL)

        hiring_type_element = page.locator(
            "label#tbBuscador\:idFormbuscarACF\:cbxObjContratacion_label"
        )
        hiring_type_element.click()

        obra_option = page.locator(
            "div#tbBuscador\:idFormbuscarACF\:cbxObjContratacion_panel li[data-label='Obra']"
        )
        obra_option.click()

        submit_button = page.locator(
            "button[name='tbBuscador:idFormbuscarACF:btnBuscarSelCCOToken']"
        )
        submit_button.click()

        table_results = page.locator(
            "table#tbBuscador\:idFormbuscarACF\:pnlGrdResultadosAnuncioContratacionFutura"
        )
        table_results.wait_for()

        page.wait_for_timeout(2000)

        dowload_button = page.locator(
            "button[name='tbBuscador\:idFormbuscarACF\:btnExportar']"
        )

        with page.expect_download() as download_info:
            dowload_button.click()

        download = download_info.value
        download.save_as("resultados.xls")

        browser.close()


if __name__ == "__main__":
    main()
