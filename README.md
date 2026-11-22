# The 5am Club

curadoria para o seu melhor horário. Loja de curadoria de wellness feminino com links de afiliado (Mercado Livre e Shopee).

- `index.html`: o site (GitHub Pages).
- `data/products.json`: catálogo.
- `assets/img/`: fotos dos produtos.
- `scripts/` e `.github/workflows/`: robô de preços (pausado).

## Campos do catálogo

Campos que já existiam continuam iguais (`n`, `s`, `f`, `url`, `store`, `img`, `official`, preços e histórico). O robô de preços só mexe nos campos de preço e mantém todo o resto.

Campos novos, todos opcionais:

| Campo | Onde | Para que serve |
| --- | --- | --- |
| `manha` | topo do arquivo | Horários da vitrine "compre pela sua manhã". Cada horário tem `hora`, `titulo`, `cor` (`rosa`, `sunrise`, `lima` ou `ceu`) e `regras`, que dizem quais categorias (`cat`) e filtros (`f`) entram. |
| `marca` | produto | Nome da marca, aparece em cima do nome no card e na ficha. |
| `curadoria.por_que` | produto | A frase "por que entrou no clube". Aparece escrita à mão no card e no topo da ficha. Vazio: o site mostra a descrição do produto (`s`). |
| `curadoria.testado` | produto | Ex.: "testado por 21 dias pela May". Só aparece se preenchido. |
| `curadoria.notas` | produto | Notas de 0 a 5 por critério, ex.: `{"fórmula": 5, "custo por dose": 4}`. Se tiver pelo menos uma, a ficha mostra "nota do clube" com a média. |
| `curadoria.checou` | produto | Lista do que foi conferido, ex.: `["registro Anvisa", "Reclame Aqui"]`. Soma com o que o site já deduz sozinho (loja oficial, nota e vendas da loja, data do preço). |
| `img_clube` | produto | Foto regerada pelo clube. Quando existir, substitui `img` no card, na vitrine e na ficha. |

## Ficha do clube

Tocar na foto, no nome ou no botão do card leva direto para a loja. Tocar no selo "aprovado pelo clube" (ou em "ver ficha do clube") abre a ficha de curadoria. Cada ficha tem link próprio para compartilhar: `.../#ficha-nome-do-produto`.

## Próximo passo: foto do clube

A ideia é uma automação (no mesmo estilo do robô de preços) que pega `img`, gera uma versão com o fundo e a luz da identidade do clube e salva em `assets/img/clube/`, preenchendo `img_clube`. O site já está pronto para ler esse campo; não precisa mexer no `index.html`.
