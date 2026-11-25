"""Abre o site num navegador de verdade (celular e computador) e testa o que o cliente usa.

Uso: python tests/browser_test.py [pasta_para_prints]
Precisa do Playwright (pip install playwright && playwright install chromium).
"""
import functools
import http.server
import os
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else None
falhas = []


def check(cond, msg):
    print(("ok    " if cond else "FALHOU ") + msg)
    if not cond:
        falhas.append(msg)


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=ROOT)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/"


def run(browser, base, nome, viewport, mobile):
    ctx = browser.new_context(viewport=viewport, is_mobile=mobile, has_touch=mobile, locale="pt-BR")
    # bloqueia o que vem de fora (fontes, analytics): o teste não depende de internet
    ctx.route("**/*", lambda r: r.abort() if not r.request.url.startswith(base) else r.continue_())
    page = ctx.new_page()
    erros_js, quebrados = [], []
    page.on("pageerror", lambda e: erros_js.append(str(e)))
    page.on("console", lambda m: erros_js.append(m.text) if m.type == "error" and "net::ERR_FAILED" not in m.text else None)
    page.on("response", lambda r: quebrados.append(r.url) if r.status >= 400 and r.url.startswith(base) else None)

    print(f"\n[{nome}]")
    page.goto(base, wait_until="networkidle")
    page.wait_for_selector("section.shelf .card", timeout=10000)
    cards = page.locator("section.shelf .card:not(.ghost)").count()
    check(cards > 0, f"{cards} cards de produto aparecem nas prateleiras")
    check(page.locator("#shelves[aria-busy]").count() == 0, "aviso de carregando some depois do catálogo")
    largura = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    check(largura <= 1, f"sem rolagem lateral na página (sobra {largura}px)")
    imgs_quebradas = page.evaluate("""() => [...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.src.startsWith(location.origin)).map(i => i.src)""")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(800)
    imgs_quebradas += page.evaluate("""() => [...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.src.startsWith(location.origin)).map(i => i.src)""")
    check(not imgs_quebradas, f"todas as fotos carregam {sorted(set(imgs_quebradas))[:3]}")

    links_loja = page.evaluate("""() => [...document.querySelectorAll('a.buy, a.art-link, a.title-link')].filter(a => !/^https:\\/\\/(meli\\.la|s\\.shopee\\.com\\.br|shopee\\.com\\.br|(www\\.|produto\\.)?mercadolivre\\.com\\.br)\\//.test(a.href) || a.target !== '_blank' || !a.rel.includes('sponsored')).map(a => a.href)""")
    check(not links_loja, f"todo botão/foto/nome leva à loja em nova aba com rel=sponsored {links_loja[:3]}")

    # filtros de categoria
    shelf = page.locator("section.shelf").first
    chips = shelf.locator(".chip")
    if chips.count() > 1:
        chips.nth(1).click()
        f = chips.nth(1).get_attribute("data-filter")
        visiveis = shelf.locator(".card:visible")
        ok = all(visiveis.nth(i).get_attribute("data-f") == f for i in range(visiveis.count()))
        check(ok, f"filtro '{f}' mostra só os produtos daquele filtro")
        chips.nth(0).click()

    # compre pela sua manhã
    tcs = page.locator("#times .tc")
    if tcs.count() > 1:
        tcs.nth(1).click()
        check(tcs.nth(1).get_attribute("aria-pressed") == "true", "trocar o horário da manhã funciona")

    # ficha do clube
    page.locator("section.shelf .seal").first.click()
    page.wait_for_selector("dialog#ficha[open]", timeout=3000)
    check("#ficha-" in page.url, "ficha abre pelo selo e ganha link próprio")
    if OUT:
        page.screenshot(path=os.path.join(OUT, f"{nome}-ficha.png"))
    page.locator("#ficha [data-close]").click()
    try:
        page.wait_for_function("() => !document.querySelector('dialog#ficha[open]') && !location.hash.startsWith('#ficha-')", timeout=3000)
    except Exception:  # noqa: BLE001
        pass
    check(page.locator("dialog#ficha[open]").count() == 0 and "#ficha-" not in page.url, "ficha fecha e o link volta ao normal")

    # link direto para uma ficha
    fid = page.locator("section.shelf .seal").first.get_attribute("data-ficha")
    page.goto("about:blank")
    page.goto(base + "#ficha-" + fid, wait_until="networkidle")
    page.wait_for_selector("dialog#ficha[open]", timeout=5000)
    check(True, "link compartilhado de ficha abre a ficha direto")
    page.keyboard.press("Escape")

    if OUT:
        page.goto(base, wait_until="networkidle")
        page.wait_for_selector("section.shelf .card")
        page.screenshot(path=os.path.join(OUT, f"{nome}-home.png"), full_page=True)

    for p in ("404.html", "privacidade.html", "termos.html"):
        page.goto(base + p, wait_until="networkidle")
        largura = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check(largura <= 1 and page.locator("h1").count() == 1, f"{p} abre sem rolagem lateral")

    check(not quebrados, f"nenhum arquivo do site dá erro 404 {quebrados[:3]}")
    check(not erros_js, f"nenhum erro de JavaScript {erros_js[:3]}")
    ctx.close()


def main():
    srv, base = serve()
    with sync_playwright() as p:
        exe = os.environ.get("CHROME_PATH")
        browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        run(browser, base, "celular", {"width": 360, "height": 780}, True)
        run(browser, base, "computador", {"width": 1366, "height": 900}, False)
        browser.close()
    srv.shutdown()
    print(f"\n{len(falhas)} falhas")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
