"""Gera a versão pequena (360 px) de cada foto de produto, usada nos cards do celular.

Uso: python robo/fotos.py
Roda sempre que entrar foto nova em assets/img/. Só cria o que estiver faltando.
"""
import glob
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "img")
SM = os.path.join(SRC, "sm")
os.makedirs(SM, exist_ok=True)
feitos = 0
for f in sorted(glob.glob(os.path.join(SRC, "**", "*.webp"), recursive=True)):
    if os.sep + "sm" + os.sep in f:
        continue
    rel = os.path.relpath(f, SRC)
    out = os.path.join(SM, rel)
    if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(f):
        continue
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im = Image.open(f).convert("RGB")
    im.thumbnail((360, 360), Image.LANCZOS)
    im.save(out, "WEBP", quality=78, method=6)
    feitos += 1
print(f"{feitos} fotos pequenas geradas")
