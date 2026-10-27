"""
Monitor de Juros e Câmbio — Brasil
Autor: Marcus Gonçales Filho

Coleta dados públicos (Banco Central do Brasil e FRED), calcula indicadores
de juros e câmbio e gera gráficos e tabelas em /graficos e /dados.

Uso:
    pip install -r requirements.txt
    python monitor.py
"""

from datetime import date, timedelta
from pathlib import Path
import io
import time

import numpy as np
import pandas as pd
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
INICIO = date(2019, 1, 1)
PASTA_DADOS = Path("dados")
PASTA_GRAFICOS = Path("graficos")

# Séries do SGS (Banco Central)
SERIES_SGS = {
    "selic_meta": 432,      # Meta Selic definida pelo Copom (% a.a.)
    "usdbrl": 1,            # Dólar comercial, venda (R$/US$)
    "ipca_12m": 13522,      # IPCA acumulado em 12 meses (%)
}

HEADERS = {"User-Agent": "monitor-juros-cambio (projeto academico)"}


# ---------------------------------------------------------------------------
# Coleta
# ---------------------------------------------------------------------------
def baixar_sgs(codigo: int, inicio: date) -> pd.Series:
    """Baixa uma série do SGS. A API limita séries diárias a janelas de
    10 anos, então a consulta é feita em blocos."""
    partes = []
    ini = inicio
    hoje = date.today()
    while ini <= hoje:
        fim = min(date(ini.year + 9, 12, 31), hoje)
        url = (
            f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
            f"?formato=json&dataInicial={ini:%d/%m/%Y}&dataFinal={fim:%d/%m/%Y}"
        )
        r = requests.get(url, headers=HEADERS, timeout=60)
        r.raise_for_status()
        partes.extend(r.json())
        ini = fim + timedelta(days=1)

    df = pd.DataFrame(partes)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df.set_index("data")["valor"].sort_index()


def baixar_focus_ipca_12m(inicio: date) -> pd.Series:
    """Mediana da expectativa de IPCA para os próximos 12 meses (Focus/BCB),
    série suavizada."""
    url = (
        "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
        "ExpectativasMercadoInflacao12Meses"
        "?$format=json&$select=Data,Mediana"
        "&$filter=Indicador%20eq%20'IPCA'%20and%20Suavizada%20eq%20'S'"
        f"%20and%20baseCalculo%20eq%200%20and%20Data%20ge%20'{inicio:%Y-%m-%d}'"
        "&$orderby=Data%20asc"
        "&$top=100000"
    )
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    df = pd.DataFrame(r.json()["value"])
    df["Data"] = pd.to_datetime(df["Data"])
    return df.set_index("Data")["Mediana"].sort_index().rename("ipca_esperado_12m")


HEADERS_NAVEGADOR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    )
}


def _get_com_retentativas(url, headers, tentativas=3, espera=3):
    """GET com novas tentativas em caso de falha de conexão."""
    ultimo_erro = None
    for i in range(tentativas):
        try:
            r = requests.get(url, headers=headers, timeout=60)
            r.raise_for_status()
            return r
        except requests.RequestException as erro:
            ultimo_erro = erro
            time.sleep(espera * (i + 1))
    raise ultimo_erro


def _fed_funds_nyfed(inicio: date) -> pd.Series:
    """Effective Federal Funds Rate (EFFR) publicada pelo Federal Reserve
    Bank of New York, em % a.a. Consulta feita ano a ano."""
    partes = []
    for ano in range(inicio.year, date.today().year + 1):
        ini = max(date(ano, 1, 1), inicio)
        fim = min(date(ano, 12, 31), date.today())
        url = (
            "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"
            f"?startDate={ini:%Y-%m-%d}&endDate={fim:%Y-%m-%d}"
        )
        r = _get_com_retentativas(url, HEADERS_NAVEGADOR)
        partes.extend(r.json().get("refRates", []))
    df = pd.DataFrame(partes)
    df["effectiveDate"] = pd.to_datetime(df["effectiveDate"])
    df["percentRate"] = pd.to_numeric(df["percentRate"], errors="coerce")
    s = df.set_index("effectiveDate")["percentRate"].sort_index()
    return s[~s.index.duplicated(keep="last")]


def _fed_funds_fred(inicio: date) -> pd.Series:
    """Fed Funds efetivo diário (FRED, série DFF), em % a.a."""
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF"
    r = _get_com_retentativas(url, HEADERS_NAVEGADOR)
    df = pd.read_csv(io.StringIO(r.text))
    col_data, col_valor = df.columns[0], df.columns[1]
    df[col_data] = pd.to_datetime(df[col_data])
    df[col_valor] = pd.to_numeric(df[col_valor], errors="coerce")
    s = df.set_index(col_data)[col_valor].sort_index()
    return s[s.index >= pd.Timestamp(inicio)]


def baixar_fed_funds(inicio: date) -> pd.Series:
    """Fed Funds efetivo: tenta o NY Fed e, se falhar, o FRED."""
    for nome, funcao in (("NY Fed", _fed_funds_nyfed), ("FRED", _fed_funds_fred)):
        try:
            s = funcao(inicio)
            print(f"  Fed Funds obtido via {nome}.")
            return s.rename("fed_funds")
        except Exception as erro:
            print(f"  Falha ao baixar do {nome}: {erro}")
    raise RuntimeError("Não foi possível baixar o Fed Funds de nenhuma fonte.")


def coletar() -> pd.DataFrame:
    print("Baixando séries do Banco Central...")
    series = {nome: baixar_sgs(cod, INICIO) for nome, cod in SERIES_SGS.items()}
    print("Baixando expectativas do Focus...")
    series["ipca_esperado_12m"] = baixar_focus_ipca_12m(INICIO)
    print("Baixando Fed Funds (FRED)...")
    series["fed_funds"] = baixar_fed_funds(INICIO)

    # Base diária: usa os dias com cotação do dólar e preenche as demais
    # séries (mensais/semanais) com o último valor conhecido.
    base = series["usdbrl"].to_frame("usdbrl")
    for nome, s in series.items():
        if nome == "usdbrl":
            continue
        s = s[~s.index.duplicated(keep="last")]
        base = base.join(s.rename(nome), how="outer")
    base = base.sort_index().ffill()
    base = base.loc[base["usdbrl"].notna()]
    base = base.loc[base.index.isin(series["usdbrl"].index)]
    return base


# ---------------------------------------------------------------------------
# Indicadores
# ---------------------------------------------------------------------------
def calcular_indicadores(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # Juro real ex-ante: Selic meta deflacionada pela inflação esperada (Fisher)
    out["juro_real_ex_ante"] = (
        (1 + out["selic_meta"] / 100) / (1 + out["ipca_esperado_12m"] / 100) - 1
    ) * 100

    # Diferencial de juros Brasil - EUA (p.p.)
    out["diferencial_br_eua"] = out["selic_meta"] - out["fed_funds"]

    # Volatilidade realizada do câmbio: desvio-padrão dos retornos
    # logarítmicos em 21 dias úteis, anualizado (% a.a.)
    ret = np.log(out["usdbrl"]).diff()
    out["vol_cambio_21d"] = ret.rolling(21).std() * np.sqrt(252) * 100

    return out


def dolar_a_termo(df: pd.DataFrame, prazos_meses=(1, 3, 6, 12)) -> pd.DataFrame:
    """Dólar a termo teórico pela paridade coberta de juros:
    F = S x (1 + i_BR)^t / (1 + i_EUA)^t

    Simplificação: usa a Selic meta e o Fed Funds como proxies das taxas
    para todos os prazos (curva plana). Na prática, a mesa usa a curva de
    DI futuro e o cupom cambial."""
    ult = df.dropna(subset=["usdbrl", "selic_meta", "fed_funds"]).iloc[-1]
    spot = ult["usdbrl"]
    i_br = ult["selic_meta"] / 100
    i_us = ult["fed_funds"] / 100

    linhas = []
    for m in prazos_meses:
        t = m / 12
        termo = spot * (1 + i_br) ** t / (1 + i_us) ** t
        linhas.append({
            "prazo_meses": m,
            "spot": round(spot, 4),
            "termo_teorico": round(termo, 4),
            "pontos_forward": round((termo - spot) * 10000, 1),
            "premio_pct": round((termo / spot - 1) * 100, 2),
        })
    tabela = pd.DataFrame(linhas)
    tabela.attrs["data_ref"] = ult.name.date()
    return tabela


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------
def _estilo(ax, titulo, ylabel):
    ax.set_title(titulo, fontsize=12, loc="left", fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)


def _rodape(fig, texto):
    fig.text(0.01, 0.01, texto, fontsize=8, color="gray")


def grafico_juros(df):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df.index, df["selic_meta"], label="Selic meta", lw=2)
    ax.plot(df.index, df["ipca_esperado_12m"], label="IPCA esperado 12m (Focus)", lw=1.5)
    ax.plot(df.index, df["juro_real_ex_ante"], label="Juro real ex-ante", lw=2)
    ax.axhline(0, color="black", lw=0.8)
    _estilo(ax, "Selic, inflação esperada e juro real ex-ante", "% a.a.")
    ax.legend(frameon=False)
    _rodape(fig, "Fonte: BCB (SGS e Focus). Elaboração própria.")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(PASTA_GRAFICOS / "1_juros.png", dpi=150)
    plt.close(fig)


def grafico_diferencial_cambio(df):
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(df.index, df["diferencial_br_eua"], color="tab:blue", lw=2,
             label="Diferencial Selic - Fed Funds (p.p.)")
    _estilo(ax1, "Diferencial de juros Brasil-EUA e dólar", "p.p.")
    ax2 = ax1.twinx()
    ax2.plot(df.index, df["usdbrl"], color="tab:green", lw=1.2, label="USD/BRL")
    ax2.set_ylabel(r"R\$/US\$")
    ax2.spines["top"].set_visible(False)
    l1, r1 = ax1.get_legend_handles_labels()
    l2, r2 = ax2.get_legend_handles_labels()
    ax1.legend(l1 + l2, r1 + r2, frameon=False, loc="upper left")
    _rodape(fig, "Fontes: BCB (SGS) e Federal Reserve. Elaboração própria.")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(PASTA_GRAFICOS / "2_diferencial_cambio.png", dpi=150)
    plt.close(fig)


def grafico_volatilidade(df):
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df.index, df["vol_cambio_21d"], color="tab:red", lw=1.5)
    media = df["vol_cambio_21d"].mean()
    ax.axhline(media, color="gray", ls="--", lw=1, label=f"Média do período ({media:.1f}%)")
    _estilo(ax, "Volatilidade realizada do USD/BRL (21 dias úteis, anualizada)", "% a.a.")
    ax.legend(frameon=False)
    _rodape(fig, "Fonte: BCB (SGS). Elaboração própria.")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(PASTA_GRAFICOS / "3_volatilidade_cambio.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
def resumo(df, termo):
    u = df.dropna().iloc[-1]
    print("\n" + "=" * 60)
    print(f"RESUMO — dados até {df.index[-1]:%d/%m/%Y}")
    print("=" * 60)
    print(f"Selic meta:                {u['selic_meta']:6.2f}% a.a.")
    print(f"IPCA esperado 12m (Focus): {u['ipca_esperado_12m']:6.2f}%")
    print(f"Juro real ex-ante:         {u['juro_real_ex_ante']:6.2f}% a.a.")
    print(f"Fed Funds:                 {u['fed_funds']:6.2f}% a.a.")
    print(f"Diferencial BR-EUA:        {u['diferencial_br_eua']:6.2f} p.p.")
    print(f"USD/BRL:                   {u['usdbrl']:6.4f}")
    print(f"Vol. câmbio 21d:           {u['vol_cambio_21d']:6.2f}% a.a.")
    print("\nDólar a termo teórico (paridade coberta):")
    print(termo.to_string(index=False))


def main():
    PASTA_DADOS.mkdir(exist_ok=True)
    PASTA_GRAFICOS.mkdir(exist_ok=True)

    dados = coletar()
    ind = calcular_indicadores(dados)
    termo = dolar_a_termo(ind)

    ind.to_csv(PASTA_DADOS / "indicadores_diarios.csv", float_format="%.4f")
    termo.to_csv(PASTA_DADOS / "dolar_a_termo.csv", index=False)

    grafico_juros(ind)
    grafico_diferencial_cambio(ind)
    grafico_volatilidade(ind)

    resumo(ind, termo)
    print(f"\nGráficos salvos em /{PASTA_GRAFICOS} e dados em /{PASTA_DADOS}.")


if __name__ == "__main__":
    main()
