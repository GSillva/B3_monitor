# -*- coding: utf-8 -*-

import os
import time
import math
from datetime import datetime, date
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
from openpyxl import load_workbook



TIMEZONE = ZoneInfo("America/Sao_Paulo")
ARQUIVO_EXCEL = "monitor_b3_acoes.xlsx"

# 10 empresas brasileiras relevantes e líquidas para acompanhar
TICKERS = {
    "VALE3": "VALE3.SA",
    "PETR4": "PETR4.SA",
    "PETR3": "PETR3.SA",
    "ITUB4": "ITUB4.SA",
    "BBDC4": "BBDC4.SA",
    "BBAS3": "BBAS3.SA",
    "B3SA3": "B3SA3.SA",
    "ABEV3": "ABEV3.SA",
    "WEGE3": "WEGE3.SA",
    "RENT3": "RENT3.SA",
}

HORA_INICIO = 10   # 10:00
HORA_FIM = 16      # última coleta cheia às 16:00

# Feriados nacionais - Formato: "MM-DD"
FERIADOS_FIXOS = {
    "01-01",  # Confraternização Universal
    "04-21",  # Tiradentes
    "05-01",  # Dia do Trabalho
    "09-07",  # Independência
    "10-12",  # Nossa Senhora Aparecida
    "11-02",  # Finados
    "11-15",  # Proclamação da República
    "12-25",  # Natal
}

# FUNÇÕES 

def agora_sp() -> datetime:
    return datetime.now(TIMEZONE)

def eh_feriado_nacional(data_ref: date) -> bool:
    chave = data_ref.strftime("%m-%d")
    return chave in FERIADOS_FIXOS

def mercado_aberto(dt: datetime) -> bool:
    # segunda=0 ... domingo=6
    if dt.weekday() >= 5:
        return False

    if eh_feriado_nacional(dt.date()):
        return False

    # Coletas em hora cheia entre 10h e 16h
    return HORA_INICIO <= dt.hour <= HORA_FIM

def proxima_hora_cheia(dt: datetime) -> datetime:
    if dt.minute == 0 and dt.second == 0:
        return dt.replace(microsecond=0)

    prox = dt.replace(minute=0, second=0, microsecond=0)
    from datetime import timedelta
    prox += timedelta(hours=1)
    return prox

def segundos_ate_proxima_execucao() -> int:
    agora = agora_sp()
    prox = proxima_hora_cheia(agora)
    delta = (prox - agora).total_seconds()
    return max(1, int(delta))

def valor_seguro(x):
    if x is None:
        return None
    try:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
    except Exception:
        pass
    return x

def baixar_snapshot(ticker_yf: str) -> dict:
    tk = yf.Ticker(ticker_yf)

    # fast_info costuma ser mais estável/rápido
    fast = {}
    try:
        fast = dict(tk.fast_info)
    except Exception:
        fast = {}

    info = {}
    try:
        info = tk.info if isinstance(tk.info, dict) else {}
    except Exception:
        info = {}

    # histórico intraday de 5 dias em 1h para pico/mínima do dia
    hist = pd.DataFrame()
    try:
        hist = tk.history(period="5d", interval="1h", auto_adjust=False, prepost=False)
    except Exception:
        hist = pd.DataFrame()

    return {
        "fast_info": fast,
        "info": info,
        "hist_1h": hist,
    }

def extrair_linha_horaria(codigo: str, ticker_yf: str, snapshot: dict, momento: datetime) -> dict:
    fast = snapshot.get("fast_info", {})
    info = snapshot.get("info", {})
    hist = snapshot.get("hist_1h", pd.DataFrame())

    # tenta usar último candle intraday disponível
    last_open = last_high = last_low = last_close = last_volume = None
    candle_time = None

    if not hist.empty:
        hist_local = hist.copy()

        # garante timezone
        if hist_local.index.tz is None:
            hist_local.index = hist_local.index.tz_localize("UTC").tz_convert(TIMEZONE)
        else:
            hist_local.index = hist_local.index.tz_convert(TIMEZONE)

        hoje = momento.date()
        hist_hoje = hist_local[hist_local.index.date == hoje]

        if not hist_hoje.empty:
            ultima = hist_hoje.iloc[-1]
            candle_time = hist_hoje.index[-1]
            last_open = valor_seguro(float(ultima.get("Open"))) if pd.notna(ultima.get("Open")) else None
            last_high = valor_seguro(float(ultima.get("High"))) if pd.notna(ultima.get("High")) else None
            last_low = valor_seguro(float(ultima.get("Low"))) if pd.notna(ultima.get("Low")) else None
            last_close = valor_seguro(float(ultima.get("Close"))) if pd.notna(ultima.get("Close")) else None
            last_volume = valor_seguro(float(ultima.get("Volume"))) if pd.notna(ultima.get("Volume")) else None

    linha = {
        "timestamp_coleta": momento.strftime("%Y-%m-%d %H:%M:%S"),
        "ticker": codigo,
        "ticker_yf": ticker_yf,
        "horario_ultimo_candle": candle_time.strftime("%Y-%m-%d %H:%M:%S") if candle_time is not None else None,

        # Intraday 
        "open_1h": last_open,
        "high_1h": last_high,
        "low_1h": last_low,
        "close_1h": last_close,
        "volume_1h": last_volume,

        # fast_info
        "last_price": valor_seguro(fast.get("lastPrice")),
        "previous_close": valor_seguro(fast.get("previousClose")),
        "open_day": valor_seguro(fast.get("open")),
        "day_high": valor_seguro(fast.get("dayHigh")),
        "day_low": valor_seguro(fast.get("dayLow")),
        "day_volume": valor_seguro(fast.get("lastVolume")),
        "market_cap": valor_seguro(fast.get("marketCap")),
        "fifty_day_average": valor_seguro(fast.get("fiftyDayAverage")),
        "two_hundred_day_average": valor_seguro(fast.get("twoHundredDayAverage")),
        "year_high": valor_seguro(fast.get("yearHigh")),
        "year_low": valor_seguro(fast.get("yearLow")),

        # info extra
        "currency": valor_seguro(info.get("currency")),
        "exchange": valor_seguro(info.get("exchange")),
        "quote_type": valor_seguro(info.get("quoteType")),
        "short_name": valor_seguro(info.get("shortName")),
        "long_name": valor_seguro(info.get("longName")),
        "sector": valor_seguro(info.get("sector")),
        "industry": valor_seguro(info.get("industry")),
        "country": valor_seguro(info.get("country")),
        "website": valor_seguro(info.get("website")),
        "beta": valor_seguro(info.get("beta")),
        "trailing_pe": valor_seguro(info.get("trailingPE")),
        "forward_pe": valor_seguro(info.get("forwardPE")),
        "price_to_book": valor_seguro(info.get("priceToBook")),
        "dividend_yield": valor_seguro(info.get("dividendYield")),
        "payout_ratio": valor_seguro(info.get("payoutRatio")),
        "bid": valor_seguro(info.get("bid")),
        "ask": valor_seguro(info.get("ask")),
        "regular_market_volume": valor_seguro(info.get("regularMarketVolume")),
        "average_volume": valor_seguro(info.get("averageVolume")),
        "average_volume_10days": valor_seguro(info.get("averageVolume10days")),
        "shares_outstanding": valor_seguro(info.get("sharesOutstanding")),
        "float_shares": valor_seguro(info.get("floatShares")),
        "book_value": valor_seguro(info.get("bookValue")),
        "profit_margins": valor_seguro(info.get("profitMargins")),
        "ebitda_margins": valor_seguro(info.get("ebitdaMargins")),
        "operating_margins": valor_seguro(info.get("operatingMargins")),
        "return_on_assets": valor_seguro(info.get("returnOnAssets")),
        "return_on_equity": valor_seguro(info.get("returnOnEquity")),
        "revenue_growth": valor_seguro(info.get("revenueGrowth")),
        "earnings_growth": valor_seguro(info.get("earningsGrowth")),
        "gross_margins": valor_seguro(info.get("grossMargins")),
        "fifty_two_week_high": valor_seguro(info.get("fiftyTwoWeekHigh")),
        "fifty_two_week_low": valor_seguro(info.get("fiftyTwoWeekLow")),
        "target_mean_price": valor_seguro(info.get("targetMeanPrice")),
        "recommendation_key": valor_seguro(info.get("recommendationKey")),
        "recommendation_mean": valor_seguro(info.get("recommendationMean")),
    }

    return linha

def consolidar_resumo_diario(df_horario: pd.DataFrame) -> pd.DataFrame:
    if df_horario.empty:
        return pd.DataFrame()

    df = df_horario.copy()
    df["data"] = pd.to_datetime(df["timestamp_coleta"]).dt.date
    df["timestamp_dt"] = pd.to_datetime(df["timestamp_coleta"])

    def first_valid(series):
        serie = series.dropna()
        return serie.iloc[0] if not serie.empty else None

    def last_valid(series):
        serie = series.dropna()
        return serie.iloc[-1] if not serie.empty else None

    resumo = (
        df.sort_values(["ticker", "timestamp_dt"])
          .groupby(["data", "ticker"], as_index=False)
          .agg(
              abertura_dia=("open_day", first_valid),
              primeiro_preco=("last_price", first_valid),
              ultimo_preco=("last_price", last_valid),
              fechamento_parcial=("close_1h", last_valid),
              max_dia=("day_high", "max"),
              min_dia=("day_low", "min"),
              pico_intraday=("high_1h", "max"),
              fundo_intraday=("low_1h", "min"),
              volume_ultima_leitura=("day_volume", last_valid),
              volume_mercado_ultima_leitura=("regular_market_volume", last_valid),
              fechamento_anterior=("previous_close", last_valid),
              market_cap=("market_cap", last_valid),
              bid=("bid", last_valid),
              ask=("ask", last_valid),
              setor=("sector", last_valid),
              industria=("industry", last_valid),
              moeda=("currency", last_valid),
          )
    )

    return resumo

def salvar_excel(df_horario: pd.DataFrame, df_resumo: pd.DataFrame, df_config: pd.DataFrame) -> None:
    if not os.path.exists(ARQUIVO_EXCEL):
        with pd.ExcelWriter(ARQUIVO_EXCEL, engine="openpyxl") as writer:
            df_horario.to_excel(writer, sheet_name="dados_horarios", index=False)
            df_resumo.to_excel(writer, sheet_name="resumo_diario", index=False)
            df_config.to_excel(writer, sheet_name="config", index=False)
        return

    with pd.ExcelWriter(
        ARQUIVO_EXCEL,
        engine="openpyxl",
        mode="a",
        if_sheet_exists="replace"
    ) as writer:
        df_horario.to_excel(writer, sheet_name="dados_horarios", index=False)
        df_resumo.to_excel(writer, sheet_name="resumo_diario", index=False)
        df_config.to_excel(writer, sheet_name="config", index=False)

def carregar_historico_existente() -> pd.DataFrame:
    if not os.path.exists(ARQUIVO_EXCEL):
        return pd.DataFrame()

    try:
        return pd.read_excel(ARQUIVO_EXCEL, sheet_name="dados_horarios")
    except Exception:
        return pd.DataFrame()

def montar_df_config() -> pd.DataFrame:
    linhas = []
    for codigo, yf_code in TICKERS.items():
        linhas.append({
            "ticker": codigo,
            "ticker_yf": yf_code,
            "bolsa": "B3",
            "timezone": "America/Sao_Paulo",
            "coleta_horaria_regular": "10:00-16:00",
            "observacao": "Fonte gratuita via Yahoo Finance / yfinance; quantidade exata de negócios pode não estar disponível."
        })
    return pd.DataFrame(linhas)

def executar_coleta() -> None:
    momento = agora_sp()
    print(f"\n[{momento.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando coleta...")

    registros = []
    for codigo, ticker_yf in TICKERS.items():
        try:
            snapshot = baixar_snapshot(ticker_yf)
            linha = extrair_linha_horaria(codigo, ticker_yf, snapshot, momento)
            registros.append(linha)
            print(f"  OK - {codigo}")
        except Exception as e:
            print(f"  ERRO - {codigo}: {e}")

    if not registros:
        print("Nenhum dado coletado.")
        return

    df_novo = pd.DataFrame(registros)
    df_existente = carregar_historico_existente()

    if df_existente.empty:
        df_horario = df_novo.copy()
    else:
        df_horario = pd.concat([df_existente, df_novo], ignore_index=True)

        # evita duplicidade por timestamp + ticker
        df_horario = df_horario.drop_duplicates(
            subset=["timestamp_coleta", "ticker"],
            keep="last"
        )

    df_horario = df_horario.sort_values(["timestamp_coleta", "ticker"]).reset_index(drop=True)
    df_resumo = consolidar_resumo_diario(df_horario)
    df_config = montar_df_config()

    salvar_excel(df_horario, df_resumo, df_config)
    print(f"Arquivo atualizado: {ARQUIVO_EXCEL}")

def loop_principal() -> None:
    print("Monitor de ações da B3 iniciado.")
    print(f"Arquivo de saída: {ARQUIVO_EXCEL}")
    print("Aguardando horário de coleta...")

    while True:
        try:
            momento = agora_sp()

            if mercado_aberto(momento) and momento.minute == 0:
                executar_coleta()
                # evita coletar várias vezes na mesma hora
                time.sleep(65)
            else:
                restante = segundos_ate_proxima_execucao()
                print(
                    f"[{momento.strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"Fora da janela de coleta ou aguardando próxima hora cheia. "
                    f"Dormindo {restante}s..."
                )
                time.sleep(restante)

        except KeyboardInterrupt:
            print("\nEncerrado pelo usuário.")
            break
        except Exception as e:
            print(f"Erro no loop principal: {e}")
            time.sleep(60)

if __name__ == "__main__":
    loop_principal()

