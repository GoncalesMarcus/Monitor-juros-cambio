# Monitor de Juros e Câmbio — Brasil

Monitor em Python que coleta dados públicos do Banco Central do Brasil e do Federal Reserve, calcula indicadores de juros e câmbio e gera gráficos e uma tabela de dólar a termo teórico.

**Autor:** Marcus Gonçales Filho · Ciências Econômicas, PUC-SP

---

## O que o monitor acompanha

| Indicador | Fonte | Para que serve |
|---|---|---|
| Selic meta | BCB / SGS (série 432) | Postura da política monetária |
| IPCA esperado 12 meses | BCB / Focus | Expectativa de inflação do mercado |
| Juro real ex-ante | Cálculo próprio | Quão contracionista está a política monetária |
| Fed Funds efetivo | NY Fed (EFFR), com FRED como reserva | Juro de referência dos EUA |
| Diferencial Brasil–EUA | Cálculo próprio | Atratividade do carry trade em reais |
| USD/BRL | BCB / SGS (série 1) | Câmbio spot |
| Volatilidade do câmbio (21d) | Cálculo próprio | Risco percebido no real |
| Dólar a termo teórico | Cálculo próprio | Preço justo do termo pela paridade coberta |

## Leitura de conjuntura — outubro/2026

**Juros.** A Selic iniciou um ciclo de alta no fim de 2024 e chegou a 15% a.a. em meados de 2025, nível em que permaneceu até o início de 2026. Desde então, o Banco Central vem reduzindo os juros de forma gradual, e a meta está hoje em 13,75% a.a. Apesar dos cortes, a política monetária segue contracionista: descontada a inflação esperada para os próximos 12 meses (4,53%, segundo o Focus), o juro real ex-ante está em 8,8% a.a., bem acima das estimativas de juro neutro, em torno de 5%. Ou seja, o BC está aliviando o aperto, não estimulando a economia.

**Câmbio.** Com a Selic em 13,75% e o Fed Funds em 3,88%, o diferencial de juros entre Brasil e EUA está perto de 10 p.p., um nível historicamente elevado. Ao longo da série, diferenciais altos tenderam a sustentar o real pelo carry trade: foi assim em 2021–22 e novamente em 2025, quando o diferencial voltou a superar 10 p.p. e o dólar recuou para perto de R$ 5,00. Em outubro de 2026, porém, o diferencial alto não impediu um choque: após o segundo turno das eleições, o dólar subiu cerca de 8% em um único dia, e a volatilidade realizada de 21 dias saltou para 37,6% a.a., o maior nível da série e quase o triplo da média do período (12,8%). O episódio mostra que o carry protege o real em condições normais, mas perde força quando a percepção de risco fiscal e político aumenta. Pela paridade coberta, o dólar a termo de 12 meses fica cerca de 9,5% acima do spot, prêmio que reflete o diferencial de juros, e não uma expectativa de alta do dólar.

**O que acompanhar.** Três pontos devem orientar juros e câmbio nas próximas semanas. Primeiro, a reação do Copom: o choque cambial pode pressionar a inflação via preços de importados (pass-through), o que tende a desacelerar ou interromper o ciclo de cortes. Segundo, as expectativas do Focus: uma alta do IPCA esperado reduziria o juro real e enfraqueceria o argumento para novos cortes. Terceiro, a sinalização fiscal do próximo mandato e a política do Fed, que juntas determinam se o diferencial de juros volta a ser suficiente para atrair capital e reduzir a volatilidade do real.

## Gráficos

![Juros](graficos/1_juros.png)

![Diferencial e câmbio](graficos/2_diferencial_cambio.png)

![Volatilidade do câmbio](graficos/3_volatilidade_cambio.png)

## Dólar a termo teórico

Pela paridade coberta de juros, o preço justo do dólar a termo é:

$$F = S \times \frac{(1 + i_{BR})^t}{(1 + i_{EUA})^t}$$

A tabela com os valores atuais fica em [`dados/dolar_a_termo.csv`](dados/dolar_a_termo.csv).

**Limitação:** o cálculo usa a Selic meta e o Fed Funds como taxa para todos os prazos (curva plana). Uma mesa de câmbio usa a curva de DI futuro para o lado brasileiro e o cupom cambial para o lado em dólar. A diferença entre o termo teórico e o negociado reflete justamente a inclinação dessas curvas e o risco-país.

## Como rodar

```bash
pip install -r requirements.txt
python monitor.py
```

O script baixa os dados, salva os CSVs em `dados/` e os gráficos em `graficos/`.

## Próximos passos

- Incluir a curva de DI futuro (B3) e comparar o termo teórico com o de mercado
- Atualização automática semanal
- Painel interativo
