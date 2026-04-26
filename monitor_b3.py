#Autores: Gabriel Aguiar (https://github.com/GSillva) e Leomax Filho (https://github.com/LeomaxFilho)
#Alterações recentes: Mudança do formato de arquivo e adição de resumo do dia
# -*- coding: utf-8 -*-

import logging
import math
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

TIMEZONE = ZoneInfo("America/Sao_Paulo")
DIR_DADOS = "dados_monitor"
LOG_FILE = os.path.join(DIR_DADOS, "monitor_acoes.log")

# Janela para disparo da coleta no horário do Brasil
# Com a lógica abaixo, coleta de 10:00 até 16:59
HORA_INICIO = 10
HORA_FIM = 17

CSV_HORARIO = os.path.join(DIR_DADOS, "dados_horarios.csv")
CSV_RESUMO = os.path.join(DIR_DADOS, "resumo_diario.csv")
CSV_CONFIG = os.path.join(DIR_DADOS, "config.csv")

os.makedirs(DIR_DADOS, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ─── TICKERS ──────────────────────────────────────────────────────────────────

TICKERS_B3 = {
    "ITUB4":  "ITUB4.SA",
    "BBDC4":  "BBDC4.SA",
    "BBDC3":  "BBDC3.SA",
    "BBAS3":  "BBAS3.SA",
    "SANB11": "SANB11.SA",
    "BPAC11": "BPAC11.SA",
    "PETR4":  "PETR4.SA",
    "PETR3":  "PETR3.SA",
    "PRIO3":  "PRIO3.SA",
    "CSAN3":  "CSAN3.SA",
    "UGPA3":  "UGPA3.SA",
    "VALE3":  "VALE3.SA",
    "GGBR4":  "GGBR4.SA",
    "CSNA3":  "CSNA3.SA",
    "ELET3":  "ELET3.SA",
    "ELET6":  "ELET6.SA",
    "CPFE3":  "CPFE3.SA",
    "SBSP3":  "SBSP3.SA",
    "CPLE6":  "CPLE6.SA",
    "ENGI11": "ENGI11.SA",
    "ABEV3":  "ABEV3.SA",
    "LREN3":  "LREN3.SA",
    "MGLU3":  "MGLU3.SA",
    "VVAR3":  "VVAR3.SA",
    "ASAI3":  "ASAI3.SA",
    "PCAR3":  "PCAR3.SA",
    "RDOR3":  "RDOR3.SA",
    "HAPV3":  "HAPV3.SA",
    "FLRY3":  "FLRY3.SA",
    "WEGE3":  "WEGE3.SA",
    "EMBR3":  "EMBR3.SA",
    "TOTS3":  "TOTS3.SA",
    "INTB3":  "INTB3.SA",
    "RENT3":  "RENT3.SA",
    "MOVI3":  "MOVI3.SA",
    "RAIL3":  "RAIL3.SA",
    "EZTC3":  "EZTC3.SA",
    "CYRE3":  "CYRE3.SA",
    "CCRO3":  "CCRO3.SA",
    "ECOR3":  "ECOR3.SA",
    "VIVT3":  "VIVT3.SA",
    "TIMS3":  "TIMS3.SA",
    "B3SA3":  "B3SA3.SA",
    "XPBR31": "XPBR31.SA",
    "SLCE3":  "SLCE3.SA",
    "AGRO3":  "AGRO3.SA",
}

TICKERS_GLOBAIS = {
    "NVDA":      "NVDA",
    "AAPL":      "AAPL",
    "MSFT":      "MSFT",
    "GOOGL":     "GOOGL",
    "AMZN":      "AMZN",
    "META":      "META",
    "TSLA":      "TSLA",
    "AVGO":      "AVGO",
    "ORCL":      "ORCL",
    "AMD":       "AMD",
    "BRK-B":     "BRK-B",
    "JPM":       "JPM",
    "V":         "V",
    "MA":        "MA",
    "BAC":       "BAC",
    "LLY":       "LLY",
    "JNJ":       "JNJ",
    "UNH":       "UNH",
    "XOM":       "XOM",
    "CVX":       "CVX",
    "WMT":       "WMT",
    "COST":      "COST",
    "PG":        "PG",
    "TSM":       "TSM",
    "ASML":      "ASML",
    "SAP":       "SAP",
    "TM":        "TM",
    "BABA":      "BABA",
    "2222.SR":   "2222.SR",
    "9988.HK":   "9988.HK",
    "005930.KS": "005930.KS",
}

TODOS_TICKERS: dict[str, str] = {**TICKERS_B3, **TICKERS_GLOBAIS}

FERIADOS_FIXOS_BR = {
    "01-01",
    "04-21",
    "05-01",
    "09-07",
    "10-12",
    "11-02",
    "11-15",
    "12-25",
}

# ─── UTILITÁRIOS ──────────────────────────────────────────────────────────────

def agora_sp() -> datetime:
    return datetime.now(TIMEZONE)

def eh_feriado_br(d: date) -> bool:
    return d.strftime("%m-%d") in FERIADOS_FIXOS_BR

def janela_coleta(dt: datetime) -> bool:
    if dt.weekday() >= 5:
        return False
    if eh_feriado_br(dt.date()):
        return False
    return HORA_INICIO <= dt.hour < HORA_FIM

def valor_seguro(x):
    if x is None:
        return None
    try:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
    except Exception:
        pass
    return x

def _safe_float(row, col: str):
    val = row.get(col)
    return valor_seguro(float(val)) if val is not None and pd.notna(val) else None

# ─── COLETA ───────────────────────────────────────────────────────────────────

def baixar_snapshot(ticker_yf: str) -> dict:
    tk = yf.Ticker(ticker_yf)
    fast, info, hist = {}, {}, pd.DataFrame()

    try:
        fast = dict(tk.fast_info)
    except Exception as exc:
        log.warning("fast_info indisponível para %s: %s", ticker_yf, exc)

    try:
        raw = tk.info
        if isinstance(raw, dict):
            info = raw
    except Exception as exc:
        log.warning("info indisponível para %s: %s", ticker_yf, exc)

    try:
        hist = tk.history(period="5d", interval="1h", auto_adjust=False, prepost=False)
    except Exception as exc:
        log.warning("histórico indisponível para %s: %s", ticker_yf, exc)

    return {"fast_info": fast, "info": info, "hist_1h": hist}

def extrair_linha(codigo: str, ticker_yf: str, snap: dict, momento: datetime) -> dict:
    fast = snap.get("fast_info", {})
    info = snap.get("info", {})
    hist = snap.get("hist_1h", pd.DataFrame())

    last_open = last_high = last_low = last_close = last_volume = None
    candle_time = None

    if not hist.empty:
        h = hist.copy()
        if h.index.tz is None:
            h.index = h.index.tz_localize("UTC").tz_convert(TIMEZONE)
        else:
            h.index = h.index.tz_convert(TIMEZONE)

        hoje = h[h.index.date == momento.date()]
        if not hoje.empty:
            ult = hoje.iloc[-1]
            candle_time = hoje.index[-1]
            last_open = _safe_float(ult, "Open")
            last_high = _safe_float(ult, "High")
            last_low = _safe_float(ult, "Low")
            last_close = _safe_float(ult, "Close")
            last_volume = _safe_float(ult, "Volume")

    return {
        "timestamp_coleta":    momento.strftime("%Y-%m-%d %H:%M:%S"),
        "mercado":             "B3" if ticker_yf.endswith(".SA") else "Global",
        "ticker":              codigo,
        "ticker_yf":           ticker_yf,
        "candle_time":         candle_time.strftime("%Y-%m-%d %H:%M:%S") if candle_time else None,
        "open_1h":             last_open,
        "high_1h":             last_high,
        "low_1h":              last_low,
        "close_1h":            last_close,
        "volume_1h":           last_volume,
        "last_price":          valor_seguro(fast.get("lastPrice")),
        "previous_close":      valor_seguro(fast.get("previousClose")),
        "open_day":            valor_seguro(fast.get("open")),
        "day_high":            valor_seguro(fast.get("dayHigh")),
        "day_low":             valor_seguro(fast.get("dayLow")),
        "day_volume":          valor_seguro(fast.get("lastVolume")),
        "market_cap":          valor_seguro(fast.get("marketCap")),
        "fifty_day_avg":       valor_seguro(fast.get("fiftyDayAverage")),
        "two_hundred_day_avg": valor_seguro(fast.get("twoHundredDayAverage")),
        "year_high":           valor_seguro(fast.get("yearHigh")),
        "year_low":            valor_seguro(fast.get("yearLow")),
        "currency":            valor_seguro(info.get("currency")),
        "exchange":            valor_seguro(info.get("exchange")),
        "short_name":          valor_seguro(info.get("shortName")),
        "sector":              valor_seguro(info.get("sector")),
        "industry":            valor_seguro(info.get("industry")),
        "country":             valor_seguro(info.get("country")),
        "beta":                valor_seguro(info.get("beta")),
        "trailing_pe":         valor_seguro(info.get("trailingPE")),
        "forward_pe":          valor_seguro(info.get("forwardPE")),
        "price_to_book":       valor_seguro(info.get("priceToBook")),
        "dividend_yield":      valor_seguro(info.get("dividendYield")),
        "payout_ratio":        valor_seguro(info.get("payoutRatio")),
        "bid":                 valor_seguro(info.get("bid")),
        "ask":                 valor_seguro(info.get("ask")),
        "regular_mkt_volume":  valor_seguro(info.get("regularMarketVolume")),
        "avg_volume":          valor_seguro(info.get("averageVolume")),
        "avg_volume_10d":      valor_seguro(info.get("averageVolume10days")),
        "shares_outstanding":  valor_seguro(info.get("sharesOutstanding")),
        "float_shares":        valor_seguro(info.get("floatShares")),
        "book_value":          valor_seguro(info.get("bookValue")),
        "profit_margins":      valor_seguro(info.get("profitMargins")),
        "ebitda_margins":      valor_seguro(info.get("ebitdaMargins")),
        "operating_margins":   valor_seguro(info.get("operatingMargins")),
        "gross_margins":       valor_seguro(info.get("grossMargins")),
        "return_on_assets":    valor_seguro(info.get("returnOnAssets")),
        "return_on_equity":    valor_seguro(info.get("returnOnEquity")),
        "revenue_growth":      valor_seguro(info.get("revenueGrowth")),
        "earnings_growth":     valor_seguro(info.get("earningsGrowth")),
        "target_mean_price":   valor_seguro(info.get("targetMeanPrice")),
        "recommendation":      valor_seguro(info.get("recommendationKey")),
        "recommendation_mean": valor_seguro(info.get("recommendationMean")),
    }

# ─── RESUMO DIÁRIO ────────────────────────────────────────────────────────────

def consolidar_resumo(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    df = df.copy()

    colunas_numericas = [
        "open_1h", "high_1h", "low_1h", "close_1h", "volume_1h",
        "last_price", "previous_close", "open_day", "day_high", "day_low",
        "day_volume", "market_cap", "fifty_day_avg", "two_hundred_day_avg",
        "year_high", "year_low", "beta", "trailing_pe", "forward_pe",
        "price_to_book", "dividend_yield", "payout_ratio", "bid", "ask",
        "regular_mkt_volume", "avg_volume", "avg_volume_10d",
        "shares_outstanding", "float_shares", "book_value",
        "profit_margins", "ebitda_margins", "operating_margins",
        "gross_margins", "return_on_assets", "return_on_equity",
        "revenue_growth", "earnings_growth", "target_mean_price",
        "recommendation_mean",
    ]

    for col in colunas_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["data"] = pd.to_datetime(df["timestamp_coleta"]).dt.date
    df["timestamp_dt"] = pd.to_datetime(df["timestamp_coleta"])

    def first_valid(s):
        s = s.dropna()
        return s.iloc[0] if not s.empty else None

    def last_valid(s):
        s = s.dropna()
        return s.iloc[-1] if not s.empty else None

    resumo = (
        df.sort_values(["ticker", "timestamp_dt"])
          .groupby(["data", "mercado", "ticker"], as_index=False)
          .agg(
              abertura_dia        = ("open_day",           first_valid),
              primeiro_preco      = ("last_price",         first_valid),
              ultimo_preco        = ("last_price",         last_valid),
              fechamento_parcial  = ("close_1h",           last_valid),
              max_dia             = ("day_high",           "max"),
              min_dia             = ("day_low",            "min"),
              pico_intraday       = ("high_1h",            "max"),
              fundo_intraday      = ("low_1h",             "min"),
              volume_ultima       = ("day_volume",         last_valid),
              volume_mkt_ultima   = ("regular_mkt_volume", last_valid),
              fechamento_anterior = ("previous_close",     last_valid),
              market_cap          = ("market_cap",         last_valid),
              bid                 = ("bid",                last_valid),
              ask                 = ("ask",                last_valid),
              setor               = ("sector",             last_valid),
              industria           = ("industry",           last_valid),
              moeda               = ("currency",           last_valid),
              trailing_pe         = ("trailing_pe",        last_valid),
              dividend_yield      = ("dividend_yield",     last_valid),
              beta                = ("beta",               last_valid),
          )
    )

    resumo["variacao_pct"] = (
        (resumo["ultimo_preco"] - resumo["fechamento_anterior"])
        / resumo["fechamento_anterior"]
        * 100
    ).round(2)

    return resumo

# ─── CSV ──────────────────────────────────────────────────────────────────────

def carregar_horario() -> pd.DataFrame:
    if not os.path.exists(CSV_HORARIO):
        return pd.DataFrame()

    try:
        return pd.read_csv(CSV_HORARIO, dtype=str)
    except Exception as exc:
        log.error("Falha ao carregar histórico: %s", exc)
        return pd.DataFrame()

def salvar_csvs(df_horario: pd.DataFrame, df_resumo: pd.DataFrame, df_config: pd.DataFrame) -> None:
    df_horario.to_csv(CSV_HORARIO, index=False, encoding="utf-8")
    df_resumo.to_csv(CSV_RESUMO, index=False, encoding="utf-8")
    df_config.to_csv(CSV_CONFIG, index=False, encoding="utf-8")

def montar_config() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ticker": codigo,
            "ticker_yf": yf_code,
            "mercado": "B3" if yf_code.endswith(".SA") else "Global",
            "janela": f"{HORA_INICIO}:00-{HORA_FIM - 1}:59",
            "fonte": "Yahoo Finance (yfinance) - dados podem ter atraso",
        }
        for codigo, yf_code in TODOS_TICKERS.items()
    ])

# ─── COLETA PRINCIPAL ─────────────────────────────────────────────────────────

def executar_coleta() -> None:
    momento = agora_sp()
    log.info("Iniciando coleta — %d tickers", len(TODOS_TICKERS))

    registros = []
    for codigo, ticker_yf in TODOS_TICKERS.items():
        try:
            snap = baixar_snapshot(ticker_yf)
            linha = extrair_linha(codigo, ticker_yf, snap, momento)
            registros.append(linha)
            log.info("OK %s", codigo)
        except Exception as exc:
            log.warning("ERRO %s: %s", codigo, exc)

    if not registros:
        log.warning("Nenhum dado coletado nesta rodada.")
        return

    df_novo = pd.DataFrame(registros)
    df_existente = carregar_horario()

    if df_existente.empty:
        df_horario = df_novo.copy()
    else:
        df_horario = (
            pd.concat([df_existente, df_novo], ignore_index=True)
              .drop_duplicates(subset=["timestamp_coleta", "ticker"], keep="last")
        )

    df_horario = df_horario.sort_values(
        ["timestamp_coleta", "mercado", "ticker"]
    ).reset_index(drop=True)

    df_resumo = consolidar_resumo(df_horario)
    df_config = montar_config()

    salvar_csvs(df_horario, df_resumo, df_config)
    log.info(
        "CSVs salvos em '%s/' (linhas históricas: %d)",
        DIR_DADOS,
        len(df_horario),
    )

def main() -> None:
    momento = agora_sp()
    log.info("Execução iniciada em %s", momento.strftime("%Y-%m-%d %H:%M:%S"))

    if janela_coleta(momento):
        executar_coleta()
    else:
        log.info("Fora da janela de coleta. Nenhuma ação executada.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log.exception("Erro fatal na execução: %s", exc)
        raise
