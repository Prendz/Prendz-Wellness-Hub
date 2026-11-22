"""Robô de preços da WellnessHub (Apify).

Roda no GitHub Actions uma vez por dia. Para cada produto do Mercado Livre com link de afiliado:
1. Descobre a página do produto seguindo o link meli.la (só na primeira vez; fica salvo em `ml_url`).
2. Manda todas as páginas para o coletor da Apify (getdataforme/mercadolivrebr-products-scraper)
   numa única execução e lê o preço atual de cada uma.
3. Grava preço, horário e histórico em data/products.json.

Precisa do segredo APIFY_TOKEN no repositório.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTS = os.path.join(ROOT, "data", "products.json")
ACTOR = "getdataforme~mercadolivrebr-products-scraper"
BROWSER = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36",
           "Accept-Language": "pt-BR,pt;q=0.9", "Accept": "text/html"}
CATALOG_RE = re.compile(r"/p/(MLB\d{6,})")
ITEM_RE = re.compile(r"MLB-?(\d{6,})")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve(url):
    """Segue o meli.la e devolve a URL canônica da página do produto."""
    req = urllib.request.Request(url, headers=BROWSER)
    with urllib.request.urlopen(req, timeout=30) as r:
        final, page = r.geturl(), r.read().decode("utf-8", "replace")
    for text in (final, page):
        m = CATALOG_RE.search(text)
        if m:
            return f"https://www.mercadolivre.com.br/p/{m.group(1)}"
    for text in (final, page):
        m = ITEM_RE.search(text)
        if m:
            return f"https://produto.mercadolivre.com.br/MLB-{m.group(1)}"
    return None


def key(url):
    m = CATALOG_RE.search(url or "") or ITEM_RE.search(url or "")
    return m.group(1).replace("MLB", "") if m else None


def run_actor(urls, token):
    endpoint = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?token={token}&timeout=280"
    for body in ({"Urls": urls}, {"Urls": [{"url": u} for u in urls]}):
        req = urllib.request.Request(endpoint, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                items = json.loads(r.read().decode())
            if items:
                return items
            print("[apify] execução sem resultados com esse formato de input, tentando o outro")
        except Exception as e:  # noqa: BLE001
            print(f"[apify] erro: {e}")
    return []


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,\.]", "", str(v))
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def main():
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        print("Falta o segredo APIFY_TOKEN.")
        sys.exit(1)
    data = json.load(open(PRODUCTS, encoding="utf-8"))
    items = [it for c in data["categories"] for it in c["items"] if it.get("url") and it.get("store", "Mercado Livre") == "Mercado Livre"]

    for it in items:
        if not it.get("ml_url"):
            try:
                it["ml_url"] = resolve(it["url"])
            except Exception as e:  # noqa: BLE001
                print(f"[link] {it['n']}: {e}")
    urls = [it["ml_url"] for it in items if it.get("ml_url")]
    print(f"[apify] consultando {len(urls)} produtos")
    results = run_actor(urls, token)
    print(f"[apify] {len(results)} resultados")
    if results:
        print("[apify] campos do primeiro resultado:", sorted(results[0].keys()))

    by_key = {}
    for r in results:
        k = key(r.get("url") or r.get("Url") or r.get("link") or "") or key(json.dumps(r))
        if k:
            by_key[k] = r

    ok = 0
    print("\nCOMPARATIVO (último preço conhecido x Apify)")
    for it in items:
        r = by_key.get(key(it.get("ml_url")))
        price = num(r.get("price")) if r else None
        if not price:
            print(f"[sem preço] {it['n']}")
            continue
        before = it.get("price")
        original = num(r.get("original_price") or r.get("originalPrice") or r.get("old_price"))
        it["price"] = price
        it["original_price"] = original if original and original > price else None
        it["price_note"], it["event"] = "", None
        it["price_source"], it["checked_at"] = "apify", now_iso()
        it.setdefault("seen", []).append({"t": it["checked_at"], "p": price})
        it["seen"] = it["seen"][-60:]
        it["ref_high"] = max(int(it.get("ref_high") or 0), int(-(-(original or price) // 1)))
        ok += 1
        print(f"{it['n']} | antes {before} | agora {price}")

    data["updated_at"] = now_iso()
    json.dump(data, open(PRODUCTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nResumo: {ok} de {len(items)} atualizados")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
