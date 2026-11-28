"""Confere o catálogo e os arquivos do site. Roda no GitHub Actions a cada mudança.

Uso: python tests/check_data.py
Sai com erro (código 1) se achar algum problema que quebra o site.
Avisos não quebram, só aparecem no relatório.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
erros, avisos = [], []


def err(msg):
    erros.append(msg)


def warn(msg):
    avisos.append(msg)


def load_json(rel):
    path = os.path.join(ROOT, rel)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        err(f"{rel} não é um JSON válido: {e}")
        return None


def parse_time(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def check_catalog():
    d = load_json("data/products.json")
    if d is None:
        return
    cats = d.get("categories") or []
    if not cats:
        err("products.json sem categorias")
    ids = {c.get("id") for c in cats}
    nomes = set()
    reais = 0
    for c in cats:
        cid = c.get("id", "?")
        for k in ("id", "icon", "title", "filters", "items"):
            if k not in c:
                err(f"categoria {cid}: falta o campo '{k}'")
        filtros = set(c.get("filters", [])[1:])
        for it in c.get("items", []):
            n = it.get("n") or "(sem nome)"
            if not it.get("n"):
                err(f"{cid}: produto sem nome")
            if n in nomes:
                warn(f"nome repetido: {n}")
            nomes.add(n)
            if it.get("f") and it["f"] not in filtros:
                err(f"{n}: filtro '{it['f']}' não existe em {cid} {sorted(filtros)}")
            if not it.get("url"):
                continue  # vaga "em breve"
            reais += 1
            if not re.match(r"^https://(meli\.la|s\.shopee\.com\.br|shopee\.com\.br|(www\.|produto\.)?mercadolivre\.com\.br)/", it["url"]):
                err(f"{n}: link fora do Mercado Livre/Shopee: {it['url']}")
            if it.get("store", "Mercado Livre") not in ("Mercado Livre", "Shopee"):
                err(f"{n}: loja desconhecida '{it.get('store')}'")
            if ("shopee" in it["url"]) != (it.get("store") == "Shopee"):
                err(f"{n}: link e loja não combinam ({it.get('store')} x {it['url']})")
            img = it.get("img_clube") or it.get("img")
            if not img:
                err(f"{n}: sem foto")
            elif not os.path.isfile(os.path.join(ROOT, img)):
                err(f"{n}: foto não encontrada: {img}")
            elif not os.path.isfile(os.path.join(ROOT, img.replace("assets/img/", "assets/img/sm/"))):
                err(f"{n}: falta a versão pequena da foto (rode python robo/fotos.py): {img}")
            elif os.path.getsize(os.path.join(ROOT, img)) > 250_000:
                warn(f"{n}: foto pesada ({os.path.getsize(os.path.join(ROOT, img)) // 1024} KB): {img}")
            if "opcoes" in it and (not isinstance(it["opcoes"], str) or not it["opcoes"].strip()):
                err(f"{n}: campo 'opcoes' deve ser um texto, ex.: '3 cores'")
            p = it.get("price")
            if p is not None and (not isinstance(p, (int, float)) or p <= 0):
                err(f"{n}: preço inválido {p!r}")
            op = it.get("original_price")
            if op is not None and p and op <= p:
                warn(f"{n}: preço riscado ({op}) não é maior que o preço ({p})")
            for k in ("checked_at",):
                if it.get(k):
                    try:
                        if parse_time(it[k]) > datetime.now(timezone.utc):
                            err(f"{n}: {k} no futuro ({it[k]})")
                    except ValueError:
                        err(f"{n}: {k} fora do formato AAAA-MM-DDTHH:MM:SSZ ({it[k]})")
            for s in it.get("seen", []):
                if not isinstance(s.get("p"), (int, float)) or s["p"] <= 0:
                    err(f"{n}: histórico com preço inválido {s}")
                try:
                    parse_time(s.get("t", ""))
                except ValueError:
                    err(f"{n}: histórico com data inválida {s}")
            if it.get("seen") and not it.get("ref_high"):
                warn(f"{n}: tem histórico mas não tem ref_high (faixa de preço não aparece)")
    for m in d.get("manha", []):
        for r in m.get("regras", []):
            if r.get("cat") not in ids:
                err(f"manhã {m.get('hora')}: categoria '{r.get('cat')}' não existe")
            else:
                cat = next(c for c in cats if c["id"] == r["cat"])
                if r.get("f") and r["f"] not in cat.get("filters", []):
                    err(f"manhã {m.get('hora')}: filtro '{r['f']}' não existe em {r['cat']}")
    print(f"catálogo: {len(cats)} categorias, {reais} produtos com link")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        for k in ("href", "src"):
            v = a.get(k)
            if v and not v.startswith(("http", "mailto:", "data:", "#", "${", "tel:")):
                self.refs.append(v)
            if v and v.startswith("https://the5amclub.github.io/"):
                self.refs.append(v.replace("https://the5amclub.github.io/", "") or "index.html")
        if tag == "img" and "alt" not in a:
            err(f"imagem sem alt: {a.get('src')}")


def check_pages():
    for page in ("index.html", "404.html", "privacidade.html", "termos.html"):
        path = os.path.join(ROOT, page)
        if not os.path.isfile(path):
            err(f"falta a página {page}")
            continue
        html = open(path, encoding="utf-8").read()
        p = Links()
        p.feed(html)
        if not re.search(r"<title>[^<]{10,}</title>", html):
            err(f"{page}: sem <title>")
        if page != "404.html" and 'name="description"' not in html:
            err(f"{page}: sem meta description")
        for ref in p.refs:
            alvo = ref.split("#")[0].split("?")[0]
            if alvo and not os.path.exists(os.path.join(ROOT, alvo)):
                err(f"{page}: link para arquivo que não existe: {ref}")
    for f in ("robots.txt", "sitemap.xml", "og-image.jpg", "favicon.svg", "site.webmanifest", "data/site.json"):
        if not os.path.isfile(os.path.join(ROOT, f)):
            err(f"falta o arquivo {f}")
    load_json("data/site.json")
    load_json("site.webmanifest")


if __name__ == "__main__":
    check_catalog()
    check_pages()
    for a in avisos:
        print(f"aviso: {a}")
    for e in erros:
        print(f"ERRO: {e}")
    print(f"\n{len(erros)} erros, {len(avisos)} avisos")
    sys.exit(1 if erros else 0)
