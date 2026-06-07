import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  BIST PROFESYONEL KOKPİT  V16.0  — tek dosya                              ║
# ║  Sayfa yapısı: sidebar + col[2.5 / 5 / 2.5]  —  değiştirilemez           ║
# ║                                                                            ║
# ║  V16 yenilikleri (V15 → V16):                                             ║
# ║   1. DI Spread Filtresi   (+DI - -DI > 10 → gerçek trend ayrışması)      ║
# ║   2. OBV Breakout         (OBV yeni 20-bar zirvesi → kurumsal giriş)     ║
# ║   3. VWAP Filtresi        (Close > VWAP → kurumsal maliyet üstü)         ║
# ║   4. Kompozit skor 19 → 22 filtre                                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

st.set_page_config(
    page_title="BIST Kokpit V16.0",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── WATCHLIST KALICILIĞI ──────────────────────────────────────────────────────
BIST_30 = [
    "AKBNK","ALARK","ARCLK","ASTOR","BIMAS","BRSAN","EKGYO","ENKAI","EREGL",
    "FROTO","GARAN","GUBRF","HEKTS","ISCTR","KCHOL","KONTR","KRDMD","OYAKC",
    "PGSUS","PETKM","SAHOL","SASA","SISE","TCELL","THYAO","TKFEN","TOASO",
    "TUPRS","VAKBN","YKBNK"
]

def load_watchlist() -> list:
    try:
        raw = st.query_params.get("wl", "")
        if raw:
            tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
            if tickers:
                return tickers
    except Exception:
        pass
    return BIST_30.copy()

def save_watchlist(wl: list):
    try:
        st.query_params["wl"] = ",".join(sorted(set(wl)))
    except Exception:
        pass

if "watchlist"    not in st.session_state:
    st.session_state.watchlist    = load_watchlist()
if "event_risks"  not in st.session_state:
    st.session_state.event_risks  = {}
if "scan_rows"    not in st.session_state:
    st.session_state.scan_rows    = []
if "breadth"      not in st.session_state:
    st.session_state.breadth      = None

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
section.main > div { padding-top: 0.35rem !important; }

.scanner-wrapper {
    max-height: 390px; overflow-y: auto; overflow-x: hidden;
    border: 1px solid #2d3a50; border-radius: 6px;
}
.scanner-table {
    width: 100%; border-collapse: collapse;
    font-size: 10.5px; font-family: 'Courier New', monospace;
    table-layout: fixed;
}
.scanner-table th {
    background: #1e2535; color: #94a3b8; font-size: 9px; font-weight: 600;
    letter-spacing: 0.3px; padding: 3px 2px; text-align: center;
    border-bottom: 1px solid #2d3a50;
    position: sticky; top: 0; z-index: 1;
    overflow: hidden; white-space: nowrap;
}
.scanner-table td {
    padding: 3px 2px; text-align: center;
    border-bottom: 1px solid #1a2030; color: #e2e8f0;
    overflow: hidden; white-space: nowrap;
}
.scanner-table td.tkr { text-align:left; padding-left:5px; font-weight:600; color:#cbd5e1; }
.scanner-table tr:hover td { background: #1e2a3a; }

.regime-banner, .freshness-banner, .htf-banner, .health-banner {
    padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 700;
    margin-bottom: 6px; text-align: center; letter-spacing: 0.3px;
}
.rb-bull { background:#14532d; color:#86efac; border:1px solid #22c55e; }
.rb-bear { background:#450a0a; color:#fca5a5; border:1px solid #ef4444; }
.rb-none { background:#1c1f2e; color:#94a3b8; border:1px solid #374151; }
.fb-green  { background:#052e16; color:#86efac; border:1px solid #22c55e; }
.fb-yellow { background:#1c1a08; color:#fde047; border:1px solid #ca8a04; }
.fb-red    { background:#450a0a; color:#fca5a5; border:1px solid #ef4444; }
.htf-bull  { background:#0f2a1a; color:#86efac; border:1px solid #16a34a; }
.htf-bear  { background:#2a0a0a; color:#fca5a5; border:1px solid #dc2626; }
.htf-none  { background:#1c1f2e; color:#94a3b8; border:1px solid #374151; }

/* Market Health Score banner */
.mhs-5   { background:#052e16; color:#4ade80; border:2px solid #22c55e; }
.mhs-4   { background:#0f2a1a; color:#86efac; border:1px solid #16a34a; }
.mhs-3   { background:#1c1a08; color:#fde047; border:1px solid #ca8a04; }
.mhs-2   { background:#2a1a08; color:#fb923c; border:1px solid #f97316; }
.mhs-1   { background:#2a0a0a; color:#fca5a5; border:1px solid #dc2626; }
.mhs-0   { background:#1c1f2e; color:#6b7280; border:1px solid #374151; }

.breadth-wrap { background:#0d1421; border-radius:6px; padding:6px 10px; margin-bottom:5px; }
.breadth-wrap .bw-lbl { font-size:9px; color:#6b7594; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:3px; }
.bar-outer { background:#1e2535; border-radius:4px; height:10px; width:100%; overflow:hidden; }
.bw-nums { display:flex; justify-content:space-between; margin-top:3px; font-size:10px; font-family:monospace; }

.mg { display:grid; grid-template-columns:1fr 1fr; gap:4px; margin-bottom:5px; }
.mc { background:#1a1f2e; border:1px solid #2d3448; border-radius:6px; padding:6px 8px; text-align:center; }
.mc .lb { font-size:9px; color:#6b7594; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:1px; }
.mc .vl { font-size:13px; font-weight:700; color:#e2e8f0; font-family:'Courier New',monospace; }
.mc .vl.up { color:#22c55e; } .mc .vl.dn { color:#ef4444; } .mc .vl.wn { color:#f59e0b; }

.karar-card { border-radius:8px; padding:10px 14px; margin-bottom:8px; text-align:center; }
.karar-card .karar-lbl { font-size:9px; color:#94a3b8; text-transform:uppercase; letter-spacing:0.6px; }
.karar-card .karar-val { font-size:17px; font-weight:800; letter-spacing:0.5px; margin-top:2px; }
.kc-al   { background:#052e16; border:2px solid #22c55e; } .kc-al   .karar-val { color:#4ade80; }
.kc-pos  { background:#0f2a1a; border:1px solid #16a34a; } .kc-pos  .karar-val { color:#86efac; }
.kc-notr { background:#1c1a08; border:1px solid #ca8a04; } .kc-notr .karar-val { color:#fde047; }
.kc-sat  { background:#2a0a0a; border:1px solid #dc2626; } .kc-sat  .karar-val { color:#fca5a5; }

.sr {
    display:flex; justify-content:space-between; align-items:center;
    background:#0d1421; border-radius:5px; padding:5px 9px; margin-bottom:3px;
    font-size:11px; border-left:3px solid transparent;
}
.sr.ok  { border-left-color:#22c55e; }
.sr.nok { border-left-color:#ef4444; }
.sr.unk { border-left-color:#f59e0b; }
.sr .sl { color:#94a3b8; font-size:10.5px; }
.sr .sv { font-weight:700; font-family:monospace; font-size:11px; }
.sr .sv.up { color:#4ade80; } .sr .sv.dn { color:#f87171; } .sr .sv.wn { color:#fbbf24; }

.sec-divider {
    font-size:9px; color:#4a5568; text-transform:uppercase; letter-spacing:1px;
    margin:8px 0 4px 0; border-bottom:1px solid #1e2535; padding-bottom:2px;
}
.level-row {
    display:flex; justify-content:space-between; align-items:center;
    padding:4px 9px; margin-bottom:2px; border-radius:4px;
    font-size:10.5px; font-family:'Courier New',monospace;
}
.level-row.res { background:#2a0a0a; border-left:3px solid #ef4444; }
.level-row.sup { background:#052e16; border-left:3px solid #22c55e; }
.level-row.cur { background:#0f1f35; border-left:3px solid #38bdf8; }
.level-row.vwap { background:#0f1a35; border-left:3px solid #a78bfa; }
.level-row .lv-lbl { color:#94a3b8; font-size:9.5px; }
.level-row.res .lv-val { color:#f87171; font-weight:700; }
.level-row.sup .lv-val { color:#4ade80; font-weight:700; }
.level-row.cur .lv-val { color:#38bdf8; font-weight:700; }
.level-row.vwap .lv-val { color:#a78bfa; font-weight:700; }
.level-row .lv-dist { font-size:9.5px; color:#6b7594; }

.rr-bar-wrap, .vol-bar-wrap { background:#0d1421; border-radius:6px; padding:8px 10px; margin-bottom:5px; }
.rr-bar-wrap .rr-lbl, .vol-bar-wrap .vb-lbl {
    font-size:9px; color:#6b7594; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;
}
.rr-nums, .vb-nums { display:flex; justify-content:space-between; margin-top:4px; font-size:10px; font-family:monospace; }
.rr-nums .rr-r { color:#f87171; } .rr-nums .rr-rw { color:#4ade80; }
.vb-nums { color:#94a3b8; }

/* MHS progress bar */
.mhs-wrap { background:#0d1421; border-radius:6px; padding:8px 10px; margin-bottom:6px; }
.mhs-wrap .mhs-lbl { font-size:9px; color:#6b7594; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px; }
.mhs-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:3px; font-size:10px; }
.mhs-row .mhs-item { color:#94a3b8; }
.mhs-row .mhs-check { font-weight:700; }

/* V16: VWAP badge */
.vwap-badge {
    display:inline-block; background:#1a1040; border:1px solid #7c3aed;
    color:#a78bfa; font-size:9px; font-weight:700; border-radius:3px;
    padding:1px 5px; letter-spacing:0.3px;
}
</style>
""", unsafe_allow_html=True)

# ── SABITLER ─────────────────────────────────────────────────────────────────
SQUEEZE_LOOKBACK  = 250
REGIME_SMA        = 50
RISK_FULL         = 0.02
RISK_HALF         = 0.01
RISK_OFF          = 0.005
ATR_MULT          = 1.5
RVOL_THRESHOLD    = 1.5
RS_SLOPE_BARS     = 5
FRESHNESS_WARN    = 20
FRESHNESS_RED     = 40
ATR_PCT_MIN       = 0.01
ATR_PCT_MAX       = 0.06
TRADE_COST        = 0.003
BREAKOUT_BARS     = 20
SR_LOOKBACK       = 200
ADX_PERIOD        = 14
ADX_THRESHOLD     = 25
VOL_PCT_LOOKBACK  = 250
ATR_EXP_BARS      = 5
BREADTH_NEUTRAL   = 55
GAP_MAX_PCT       = 0.04
RSI_PCT_LOOKBACK  = 252
ADX_SLOPE_BARS    = 3
ATR_PCT_LOOKBACK  = 250
VCP_LOOKBACK      = 60
# ── V16 yeni sabitler ────────────────────────────────────────────────────────
DI_SPREAD_MIN     = 10      # V16: +DI - -DI farkı eşiği
OBV_BRK_LOOKBACK  = 20      # V16: OBV zirve kırılımı penceresi

# ── V15: Sektör haritası ─────────────────────────────────────────────────────
SEKTOR_MAP = {
    "AKBNK":"XBANK.IS","GARAN":"XBANK.IS","ISCTR":"XBANK.IS",
    "VAKBN":"XBANK.IS","YKBNK":"XBANK.IS","ALBRK":"XBANK.IS",
    "HALKB":"XBANK.IS","TSKB":"XBANK.IS","QNBFB":"XBANK.IS",
    "KCHOL":"XHOLD.IS","SAHOL":"XHOLD.IS","ENKAI":"XHOLD.IS",
    "ALARK":"XHOLD.IS","TKFEN":"XHOLD.IS",
    "EREGL":"XUSIN.IS","KRDMD":"XUSIN.IS","BRSAN":"XUSIN.IS",
    "OYAKC":"XUSIN.IS","ARCLK":"XUSIN.IS","TOASO":"XUSIN.IS",
    "FROTO":"XUSIN.IS","SISE":"XUSIN.IS","GUBRF":"XUSIN.IS",
    "PETKM":"XUSIN.IS","TUPRS":"XUSIN.IS","HEKTS":"XUSIN.IS",
    "ASELS":"XUTEK.IS","SASA":"XUTEK.IS","LOGO":"XUTEK.IS",
    "KONTR":"XELKT.IS","ASTOR":"XELKT.IS","AKSEN":"XELKT.IS",
    "BIMAS":"XMESY.IS","MGROS":"XMESY.IS",
    "THYAO":"XTRZM.IS","PGSUS":"XTRZM.IS",
    "EKGYO":"XGMYO.IS",
    "TCELL":"XUHIZ.IS",
}

# ── VERİ KATMANI ─────────────────────────────────────────────────────────────
def _flatten(df):
    if df is None or df.empty: return None
    if isinstance(df.columns, pd.MultiIndex):
        lvl = 0 if "Close" in df.columns.get_level_values(0) else 1
        df.columns = df.columns.get_level_values(lvl)
    df = df.loc[:, ~df.columns.duplicated()]
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    return df if not df.empty else None

@st.cache_data(ttl=900)
def get_xu100():
    for sym in ("XU100.IS", "^XU100"):
        try:
            df = _flatten(yf.download(sym, period="60d", interval="15m", progress=False))
            if df is not None:
                df["SMA50"] = df["Close"].rolling(REGIME_SMA).mean()
                df["RSI"]   = _calc_rsi(df["Close"])
                _adx, _pdi, _mdi = _calc_adx(df)
                df["ADX"]        = _adx
                df["PlusDI"]     = _pdi
                df["MinusDI"]    = _mdi
                return df
        except Exception:
            continue
    return None

@st.cache_data(ttl=1800)
def get_4h(ticker):
    sym = f"{ticker}.IS"

    def _add_sma(df):
        df = df.copy()
        df["SMA50"]  = df["Close"].rolling(50).mean()
        df["SMA200"] = df["Close"].rolling(200).mean()
        return df

    try:
        df = _flatten(yf.download(sym, period="60d", interval="4h", progress=False))
        if df is not None and len(df) >= 55:
            result = _add_sma(df).dropna()
            if len(result) >= 5:
                return result
    except Exception:
        pass

    try:
        df1h = _flatten(yf.download(sym, period="60d", interval="1h", progress=False))
        if df1h is not None and len(df1h) >= 55:
            df = df1h.resample("4h").agg(
                {"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}
            ).dropna()
            if len(df) >= 55:
                result = _add_sma(df).dropna()
                if len(result) >= 5:
                    return result
    except Exception:
        pass

    try:
        df = _flatten(yf.download(sym, period="2y", interval="1d", progress=False))
        if df is not None and len(df) >= 210:
            result = _add_sma(df).dropna()
            if len(result) >= 5:
                return result
    except Exception:
        pass

    return None

# ── İNDİKATÖR FONKSİYONLARI ─────────────────────────────────────────────────
def _calc_rsi(close, period=14):
    d = close.diff()
    return 100 - (100 / (1 + d.where(d > 0, 0.0).rolling(period).mean()
                              / (-d.where(d < 0, 0.0)).rolling(period).mean()))

def _calc_adx(df, period=ADX_PERIOD):
    h, l, c = df["High"], df["Low"], df["Close"]
    up_move  = h.diff()
    dn_move  = -l.diff()
    plus_dm  = np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0)
    tr       = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr14    = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di  = 100 * pd.Series(plus_dm,  index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr14
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr14
    dx       = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx      = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx, plus_di, minus_di

# ── V16: VWAP Hesaplama ──────────────────────────────────────────────────────
def _calc_vwap(df):
    """
    Seans bazlı VWAP: (H+L+C)/3 * Volume / kümülatif Volume.
    Her günün başında sıfırlanır (anchored to daily open).
    15m veride günlük VWAP hesaplar.
    """
    try:
        typical = (df["High"] + df["Low"] + df["Close"]) / 3
        pv      = typical * df["Volume"]
        # Gün bazında kümülatif VWAP
        date_idx = df.index.normalize()
        cum_pv   = pv.groupby(date_idx).cumsum()
        cum_vol  = df["Volume"].groupby(date_idx).cumsum()
        vwap     = cum_pv / cum_vol.replace(0, np.nan)
        return vwap
    except Exception:
        return pd.Series(np.nan, index=df.index)

@st.cache_data(ttl=300)
def get_data(ticker):
    try:
        df = _flatten(yf.download(f"{ticker}.IS", period="60d", interval="15m", progress=False))
        if df is None: return None
        c = df["Close"]
        h, l = df["High"], df["Low"]

        df["SMA20"]   = c.rolling(20).mean()
        df["RSI"]     = _calc_rsi(c)
        df["TR"]      = pd.concat([h - l,
                                   (h - c.shift()).abs(),
                                   (l - c.shift()).abs()], axis=1).max(axis=1)
        df["ATR"]     = df["TR"].rolling(ADX_PERIOD).mean()
        df["VolMA20"] = df["Volume"].rolling(20).mean()
        df["High20"]  = h.rolling(BREAKOUT_BARS).max().shift(1)

        adx, plus_di, minus_di = _calc_adx(df)
        df["ADX"]      = adx
        df["PlusDI"]   = plus_di
        df["MinusDI"]  = minus_di

        df["VolPct"] = (df["Volume"]
                        .rolling(VOL_PCT_LOOKBACK, min_periods=20)
                        .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100,
                               raw=False))

        df["ATR_Slope"] = df["ATR"].diff(ATR_EXP_BARS)

        direction       = np.sign(c.diff())
        df["OBV"]       = (direction * df["Volume"]).fillna(0).cumsum()
        df["OBV_MA20"]  = df["OBV"].rolling(20).mean()

        prev_close       = c.shift(1)
        df["GapPct"]     = ((df["Open"] - prev_close).abs() / prev_close.replace(0, np.nan))

        df["RSI_Pct"] = (df["RSI"]
                         .rolling(RSI_PCT_LOOKBACK, min_periods=30)
                         .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100,
                                raw=False))

        df["ADX_Slope"] = df["ADX"].diff(ADX_SLOPE_BARS)

        df["ATR_Pct"] = (df["ATR"]
                         .rolling(ATR_PCT_LOOKBACK, min_periods=30)
                         .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100,
                                raw=False))

        # ── V16: DI Spread ────────────────────────────────────────────────────
        df["DI_Spread"] = df["PlusDI"] - df["MinusDI"]

        # ── V16: OBV Breakout (OBV son 20 barın maksimumunu kırdı mı?) ───────
        df["OBV_High20"] = df["OBV"].rolling(OBV_BRK_LOOKBACK).max().shift(1)

        # ── V16: VWAP ─────────────────────────────────────────────────────────
        df["VWAP"] = _calc_vwap(df)

        return df.dropna()
    except Exception:
        return None

# ── FONKSİYONLAR (V15'ten taşındı, V16 eklemeleriyle) ──────────────────────
def bollinger_squeeze(close):
    try:
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        sma  = close.rolling(20).mean()
        bb_w = (4 * close.rolling(20).std()) / sma
        thr  = bb_w.rolling(SQUEEZE_LOOKBACK, min_periods=30).quantile(0.15)
        return bb_w < thr
    except Exception:
        return pd.Series(False, index=close.index)

@st.cache_data(ttl=900)
def get_sektor_data(sektor_sym):
    try:
        df = _flatten(yf.download(sektor_sym, period="60d", interval="15m", progress=False))
        return df
    except Exception:
        return None

def sektor_rs(stock_close, ticker, xu100_df):
    sektor_sym = SEKTOR_MAP.get(ticker.upper())
    rs_sektor_ok = None
    if sektor_sym:
        try:
            sek_df = get_sektor_data(sektor_sym)
            if sek_df is not None and not sek_df.empty:
                sc  = stock_close.copy(); sc.name = "stk"
                sek = sek_df["Close"].copy(); sek.name = "sek"
                aln = pd.concat([sc, sek], axis=1).ffill().dropna()
                if len(aln) > 20:
                    rs_s = aln["stk"] / aln["sek"]
                    rs_sektor_ok = bool(rs_s.iloc[-1] > rs_s.rolling(20).mean().iloc[-1])
        except Exception:
            rs_sektor_ok = None

    rs_xu100_ok = None
    if xu100_df is not None and not xu100_df.empty:
        try:
            sc  = stock_close.copy(); sc.name = "stk"
            xu  = xu100_df["Close"].copy(); xu.name = "idx"
            aln = pd.concat([sc, xu], axis=1).ffill().dropna()
            if len(aln) > 20:
                rs_x = aln["stk"] / aln["idx"]
                rs_xu100_ok = bool(rs_x.iloc[-1] > rs_x.rolling(20).mean().iloc[-1])
        except Exception:
            pass

    return rs_xu100_ok, rs_sektor_ok, sektor_sym

def vcp_score(df):
    try:
        c   = df["Close"] if "Close" in df.columns else df.iloc[:, 0]
        vol = df["Volume"]
        n   = len(c)
        if n < VCP_LOOKBACK:
            return 0, False, False, False

        std_recent = c.iloc[-20:].std()
        std_long   = c.iloc[-VCP_LOOKBACK:].std()
        vol_recent = vol.iloc[-20:].mean()
        vol_long   = vol.iloc[-VCP_LOOKBACK:].mean()

        price_contract = (std_recent < std_long * 0.85) if std_long > 0 else False
        vol_contract   = (vol_recent < vol_long * 0.75)  if vol_long  > 0 else False
        rs_rising      = float(c.iloc[-1]) > float(c.iloc[-20]) if n >= 20 else False

        score = int(price_contract) + int(vol_contract) + int(rs_rising)
        return score, price_contract, vol_contract, rs_rising
    except Exception:
        return 0, False, False, False

def relative_strength_full(stock_close, xu100_df):
    if xu100_df is None or xu100_df.empty: return None, None, None
    try:
        if isinstance(stock_close, pd.DataFrame): stock_close = stock_close.iloc[:, 0]
        xu  = xu100_df["Close"].copy(); xu.name = "idx"
        sc  = stock_close.copy();       sc.name = "stk"
        aln = pd.concat([sc, xu], axis=1).ffill().dropna()
        if aln.empty: return None, None, None
        rs       = aln["stk"] / aln["idx"]
        rs_above = rs > rs.rolling(20).mean()
        rs_slope = rs.diff(RS_SLOPE_BARS) > 0
        return rs_above, rs_slope, rs
    except Exception:
        return None, None, None

def htf_trend(ticker):
    try:
        df = get_4h(ticker)
        if df is None or len(df) < 5: return None
        s50, s200 = float(df["SMA50"].iloc[-1]), float(df["SMA200"].iloc[-1])
        if pd.isna(s50) or pd.isna(s200): return None
        return s50 > s200
    except Exception:
        return None

def atr_regime(atr_val, price):
    if price <= 0: return False, 0.0
    pct = atr_val / price
    return ATR_PCT_MIN < pct < ATR_PCT_MAX, pct

def breakout_check(df):
    try:
        return float(df["Close"].iloc[-1]) > float(df["High20"].iloc[-1])
    except Exception:
        return False

def event_risk(ticker):
    try:
        ed = yf.Ticker(f"{ticker}.IS").info.get("earningsDate")
        if ed is None: return "📡"
        if isinstance(ed, list): ed = ed[0]
        if isinstance(ed, int):  ed = datetime.datetime.fromtimestamp(ed)
        return "⚠" if 0 <= (ed.replace(tzinfo=None) - datetime.datetime.now()).days <= 5 else "✅"
    except Exception:
        return "📡"

# ── MARKET HEALTH SCORE ───────────────────────────────────────────────────────
def market_health_score(xu100_df, breadth_pct: float | None = None):
    score  = 0
    detail = {}

    k1 = False
    if xu100_df is not None and "SMA50" in xu100_df.columns:
        try:
            k1 = float(xu100_df["Close"].iloc[-1]) > float(xu100_df["SMA50"].iloc[-1])
        except Exception:
            pass
    score += int(k1); detail["XU100 > SMA50"] = k1

    k2 = False
    if breadth_pct is not None:
        k2 = breadth_pct > BREADTH_NEUTRAL
    score += int(k2); detail[f"Breadth > {BREADTH_NEUTRAL}%"] = k2

    k3 = False
    if breadth_pct is not None:
        k3 = breadth_pct > 70
    score += int(k3); detail["Breadth > 70%"] = k3

    k4 = False
    if xu100_df is not None and "RSI" in xu100_df.columns:
        try:
            rsi_val = float(xu100_df["RSI"].iloc[-1])
            k4 = not pd.isna(rsi_val) and rsi_val > 50
        except Exception:
            pass
    score += int(k4); detail["XU100 RSI > 50"] = k4

    k5 = False
    if xu100_df is not None and "ADX" in xu100_df.columns:
        try:
            adx_val = xu100_df["ADX"]
            if isinstance(adx_val, pd.DataFrame):
                adx_val = adx_val.iloc[:, 0]
            v = float(adx_val.iloc[-1])
            k5 = not pd.isna(v) and v > 20
        except Exception:
            pass
    score += int(k5); detail["XU100 ADX > 20"] = k5

    return score, detail

def mhs_risk(score: int) -> float:
    if score >= 4: return RISK_FULL
    if score == 3: return RISK_FULL
    if score == 2: return RISK_HALF
    return RISK_OFF

def market_regime(xu100_df, breadth_pct: float | None = None):
    na = {"lbl":"Belirsiz","css":"rb-none","risk":RISK_FULL,"icon":"⚠️","mhs":0}
    if xu100_df is None or "SMA50" not in xu100_df.columns: return na
    try:
        c = float(xu100_df["Close"].iloc[-1])
        s = float(xu100_df["SMA50"].iloc[-1])
        if pd.isna(s): return na
        mhs, _ = market_health_score(xu100_df, breadth_pct)
        risk    = mhs_risk(mhs)
        above_sma = c > s
        breadth_ok = (breadth_pct is None) or (breadth_pct > BREADTH_NEUTRAL)
        if above_sma and breadth_ok:
            return {"lbl":f"BULL — XU100 {c:.0f} > SMA50 {s:.0f}  |  MHS {mhs}/5",
                    "css":"rb-bull","risk":risk,"icon":"🟢","mhs":mhs}
        elif above_sma and not breadth_ok:
            return {"lbl":f"ZAYIF BULL — Breadth %{breadth_pct:.0f} < {BREADTH_NEUTRAL}%  |  MHS {mhs}/5",
                    "css":"rb-none","risk":risk,"icon":"🟡","mhs":mhs}
        return     {"lbl":f"BEAR — XU100 {c:.0f} < SMA50 {s:.0f}  |  MHS {mhs}/5",
                    "css":"rb-bear","risk":risk,"icon":"🔴","mhs":mhs}
    except Exception:
        return na

def data_freshness(df):
    try:
        age = (datetime.datetime.now() - df.index[-1]).total_seconds() / 60
        if age > 900:
            return {"age":age,"css":"fb-yellow","icon":"⏸️","label":"Piyasa Kapalı","is_closed":True}
        elif age <= FRESHNESS_WARN:
            return {"age":age,"css":"fb-green", "icon":"🟢","label":f"Güncel — {age:.0f}dk önce","is_closed":False}
        elif age <= FRESHNESS_RED:
            return {"age":age,"css":"fb-yellow","icon":"🟡","label":f"Gecikiyor — {age:.0f}dk önce","is_closed":False}
        else:
            return {"age":age,"css":"fb-red",   "icon":"🔴","label":f"BAYAT — {age:.0f}dk önce","is_closed":False}
    except Exception:
        return {"age":0,"css":"fb-yellow","icon":"⚠️","label":"Zaman bilinmiyor","is_closed":False}

def support_resistance_v2(df, lookback=SR_LOOKBACK):
    try:
        hi, lo  = df["High"].iloc[-lookback:].values, df["Low"].iloc[-lookback:].values
        vol     = df["Volume"].iloc[-lookback:].values
        price   = float(df["Close"].iloc[-1])
        TOL     = 0.005
        ph, pl  = [], []
        for i in range(2, len(hi) - 2):
            if hi[i] > hi[i-1] and hi[i] > hi[i-2] and hi[i] > hi[i+1] and hi[i] > hi[i+2]:
                ph.append((hi[i], vol[i]))
            if lo[i] < lo[i-1] and lo[i] < lo[i-2] and lo[i] < lo[i+1] and lo[i] < lo[i+2]:
                pl.append((lo[i], vol[i]))
        def touches(level, bars):
            return sum(1 for v, _ in bars if abs(v - level) / level <= TOL)
        res_raw = sorted([(p, v) for p, v in ph if p > price])[:3]
        sup_raw = sorted([(p, v) for p, v in pl if p < price], reverse=True)[:3]
        return ([(p, touches(p, pl)) for p, _ in sup_raw],
                [(p, touches(p, ph)) for p, _ in res_raw])
    except Exception:
        return [], []

# ── BACKTEST (V16: 20 filtre) ─────────────────────────────────────────────────
def run_backtest(df, xu100_df):
    try:
        sqz                  = bollinger_squeeze(df["Close"])
        rs_above, rs_sl, _   = relative_strength_full(df["Close"], xu100_df)
        if rs_above is None: return {"err": "XU100 verisi yok"}

        vol_ratio_s  = df["Volume"] / df["VolMA20"]
        vol_confirm  = (vol_ratio_s > RVOL_THRESHOLD) & (df["Close"] > df["Close"].shift(1))
        breakout_s   = df["Close"] > df["High20"]
        atr_pct_s    = df["ATR"] / df["Close"]
        atr_ok_s     = (atr_pct_s > ATR_PCT_MIN) & (atr_pct_s < ATR_PCT_MAX)
        adx_ok_s     = df["ADX"] > ADX_THRESHOLD
        adx_dir_s    = df["PlusDI"] > df["MinusDI"]
        vol_pct_ok_s = df["VolPct"] > 70
        atr_exp_s    = df["ATR_Slope"] > 0
        obv_ok_s     = df["OBV"] > df["OBV_MA20"]
        gap_ok_s     = df["GapPct"] < GAP_MAX_PCT
        rsi_pct_s    = df["RSI_Pct"] > 60           if "RSI_Pct"   in df.columns else pd.Series(True, index=df.index)
        adx_slope_s  = df["ADX_Slope"] > 0          if "ADX_Slope" in df.columns else pd.Series(True, index=df.index)
        atr_pct_s2   = (df["ATR_Pct"] > 10) & (df["ATR_Pct"] < 75) if "ATR_Pct" in df.columns else pd.Series(True, index=df.index)
        # V16 yeni filtreler
        di_spread_s  = df["DI_Spread"] > DI_SPREAD_MIN if "DI_Spread"  in df.columns else pd.Series(True, index=df.index)
        obv_brk_s    = df["OBV"] > df["OBV_High20"]    if "OBV_High20" in df.columns else pd.Series(True, index=df.index)
        vwap_s       = df["Close"] > df["VWAP"]         if "VWAP"       in df.columns else pd.Series(True, index=df.index)

        bt = pd.concat([
            df[["Close","SMA20","ATR","RSI","PlusDI","MinusDI"]],
            sqz.rename("SQZ"),
            rs_above.rename("RS"),
            rs_sl.rename("RS_SL"),
            vol_confirm.rename("VOL"),
            breakout_s.rename("BRK"),
            atr_ok_s.rename("ATROK"),
            adx_ok_s.rename("ADXOK"),
            adx_dir_s.rename("ADXDIR"),
            vol_pct_ok_s.rename("VPCT"),
            atr_exp_s.rename("ATREXP"),
            obv_ok_s.rename("OBV_OK"),
            gap_ok_s.rename("GAP_OK"),
            rsi_pct_s.rename("RSIPCT"),
            adx_slope_s.rename("ADXSLP"),
            atr_pct_s2.rename("ATRPCT"),
            di_spread_s.rename("DISP"),
            obv_brk_s.rename("OBVBRK"),
            vwap_s.rename("VWAPOK"),
        ], axis=1).ffill().dropna()

        pos, buy_cost, stop_px, trades = False, 0.0, 0.0, []
        for _, r in bt.iterrows():
            if not pos:
                if (r.Close > r.SMA20 and 50 < r.RSI < 70
                        and r.RS and r.RS_SL and r.SQZ and r.VOL
                        and r.BRK and r.ATROK and r.ADXOK and r.ADXDIR
                        and r.VPCT and r.ATREXP and r.OBV_OK and r.GAP_OK
                        and r.RSIPCT and r.ADXSLP and r.ATRPCT
                        and r.DISP and r.OBVBRK and r.VWAPOK):
                    pos      = True
                    buy_cost = r.Close * (1 + TRADE_COST)
                    stop_px  = r.Close - r.ATR * ATR_MULT
            else:
                reason = ("Trend" if r.Close < r.SMA20 else
                          "RS"    if not r.RS           else
                          "Stop"  if r.Close < stop_px  else None)
                if reason:
                    trades.append({
                        "pnl": (r.Close * (1 - TRADE_COST) - buy_cost) / buy_cost * 100,
                        "why": reason
                    })
                    pos = False

        if not trades: return {"err": "60 günde kriterlere uygun işlem yok"}
        pnls   = [t["pnl"] for t in trades]
        wins   = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        pf     = sum(wins) / abs(sum(losses)) if losses else float("inf")
        cum    = pd.Series(pnls).cumsum()
        bh     = (bt["Close"].iloc[-1] / bt["Close"].iloc[0] - 1) * 100
        ec     = {"Trend":0,"RS":0,"Stop":0}
        for t in trades: ec[t["why"]] += 1
        return {"total":sum(pnls),"wr":len(wins)/len(trades)*100,
                "pf":pf,"bh":bh,"dd":(cum-cum.cummax()).min(),
                "n":len(trades),"ec":ec,"err":None}
    except Exception as e:
        return {"err": str(e)}

# ── HTML YARDIMCILARI ─────────────────────────────────────────────────────────
def scanner_html(rows):
    hdr = ("<colgroup>"
           "<col style='width:26%'><col style='width:18%'>"
           "<col style='width:7%'><col style='width:7%'>"
           "<col style='width:7%'><col style='width:7%'>"
           "<col style='width:7%'><col style='width:9%'>"
           "<col style='width:12%'>"
           "</colgroup>"
           "<thead><tr>"
           "<th style='text-align:left;padding-left:5px'>Hisse</th>"
           "<th>Fiyat</th><th>T</th>"
           "<th title='4H Trend'>4H</th>"
           "<th title='ADX Trend Gücü + Yön'>ADX</th>"
           "<th title='Bollinger Squeeze'>SQZ</th>"
           "<th title='RS + Slope'>RS</th>"
           "<th title='OBV Kurumsal Akış'>OBV</th>"
           "<th title='Event Risk'>EVT</th>"
           "</tr></thead>")
    body = "<tbody>"
    for r in rows:
        tc = "#22c55e" if r["T"] == "↑" else "#ef4444"
        body += (f"<tr><td class='tkr'>{r['H']}</td><td>{r['F']}</td>"
                 f"<td style='color:{tc}'>{r['T']}</td>"
                 f"<td>{r['HTF']}</td><td>{r['ADX']}</td>"
                 f"<td>{r['SQZ']}</td><td>{r['RS']}</td>"
                 f"<td>{r['OBV']}</td><td>{r['EVT']}</td></tr>")
    return (f"<div class='scanner-wrapper'>"
            f"<table class='scanner-table'>{hdr}{body}</tbody></table></div>")

def breadth_html(above, total):
    if total == 0: return ""
    pct = int(above / total * 100)
    css = "#22c55e" if pct >= 70 else ("#f59e0b" if pct >= BREADTH_NEUTRAL else "#ef4444")
    lbl = (f"GÜÇLÜ ({above}/{total})" if pct >= 70
           else f"NÖTR ({above}/{total})" if pct >= BREADTH_NEUTRAL
           else f"ZAYIF ({above}/{total})")
    return (f"<div class='breadth-wrap'>"
            f"<div class='bw-lbl'>Piyasa Genişliği — SMA20 Üstü</div>"
            f"<div class='bar-outer'>"
            f"<div style='width:{pct}%;height:100%;background:{css};border-radius:4px'></div>"
            f"</div>"
            f"<div class='bw-nums'>"
            f"<span style='color:{css};font-weight:700'>{lbl}</span>"
            f"<span style='color:#6b7594'>%{pct}</span>"
            f"</div></div>")

def regime_html(reg, extra=""):
    return f"<div class='regime-banner {reg['css']}' style='{extra}'>{reg['icon']} {reg['lbl']}</div>"

def freshness_html(fr, extra=""):
    return f"<div class='freshness-banner {fr['css']}' style='{extra}'>{fr['icon']} {fr['label']}</div>"

def htf_html(val, ticker):
    if val is None:
        return f"<div class='htf-banner htf-none'>⚠️ 4H veri yok — {ticker}</div>"
    return (f"<div class='htf-banner htf-bull'>🟢 4H BULL — SMA50 > SMA200</div>"
            if val else
            f"<div class='htf-banner htf-bear'>🔴 4H BEAR — SMA50 < SMA200</div>")

def mhs_html(score: int, detail: dict):
    css_map = {5:"mhs-5",4:"mhs-4",3:"mhs-3",2:"mhs-2",1:"mhs-1",0:"mhs-0"}
    lbl_map = {5:"RİSK ON — Tam Pozisyon",
               4:"RİSK ON — Tam Pozisyon",
               3:"NÖTR — Normal Pozisyon",
               2:"TEMKİNLİ — Yarı Pozisyon",
               1:"RİSK OFF — Küçük Pozisyon",
               0:"RİSK OFF — Bekleme"}
    icon_map= {5:"💚",4:"🟢",3:"🟡",2:"🟠",1:"🔴",0:"⛔"}
    css  = css_map.get(score, "mhs-0")
    risk = mhs_risk(score)
    rows = "".join(
        f"<div class='mhs-row'>"
        f"<span class='mhs-item'>{k}</span>"
        f"<span class='mhs-check' style='color:{'#4ade80' if v else '#ef4444'}'>{'✅' if v else '❌'}</span>"
        f"</div>"
        for k, v in detail.items()
    )
    return (f"<div class='mhs-wrap'>"
            f"<div class='mhs-lbl'>Market Health Score — {score}/5</div>"
            f"<div class='health-banner {css}' style='margin-bottom:6px'>"
            f"{icon_map[score]} {lbl_map[score]}  ·  Risk: %{risk*100:.1f}</div>"
            f"{rows}</div>")

def sig_row_html(label, state, t_txt, f_txt, none_txt="📡 Veri Yok"):
    if state is None:
        return (f"<div class='sr unk'><span class='sl'>{label}</span>"
                f"<span class='sv wn'>{none_txt}</span></div>")
    return (f"<div class='sr {'ok' if state else 'nok'}'>"
            f"<span class='sl'>{label}</span>"
            f"<span class='sv {'up' if state else 'dn'}'>"
            f"{t_txt if state else f_txt}</span></div>")

def karar_html(skor, n):
    # V16: 22 filtre → eşikler orantılı: %82/%68/%45
    if   skor >= 18: css, lbl, ikon = "kc-al",   "GÜÇLÜ AL",    "💚"
    elif skor >= 15: css, lbl, ikon = "kc-pos",  "OLUMLU",      "🟢"
    elif skor >= 10: css, lbl, ikon = "kc-notr", "NÖTR / İZLE", "🟡"
    else:            css, lbl, ikon = "kc-sat",  "BEKLE / SAT", "🔴"
    return (f"<div class='karar-card {css}'>"
            f"<div class='karar-lbl'>Kompozit Karar — {skor}/{n} sinyal aktif</div>"
            f"<div class='karar-val'>{ikon} {lbl}</div></div>")

def metric_grid(*cards):
    items = "".join(
        f"<div class='mc'><div class='lb'>{l}</div>"
        f"<div class='vl {c}'>{v}</div></div>"
        for l, v, c in cards)
    return f"<div class='mg'>{items}</div>"

def sec_div(text):
    return f"<div class='sec-divider'>{text}</div>"

def level_rows_html(price, supports, resistances, vwap_val=None):
    html = ""
    for p, tc in reversed(resistances):
        dist  = (p / price - 1) * 100
        touch = f" ★{tc}" if tc >= 2 else ""
        html += (f"<div class='level-row res'>"
                 f"<span class='lv-lbl'>Direnç{touch}</span>"
                 f"<span class='lv-val'>{p:.2f} TL</span>"
                 f"<span class='lv-dist'>+{dist:.2f}%</span></div>")
    html += (f"<div class='level-row cur'>"
             f"<span class='lv-lbl'>Güncel</span>"
             f"<span class='lv-val'>{price:.2f} TL</span>"
             f"<span class='lv-dist'>—</span></div>")
    # V16: VWAP seviyesi destek/direnç tabloya eklendi
    if vwap_val is not None and not pd.isna(vwap_val):
        vwap_dist = (price / vwap_val - 1) * 100
        vwap_side = "üstü ✅" if price >= vwap_val else "altı ⚠️"
        html += (f"<div class='level-row vwap'>"
                 f"<span class='lv-lbl'>VWAP ({vwap_side})</span>"
                 f"<span class='lv-val'>{vwap_val:.2f} TL</span>"
                 f"<span class='lv-dist'>{vwap_dist:+.2f}%</span></div>")
    for p, tc in supports:
        dist  = (price / p - 1) * 100
        touch = f" ★{tc}" if tc >= 2 else ""
        html += (f"<div class='level-row sup'>"
                 f"<span class='lv-lbl'>Destek{touch}</span>"
                 f"<span class='lv-val'>{p:.2f} TL</span>"
                 f"<span class='lv-dist'>-{dist:.2f}%</span></div>")
    return html

def rr_bar_html(risk_tl, reward_tl, ratio):
    total = risk_tl + reward_tl
    r_pct = int(risk_tl / total * 100) if total > 0 else 50
    r_cls = "up" if ratio >= 2.0 else ("wn" if ratio >= 1.0 else "dn")
    return (f"<div class='rr-bar-wrap'><div class='rr-lbl'>Risk / Ödül Oranı</div>"
            f"<div class='bar-outer'><div style='display:flex;height:100%'>"
            f"<div style='width:{r_pct}%;height:100%;background:#ef4444;border-radius:4px 0 0 4px'></div>"
            f"<div style='width:{100-r_pct}%;height:100%;background:#22c55e;border-radius:0 4px 4px 0'></div>"
            f"</div></div>"
            f"<div class='rr-nums'>"
            f"<span class='rr-r'>Risk: {risk_tl:.2f} TL</span>"
            f"<span class='vl {r_cls}' style='font-size:11px;font-weight:700'>1:{ratio:.2f}</span>"
            f"<span class='rr-rw'>Ödül: {reward_tl:.2f} TL</span>"
            f"</div></div>")

def vol_bar_html(vol_now, vol_ma, vol_ratio, vol_confirmed, vol_pct):
    fill = min(int(vol_ratio * 50), 100)
    bar_c = "#22c55e" if vol_confirmed else ("#f59e0b" if vol_ratio >= RVOL_THRESHOLD else "#94a3b8")
    if vol_confirmed:
        lbl = f"✅ DOĞRULANDI (x{vol_ratio:.2f}, P{vol_pct:.0f})"
    elif vol_ratio >= RVOL_THRESHOLD:
        lbl = f"⚠️ Yüksek Hacim — Negatif Kapanış (Dağıtım?)"
    else:
        lbl = f"Normal/Düşük (x{vol_ratio:.2f}, P{vol_pct:.0f})"
    return (f"<div class='vol-bar-wrap'><div class='vb-lbl'>Hacim — {lbl}</div>"
            f"<div class='bar-outer'>"
            f"<div style='width:{fill}%;height:100%;background:{bar_c};border-radius:4px'></div>"
            f"</div>"
            f"<div class='vb-nums'>"
            f"<span>Anlık: {vol_now:,.0f}</span>"
            f"<span>RVOL: x{vol_ratio:.2f}</span>"
            f"<span>Percentile: P{vol_pct:.0f}</span>"
            f"</div></div>")

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
xu100  = get_xu100()

_breadth_pct = None
if st.session_state.breadth:
    b = st.session_state.breadth
    if b["total"] > 0:
        _breadth_pct = b["above"] / b["total"] * 100

regime = market_regime(xu100, _breadth_pct)

with st.sidebar:
    st.header("⚙️ Kontrol Paneli")
    st.markdown(regime_html(regime), unsafe_allow_html=True)

    mhs_score, mhs_detail = market_health_score(xu100, _breadth_pct)
    st.markdown(
        f"<div style='background:#0d1421;border-radius:5px;padding:5px 10px;"
        f"margin-bottom:6px;font-size:10px;text-align:center;'>"
        f"<span style='color:#6b7594'>Market Health: </span>"
        f"<span style='color:#e2e8f0;font-weight:700'>{mhs_score}/5  "
        f"·  Risk: %{mhs_risk(mhs_score)*100:.1f}</span></div>",
        unsafe_allow_html=True
    )

    secilen = st.selectbox("Hisse Seçin:", sorted(st.session_state.watchlist))
    portfoy = st.number_input(
        f"Portföy (TL)  ·  Risk: %{regime['risk']*100:.1f}",
        min_value=1000, value=100_000, step=10_000
    )
    df_sb = get_data(secilen)
    if df_sb is not None:
        st.markdown(freshness_html(data_freshness(df_sb)), unsafe_allow_html=True)
    else:
        st.error("🔴 Veri Bağlantısı Koptu")

    st.divider()
    st.subheader("📝 Liste Yönetimi")

    yeni = st.text_input("Hisse Ekle (Örn: ASELS):").upper().strip()
    b1, b2 = st.columns(2)
    with b1:
        if st.button("➕ Ekle"):
            if yeni and yeni not in st.session_state.watchlist:
                st.session_state.watchlist.append(yeni)
                save_watchlist(st.session_state.watchlist)
                st.rerun()
    with b2:
        if st.button("🗑️ Çıkar"):
            if len(st.session_state.watchlist) > 1:
                st.session_state.watchlist.remove(secilen)
                save_watchlist(st.session_state.watchlist)
                st.rerun()

    if st.button("↺ Listeyi Sıfırla"):
        st.session_state.watchlist = BIST_30.copy()
        save_watchlist(st.session_state.watchlist)
        st.rerun()

    st.caption(f"📋 {len(st.session_state.watchlist)} hisse  ·  "
               f"Sayfayı yenileyebilirsiniz, liste korunur.")

# ── ANA EKRAN ─────────────────────────────────────────────────────────────────
col_l, col_c, col_r = st.columns([2.5, 5, 2.5])
df = get_data(secilen)

# ══ SOL: SCANNER ══════════════════════════════════════════════════════════════
with col_l:
    st.markdown("### 🚀 Tarayıcı")
    st.caption("⏱️ 15dk gecikmeli  ·  V16: DI Spread / OBV Breakout / VWAP dahil")

    if st.button("Tüm Listeyi Tara"):
        st.session_state.scan_rows = []
        st.session_state.breadth   = None
        rows, above_count = [], 0
        prog = st.progress(0, text="Başlatılıyor...")
        wl   = sorted(st.session_state.watchlist)
        for i, t in enumerate(wl):
            d = get_data(t)
            if d is not None:
                rs_ab, rs_sl, _ = relative_strength_full(d["Close"], xu100)
                if rs_ab is None:                                         rs_icon = "📡"
                elif bool(rs_ab.iloc[-1]) and bool(rs_sl.iloc[-1]):      rs_icon = "💚"
                elif bool(rs_ab.iloc[-1]):                                rs_icon = "🟡"
                else:                                                     rs_icon = "🔴"

                htf_val  = htf_trend(t)
                htf_icon = "🟢" if htf_val is True else ("🔴" if htf_val is False else "⚪")

                adx_val  = float(d["ADX"].iloc[-1])     if "ADX"     in d.columns else 0
                pdi      = float(d["PlusDI"].iloc[-1])  if "PlusDI"  in d.columns else 0
                mdi      = float(d["MinusDI"].iloc[-1]) if "MinusDI" in d.columns else 0
                # V16: DI Spread dahil ADX ikonu
                di_sp    = pdi - mdi
                adx_ok   = adx_val > ADX_THRESHOLD and pdi > mdi and di_sp > DI_SPREAD_MIN
                adx_icon = ("💪" if adx_ok else ("⚠️" if adx_val > ADX_THRESHOLD else "·"))

                obv_ok   = ("OBV" in d.columns and "OBV_MA20" in d.columns and
                            float(d["OBV"].iloc[-1]) > float(d["OBV_MA20"].iloc[-1]))
                # V16: OBV Breakout ekstra kontrol
                obv_brk  = ("OBV_High20" in d.columns and
                            float(d["OBV"].iloc[-1]) > float(d["OBV_High20"].iloc[-1]))
                obv_icon = ("🚀" if (obv_ok and obv_brk) else
                            "📈" if obv_ok else "📉")

                trend_up = float(d["Close"].iloc[-1]) > float(d["SMA20"].iloc[-1])
                if trend_up: above_count += 1

                rows.append({
                    "H":   t,
                    "F":   f"{float(d['Close'].iloc[-1]):.2f}",
                    "T":   "↑" if trend_up else "↓",
                    "HTF": htf_icon,
                    "ADX": adx_icon,
                    "SQZ": "🟡" if bool(bollinger_squeeze(d["Close"]).iloc[-1]) else "·",
                    "RS":  rs_icon,
                    "OBV": obv_icon,
                    "EVT": st.session_state.event_risks.get(t, "📡"),
                })
            prog.progress((i + 1) / len(wl), text=f"Tarıyor: {t}")
        prog.empty()
        st.session_state.scan_rows = rows
        st.session_state.breadth   = {"above": above_count, "total": len(rows)}
        st.rerun()

    if st.session_state.breadth:
        b = st.session_state.breadth
        st.markdown(breadth_html(b["above"], b["total"]), unsafe_allow_html=True)

    if st.session_state.scan_rows:
        st.markdown(scanner_html(st.session_state.scan_rows), unsafe_allow_html=True)
        if st.button("⚠️ Event Risklerini Yükle (Yavaş)"):
            pr, risks = st.progress(0), {}
            for i, t in enumerate(st.session_state.watchlist):
                risks[t] = event_risk(t)
                pr.progress((i + 1) / len(st.session_state.watchlist))
            st.session_state.event_risks = risks
            pr.empty(); st.rerun()

# ══ ORTA: GRAFİK ══════════════════════════════════════════════════════════════
with col_c:
    st.markdown(f"### 📈 {secilen} · 15m Grafik")
    if df is not None and not df.empty:
        fr = data_freshness(df)
        st.markdown(freshness_html(fr, "font-size:10px;padding:3px 8px;margin-bottom:4px"),
                    unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="Fiyat",
            increasing_line_color="#22c55e", decreasing_line_color="#ef4444"
        ))
        fig.add_trace(go.Scatter(
            x=df.index, y=df["SMA20"], mode="lines",
            name="SMA20", line=dict(color="#38bdf8", width=1.5)
        ))
        # V16: VWAP grafikte gösterildi
        if "VWAP" in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["VWAP"], mode="lines",
                name="VWAP", line=dict(color="#a78bfa", width=1.2, dash="dot"),
                opacity=0.85
            ))
        if "OBV" in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["OBV"], mode="lines",
                name="OBV", line=dict(color="#a78bfa", width=1),
                yaxis="y2", opacity=0.7
            ))
            fig.add_trace(go.Scatter(
                x=df.index, y=df["OBV_MA20"], mode="lines",
                name="OBV MA20", line=dict(color="#f59e0b", width=1, dash="dot"),
                yaxis="y2", opacity=0.7
            ))
        fig.update_xaxes(rangebreaks=[
            dict(bounds=["18:00", "09:55"]),
            dict(bounds=["sat", "mon"])
        ])
        fig.update_layout(
            template="plotly_dark", height=530,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.02, x=0, font=dict(size=10)),
            yaxis=dict(domain=[0.28, 1.0]),
            yaxis2=dict(domain=[0.0, 0.25],
                        title=dict(text="OBV", font=dict(size=9, color="#a78bfa")),
                        tickfont=dict(size=8))
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Grafik verisi çekilemedi.")

# ══ SAĞ: ANALİZ PANELİ ════════════════════════════════════════════════════════
with col_r:
    st.markdown("### 🧠 Analiz Paneli")

    if df is not None and not df.empty:
        fiyat    = float(df["Close"].iloc[-1])
        fiyat_p  = float(df["Close"].iloc[-2]) if len(df) > 1 else fiyat
        atr      = float(df["ATR"].iloc[-1])
        sma      = float(df["SMA20"].iloc[-1])
        rsi      = float(df["RSI"].iloc[-1])
        vol_now  = float(df["Volume"].iloc[-1])
        vol_ma   = float(df["VolMA20"].iloc[-1])   if "VolMA20"   in df.columns else vol_now
        adx_val  = float(df["ADX"].iloc[-1])        if "ADX"       in df.columns else 0.0
        plus_di  = float(df["PlusDI"].iloc[-1])     if "PlusDI"    in df.columns else 0.0
        minus_di = float(df["MinusDI"].iloc[-1])    if "MinusDI"   in df.columns else 0.0
        vol_pct  = float(df["VolPct"].iloc[-1])     if "VolPct"    in df.columns else 50.0
        atr_exp  = float(df["ATR_Slope"].iloc[-1])  if "ATR_Slope" in df.columns else 0.0
        obv_now  = float(df["OBV"].iloc[-1])        if "OBV"       in df.columns else 0.0
        obv_ma   = float(df["OBV_MA20"].iloc[-1])   if "OBV_MA20"  in df.columns else 0.0
        gap_pct  = float(df["GapPct"].iloc[-1])     if "GapPct"    in df.columns else 0.0

        # V16: yeni gösterge değerleri
        di_spread_val  = float(df["DI_Spread"].iloc[-1])  if "DI_Spread"  in df.columns else (plus_di - minus_di)
        obv_high20     = float(df["OBV_High20"].iloc[-1]) if "OBV_High20" in df.columns else obv_now
        vwap_val       = float(df["VWAP"].iloc[-1])        if "VWAP"       in df.columns else None

        sqz_now               = bool(bollinger_squeeze(df["Close"]).iloc[-1])
        rs_above, rs_sl_s, _  = relative_strength_full(df["Close"], xu100)
        rs_now                = bool(rs_above.iloc[-1])  if rs_above is not None else None
        rs_slope_now          = bool(rs_sl_s.iloc[-1])   if rs_sl_s  is not None else None
        htf_now               = htf_trend(secilen)
        atr_ok, atr_pct       = atr_regime(atr, fiyat)
        brk_now               = breakout_check(df)
        supports, resistances = support_resistance_v2(df)
        fr                    = data_freshness(df)

        lb            = min(26, len(df) - 1)
        deg_pct       = (fiyat / float(df["Close"].iloc[-lb]) - 1) * 100
        sma_pct       = (fiyat / sma - 1) * 100
        vol_ratio     = vol_now / vol_ma if vol_ma > 0 else 1.0
        vol_confirmed = (vol_ratio >= RVOL_THRESHOLD) and (fiyat > fiyat_p)
        rsi_ok        = 50 < rsi < 70
        adx_ok        = adx_val > ADX_THRESHOLD
        adx_dir_ok    = plus_di > minus_di
        vol_pct_ok    = vol_pct > 70
        atr_exp_ok    = atr_exp > 0
        obv_ok        = obv_now > obv_ma
        gap_ok        = gap_pct < GAP_MAX_PCT

        # V15 değerleri
        rsi_pct_val   = float(df["RSI_Pct"].iloc[-1])   if "RSI_Pct"   in df.columns else 50.0
        adx_slope_val = float(df["ADX_Slope"].iloc[-1]) if "ADX_Slope" in df.columns else 0.0
        atr_pct_val   = float(df["ATR_Pct"].iloc[-1])   if "ATR_Pct"   in df.columns else 50.0
        rsi_pct_ok    = rsi_pct_val > 60
        adx_slope_ok  = adx_slope_val > 0
        atr_pct_ok    = 10 < atr_pct_val < 75

        rs_xu100_ok, rs_sektor_ok, sektor_sym = sektor_rs(df["Close"], secilen, xu100)
        sektor_rs_ok  = (rs_sektor_ok is True) if rs_sektor_ok is not None else True

        vcp_s, vcp_price, vcp_vol, vcp_rs = vcp_score(df)
        vcp_ok        = vcp_s >= 2

        # ── V16: Yeni filtre mantığı ─────────────────────────────────────────
        # 1. DI Spread: +DI - -DI > 10 (gerçek yükseliş gücü ayrışması)
        di_spread_ok  = di_spread_val > DI_SPREAD_MIN

        # 2. OBV Breakout: OBV son 20 barın maksimumunu kırıyor mu?
        obv_brk_ok    = obv_now > obv_high20 if obv_high20 != 0 else False

        # 3. VWAP: Close > günlük VWAP → kurumsal maliyet üstünde
        vwap_ok       = (fiyat > vwap_val) if (vwap_val is not None and not pd.isna(vwap_val)) else None

        if   rsi >= 70: rz_lbl, rz_cls = "AŞIRI ALIM",  "dn"
        elif rsi >= 55: rz_lbl, rz_cls = "GÜÇLÜ BÖLGE", "up"
        elif rsi >= 50: rz_lbl, rz_cls = "NÖTR ÜST",    "wn"
        elif rsi >= 45: rz_lbl, rz_cls = "NÖTR ALT",    "wn"
        elif rsi >= 30: rz_lbl, rz_cls = "ZAYIF BÖLGE", "dn"
        else:           rz_lbl, rz_cls = "AŞIRI SATIM", "wn"

        # 22 filtre kompozit skor (V16)
        sinyaller = [
            fiyat > sma,                # 1.  Trend (15m)
            rsi_ok,                     # 2.  RSI bandı 50-70
            rs_now is True,             # 3.  RS güçlü (XU100)
            rs_slope_now is True,       # 4.  RS hızlanıyor
            sqz_now,                    # 5.  Squeeze
            vol_confirmed,              # 6.  Hacim doğrulama
            htf_now is True,            # 7.  4H HTF
            brk_now,                    # 8.  Breakout
            atr_ok,                     # 9.  ATR% bölgesi (sabit bant)
            adx_ok,                     # 10. ADX > 25
            adx_dir_ok,                 # 11. +DI > -DI
            vol_pct_ok,                 # 12. Volume Percentile > 70
            atr_exp_ok,                 # 13. ATR Expansion
            obv_ok,                     # 14. OBV > OBV_MA20
            rsi_pct_ok,                 # 15. RSI Percentile > 60 (V15)
            adx_slope_ok,               # 16. ADX Slope > 0 (V15)
            sektor_rs_ok,               # 17. Sektör RS (V15)
            atr_pct_ok,                 # 18. ATR Percentile 10-75 (V15)
            vcp_ok,                     # 19. VCP Skoru ≥ 2/3 (V15)
            di_spread_ok,               # 20. DI Spread > 10 (V16 YENİ)
            obv_brk_ok,                 # 21. OBV Breakout 20-bar (V16 YENİ)
            vwap_ok is True,            # 22. VWAP üstü (V16 YENİ)
        ]
        skor = sum(sinyaller)
        gap_blocked = not gap_ok

        stop      = fiyat - atr * ATR_MULT
        risk_tl   = max(fiyat - stop, 0.01)
        hedef     = fiyat + risk_tl * 2
        reward_tl = hedef - fiyat
        rr_ratio  = reward_tl / risk_tl

        mhs_score, mhs_detail = market_health_score(xu100, _breadth_pct)
        aktif_risk = regime["risk"]

        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "📐 Planner","🤖 Broker","📊 Backtest",
            "🎯 Filtreler","🏥 MHS","🔬 V15 Pro","⚡ V16 Yeni"
        ])

        # ╔══════════════════════════════════╗
        # ║  TAB 1 — PLANNER               ║
        # ╚══════════════════════════════════╝
        with tab1:
            lot = int((portfoy * aktif_risk) / risk_tl)
            st.markdown(regime_html(regime, "font-size:10px;padding:4px 8px"), unsafe_allow_html=True)
            st.markdown(htf_html(htf_now, secilen), unsafe_allow_html=True)

            if gap_blocked:
                st.warning(f"⚠️ **GAP UYARISI** — Açılış gapi %{gap_pct*100:.2f} > %{GAP_MAX_PCT*100:.0f}  →  Pozisyon boyutunu küçültün veya bekleyin.")

            # V16: VWAP durumu plannerda gösterildi
            if vwap_val is not None and not pd.isna(vwap_val):
                vwap_dist_pct = (fiyat / vwap_val - 1) * 100
                vwap_cls = "#22c55e" if fiyat >= vwap_val else "#ef4444"
                vwap_lbl = "üstünde ✅" if fiyat >= vwap_val else "altında ⚠️"
                st.markdown(
                    f"<div style='background:#0d1421;border-radius:5px;padding:5px 10px;"
                    f"margin-bottom:6px;font-size:10.5px;border-left:3px solid #a78bfa'>"
                    f"<span style='color:#a78bfa;font-weight:700'>VWAP</span>"
                    f"  <span style='color:#94a3b8'>{vwap_val:.2f} TL</span>"
                    f"  <span style='color:{vwap_cls};font-weight:700'>"
                    f"Fiyat VWAP {vwap_lbl} ({vwap_dist_pct:+.2f}%)</span></div>",
                    unsafe_allow_html=True
                )

            st.markdown(metric_grid(
                ("Giriş Fiyatı",   f"{fiyat:.2f} TL",       ""),
                ("Stop Loss",      f"{stop:.2f} TL",         "dn"),
                ("Hedef Fiyat",    f"{hedef:.2f} TL",        "up"),
                ("Önerilen Lot",   f"{lot} adet",            "up" if fiyat > sma else "wn"),
                ("Maliyet",        f"{lot*fiyat:,.0f} TL",   ""),
                ("Risk / İşlem",   f"%{aktif_risk*100:.1f}", "wn"),
            ), unsafe_allow_html=True)
            st.markdown(rr_bar_html(risk_tl, reward_tl, rr_ratio), unsafe_allow_html=True)
            st.markdown(mhs_html(mhs_score, mhs_detail), unsafe_allow_html=True)
            st.caption("⏱️ 15dk gecikmeli veri — giriş öncesi teyit alın.")

        # ╔══════════════════════════════════╗
        # ║  TAB 2 — BROKER                ║
        # ╚══════════════════════════════════╝
        with tab2:
            if fr["css"] in ("fb-yellow","fb-red") and not fr["is_closed"]:
                st.markdown(freshness_html(fr,"font-size:10px;padding:3px 8px"), unsafe_allow_html=True)

            if gap_blocked:
                st.markdown(
                    f"<div class='sr nok' style='margin-bottom:6px'>"
                    f"<span class='sl'>⛔ GAP BLOCKER</span>"
                    f"<span class='sv dn'>Açılış gapi %{gap_pct*100:.2f} — Sinyal geçersiz</span></div>",
                    unsafe_allow_html=True
                )

            st.markdown(karar_html(skor, len(sinyaller)), unsafe_allow_html=True)
            st.markdown(htf_html(htf_now, secilen), unsafe_allow_html=True)

            st.markdown(sec_div("Fiyat & Momentum"), unsafe_allow_html=True)
            st.markdown(metric_grid(
                ("Değişim (~6.5s)", f"{'+'if deg_pct>=0 else ''}{deg_pct:.2f}%",
                 "up" if deg_pct >= 0 else "dn"),
                ("SMA20 Uzaklığı",  f"{'+'if sma_pct>=0 else ''}{sma_pct:.2f}%",
                 "up" if sma_pct >= 0 else "dn"),
                ("RSI (14)",        f"{rsi:.1f}",  rz_cls),
                ("RSI Percentile",  f"P{rsi_pct_val:.0f}", "up" if rsi_pct_ok else "wn"),
                ("ADX (14)",        f"{adx_val:.1f}", "up" if adx_ok else "wn"),
                ("ADX Slope",       f"{'↑' if adx_slope_ok else '↓'} {adx_slope_val:.2f}",
                 "up" if adx_slope_ok else "dn"),
                ("DI Spread",       f"+{di_spread_val:.1f}", "up" if di_spread_ok else ("wn" if di_spread_val > 0 else "dn")),
                ("VWAP",            f"{vwap_val:.2f}" if (vwap_val and not pd.isna(vwap_val)) else "—",
                 "up" if (vwap_ok is True) else ("dn" if (vwap_ok is False) else "")),
                ("ATR Percentile",  f"P{atr_pct_val:.0f}", "up" if atr_pct_ok else "wn"),
                ("VCP Skoru",       f"{vcp_s}/3", "up" if vcp_ok else ("wn" if vcp_s == 1 else "dn")),
            ), unsafe_allow_html=True)

            st.markdown(sec_div("Hacim & OBV Analizi"), unsafe_allow_html=True)
            st.markdown(vol_bar_html(vol_now, vol_ma, vol_ratio, vol_confirmed, vol_pct),
                        unsafe_allow_html=True)

            st.markdown(sec_div("Destek & Direnç  (★ = çoklu test)"), unsafe_allow_html=True)
            if supports or resistances:
                st.markdown(level_rows_html(fiyat, supports, resistances, vwap_val),
                            unsafe_allow_html=True)
            else:
                st.caption("Pivot bulunamadı.")

            st.markdown(sec_div("Risk / Ödül"), unsafe_allow_html=True)
            st.markdown(rr_bar_html(risk_tl, reward_tl, rr_ratio), unsafe_allow_html=True)

            st.markdown(sec_div("Sinyal Detayı (V16: 22 Filtre)"), unsafe_allow_html=True)
            rs_ab_h = (
                f"<div class='sr unk'><span class='sl'>RS vs XU100</span>"
                f"<span class='sv wn'>📡 Veri Yok</span></div>"
                if rs_now is None else
                sig_row_html("RS vs XU100", rs_now,
                             "💚 XU100'den Güçlü","🔴 XU100'den Zayıf")
            )
            rs_sl_h = (
                f"<div class='sr unk'><span class='sl'>RS Slope</span>"
                f"<span class='sv wn'>📡 Veri Yok</span></div>"
                if rs_slope_now is None else
                sig_row_html("RS Slope (Hız)", rs_slope_now,
                             "📈 Hızlanıyor","📉 Yavaşlıyor")
            )
            st.markdown(
                sig_row_html("Trend (SMA20)",     fiyat > sma,
                             "✅ Pozitif","❌ Negatif") +
                sig_row_html("RSI Bandı",          rsi_ok,
                             f"✅ {rsi:.1f} (50-70)",f"⚠️ {rsi:.1f} bant dışı") +
                rs_ab_h + rs_sl_h +
                sig_row_html("Bollinger SQZ",      sqz_now,
                             "🟡 Sıkışma Aktif","⚪ Normal") +
                sig_row_html("Hacim Doğrulama",    vol_confirmed,
                             f"✅ RVOL x{vol_ratio:.1f} Poz.",
                             f"❌ Doğrulanmadı x{vol_ratio:.1f}") +
                sig_row_html("4H HTF Trend",       htf_now,
                             "🟢 4H Bull","🔴 4H Bear",
                             none_txt="⚠️ 4H Veri Yetersiz") +
                sig_row_html("Breakout",           brk_now,
                             f"🚀 {BREAKOUT_BARS}-bar High Kırıldı",
                             "⏳ Kırılım Bekleniyor") +
                sig_row_html("ATR% Bölgesi",       atr_ok,
                             f"✅ %{atr_pct*100:.2f} (1-6)",
                             f"⚠️ %{atr_pct*100:.2f} dışı") +
                sig_row_html("ADX Trend Gücü",     adx_ok,
                             f"💪 ADX {adx_val:.1f} > {ADX_THRESHOLD} (Güçlü)",
                             f"⚠️ ADX {adx_val:.1f} < {ADX_THRESHOLD} (Zayıf)") +
                sig_row_html("ADX Yönü (+DI/-DI)",  adx_dir_ok,
                             f"⬆️ +DI {plus_di:.1f} > -DI {minus_di:.1f} (Yükseliş)",
                             f"⬇️ +DI {plus_di:.1f} < -DI {minus_di:.1f} (Düşüş)") +
                sig_row_html("Volume Percentile",  vol_pct_ok,
                             f"✅ P{vol_pct:.0f} — Üst %30 Hacim",
                             f"⚠️ P{vol_pct:.0f} — Düşük Hacim Dilimi") +
                sig_row_html("ATR Expansion",      atr_exp_ok,
                             "📈 Volatilite Açılıyor — Kırılım Teyidi",
                             "📉 Volatilite Daralıyor — Bekle") +
                sig_row_html("OBV Kurumsal Akış",  obv_ok,
                             "📈 OBV > MA20 — Kurumsal Alım",
                             "📉 OBV < MA20 — Kurumsal Satış / Dağıtım") +
                sig_row_html("Gap Filtresi",        gap_ok,
                             f"✅ Gap %{gap_pct*100:.2f} — Normal Açılış",
                             f"⛔ Gap %{gap_pct*100:.2f} > %{GAP_MAX_PCT*100:.0f} — BLOKE") +
                sig_row_html("RSI Percentile",     rsi_pct_ok,
                             f"✅ P{rsi_pct_val:.0f} Güçlü Konum",
                             f"📊 P{rsi_pct_val:.0f} Henüz Girmedi") +
                sig_row_html("ADX Slope",          adx_slope_ok,
                             f"📈 Trend Güçleniyor (+{adx_slope_val:.2f})",
                             f"📉 Trend Zayıflıyor ({adx_slope_val:.2f})") +
                sig_row_html("Sektör RS",          sektor_rs_ok if rs_sektor_ok is not None else None,
                             f"💚 Sektör Lideri ({sektor_sym or '?'})",
                             f"🔴 Sektör Geride ({sektor_sym or '?'})",
                             none_txt="ℹ️ Sektör Endeksi Yok") +
                sig_row_html("ATR Percentile",     atr_pct_ok,
                             f"✅ P{atr_pct_val:.0f} İdeal Volatilite",
                             f"⚠️ P{atr_pct_val:.0f} Bant Dışı") +
                sig_row_html("VCP (Minervini)",     vcp_ok,
                             f"💎 VCP {vcp_s}/3 — Pattern Hazır",
                             f"⏳ VCP {vcp_s}/3 — Gelişiyor") +
                # V16 yeni sinyaller
                sig_row_html("DI Spread (V16)",    di_spread_ok,
                             f"💪 +DI−−DI = {di_spread_val:.1f} > {DI_SPREAD_MIN} — Güçlü Ayrışma",
                             f"⚠️ +DI−−DI = {di_spread_val:.1f} < {DI_SPREAD_MIN} — Zayıf Ayrışma") +
                sig_row_html("OBV Breakout (V16)", obv_brk_ok,
                             "🚀 OBV 20-bar Zirvesinde — Kurumsal Giriş!",
                             "⏳ OBV Zirve Kırmadı — Birikim Devam") +
                sig_row_html("VWAP Üstü (V16)",   vwap_ok,
                             f"✅ Fiyat VWAP Üstünde ({vwap_val:.2f})" if (vwap_val and not pd.isna(vwap_val)) else "✅ VWAP Üstünde",
                             f"❌ Fiyat VWAP Altında ({vwap_val:.2f})" if (vwap_val and not pd.isna(vwap_val)) else "❌ VWAP Altında",
                             none_txt="📡 VWAP Hesaplanamadı"),
                unsafe_allow_html=True
            )
            st.caption("⏱️ 15dk gecikmeli veri — giriş öncesi teyit alın.")

        # ╔══════════════════════════════════╗
        # ║  TAB 3 — BACKTEST              ║
        # ╚══════════════════════════════════╝
        with tab3:
            st.caption(f"Maliyet: %{TRADE_COST*100:.2f}/işlem  ·  "
                       f"20 giriş filtresi (V16)  ·  Çıkış: Trend/RS/Stop")
            res = run_backtest(df, xu100)
            if res.get("err"):
                st.info(f"ℹ️ {res['err']}")
            else:
                ret_cls = "up" if res["total"] >= 0 else "dn"
                pf_str  = f"{res['pf']:.2f}" if res["pf"] != float("inf") else "∞"
                st.markdown(metric_grid(
                    ("Robot Getiri",  f"%{res['total']:.2f}", ret_cls),
                    ("Al-Bekle",      f"%{res['bh']:.2f}",    "up" if res["bh"]>=0 else "dn"),
                    ("Win Rate",      f"%{res['wr']:.1f}",    "up" if res["wr"]>=50 else "dn"),
                    ("Profit Factor", pf_str,                  "up" if res["pf"]>1 else "dn"),
                    ("Max Drawdown",  f"%{res['dd']:.1f}",    "dn"),
                    ("İşlem Sayısı",  str(res["n"]),           ""),
                ), unsafe_allow_html=True)
                if res["total"] > res["bh"]:
                    st.success("💪 Robot Piyasayı Yendi! (Maliyet Dahil)")
                else:
                    st.warning("🐢 Al-Bekle Daha İyi (Maliyet Dahil)")
                ec = res["ec"]
                st.markdown(
                    f"<div style='font-size:10px;color:#6b7594;margin-top:4px'>"
                    f"Çıkış → Trend: <b>{ec['Trend']}</b>  "
                    f"RS: <b>{ec['RS']}</b>  Stop: <b>{ec['Stop']}</b></div>",
                    unsafe_allow_html=True
                )
                st.caption(f"⚠️ Kapanış fiyatı bazlı  ·  %{TRADE_COST*100:.2f} maliyet düşüldü.")

        # ╔══════════════════════════════════╗
        # ║  TAB 4 — FİLTRELER (V15 koru)  ║
        # ╚══════════════════════════════════╝
        with tab4:
            evt = st.session_state.event_risks.get(secilen, "📡")

            st.markdown("**1. Bollinger Squeeze**")
            if sqz_now: st.warning("🟡 Sıkışma Aktif — Patlama yaklaşıyor.")
            else:        st.info("⚪ Sıkışma Yok — Normal volatilite.")

            st.markdown("**2. Relative Strength**")
            if   rs_now is None: st.error("📡 XU100 verisi alınamadı.")
            elif rs_now:         st.success("💚 Güçlü — BIST 100'den iyi.")
            else:                st.error("🔴 Zayıf — BIST 100'den kötü.")

            st.markdown("**3. RS Slope**")
            if   rs_slope_now is None: st.info("📡 Hesaplanamadı.")
            elif rs_slope_now:         st.success("📈 Hızlanıyor — Lider adayı.")
            else:                      st.warning("📉 Yavaşlıyor — Dikkat.")

            st.markdown("**4. ADX Trend Gücü**")
            if adx_ok: st.success(f"💪 ADX {adx_val:.1f} > {ADX_THRESHOLD} — Güçlü trend.")
            else:      st.warning(f"⚠️ ADX {adx_val:.1f} < {ADX_THRESHOLD} — Trend zayıf.")

            st.markdown("**5. ADX Yönü (+DI / -DI)**")
            if adx_dir_ok: st.success(f"⬆️ +DI {plus_di:.1f} > -DI {minus_di:.1f} — Yükseliş yönlü.")
            else:          st.error(f"⬇️ +DI {plus_di:.1f} < -DI {minus_di:.1f} — Düşüş yönlü!")

            st.markdown("**6. OBV Kurumsal Akış**")
            if obv_ok: st.success("📈 OBV > MA20 — Kurumsal alım ağırlıklı.")
            else:      st.error("📉 OBV < MA20 — Kurumsal satış / dağıtım baskısı.")

            st.markdown("**7. Gap Filtresi**")
            if gap_ok: st.success(f"✅ Gap %{gap_pct*100:.2f} — Normal, sinyal geçerli.")
            else:
                st.error(f"⛔ Gap %{gap_pct*100:.2f} > %{GAP_MAX_PCT*100:.0f} — Sinyal BLOKE!")
                st.caption("Gap; bilanço, KAP haberi veya bedelsiz sonrası oluşmuş olabilir.")

            st.markdown("**8. Volume Percentile**")
            if vol_pct_ok: st.success(f"✅ P{vol_pct:.0f} — Son 250 mumun üst %30'unda.")
            else:          st.info(f"📊 P{vol_pct:.0f} — Hacim kurumsal giriş eşiğinde değil.")

            st.markdown("**9. ATR Expansion**")
            if atr_exp_ok: st.success("📈 Volatilite açılıyor — Kırılım teyidi güçlü.")
            else:          st.info("📉 Volatilite daralıyor — Sıkışma henüz açılmadı.")

            st.markdown("**10. 4H HTF Trend**")
            st.markdown(htf_html(htf_now, secilen), unsafe_allow_html=True)

            st.markdown("**11. Breakout**")
            if brk_now: st.success(f"🚀 {BREAKOUT_BARS}-bar high kırıldı.")
            else:        st.info("⏳ Kırılım bekleniyor.")

            st.markdown("**12. ATR% Volatilite Rejimi**")
            if atr_ok: st.success(f"✅ ATR% {atr_pct*100:.2f} uygun bölgede (1-6%).")
            else:       st.warning(f"⚠️ ATR% {atr_pct*100:.2f} bant dışı.")

            st.markdown("**13. Event Risk**")
            if   evt == "⚠":  st.warning("⚠️ Risk — Yakın bilanço var.")
            elif evt == "✅": st.success("✅ Temiz takvim.")
            else:              st.info("📡 Sorgulanmamış — Event Risklerini Yükle.")

            st.markdown("**14. Veri Tazeliği**")
            st.markdown(freshness_html(fr), unsafe_allow_html=True)

            st.markdown("**15. RSI Percentile** — *V15*")
            if rsi_pct_ok:
                st.success(f"✅ P{rsi_pct_val:.0f} — RSI son 252 barda güçlü konumda.")
            else:
                st.info(f"📊 P{rsi_pct_val:.0f} — RSI henüz üst %40'a girmedi.")

            st.markdown("**16. ADX Slope** — *V15*")
            if adx_slope_ok:
                st.success(f"📈 ADX eğimi pozitif (+{adx_slope_val:.2f}) — Trend gücü artıyor.")
            else:
                st.warning(f"📉 ADX eğimi negatif ({adx_slope_val:.2f}) — Trend zayıflıyor olabilir.")

            st.markdown("**17. Sektör RS** — *V15*")
            if rs_sektor_ok is None:
                st.info(f"ℹ️ {secilen} için sektör endeksi eşleşmesi yok — XU100 RS geçerli.")
            elif rs_sektor_ok:
                st.success(f"💚 {secilen} sektör endeksinin ({sektor_sym}) üzerinde — Gerçek sektör lideri!")
            else:
                st.error(f"🔴 {secilen} XU100'ü geçse bile sektörünü ({sektor_sym}) geçemiyor.")

            st.markdown("**18. ATR Percentile** — *V15*")
            atr_pct_lbl = ("Düşük — henüz açılmamış" if atr_pct_val <= 10
                           else "Yüksek risk — aşırı volatilite" if atr_pct_val >= 75
                           else "Uygun bölge")
            if atr_pct_ok:
                st.success(f"✅ ATR Percentile P{atr_pct_val:.0f} — {atr_pct_lbl}.")
            else:
                st.warning(f"⚠️ ATR Percentile P{atr_pct_val:.0f} — {atr_pct_lbl}.")

            st.markdown("**19. VCP Skoru (Minervini)** — *V15*")
            vcp_detail = []
            if vcp_price: vcp_detail.append("✅ Fiyat volatilitesi daralıyor")
            else:         vcp_detail.append("❌ Fiyat volatilitesi henüz daralmıyor")
            if vcp_vol:   vcp_detail.append("✅ Hacim daralıyor (kurumsal birikim)")
            else:         vcp_detail.append("❌ Hacim daralması yok")
            if vcp_rs:    vcp_detail.append("✅ Fiyat yükseliyor (RS gücü)")
            else:         vcp_detail.append("❌ Fiyat momentumu yok")
            if vcp_ok:   st.success(f"💎 VCP {vcp_s}/3 — Pattern Hazır!")
            elif vcp_s==1: st.info(f"🔄 VCP {vcp_s}/3 — Gelişiyor.")
            else:          st.warning(f"⏳ VCP {vcp_s}/3 — Pattern yok.")
            for d in vcp_detail: st.caption(d)

            st.markdown("**20–22. V16 Yeni Filtreler** → ⚡ V16 Yeni sekmesine bakın")

        # ╔══════════════════════════════════╗
        # ║  TAB 5 — MHS                   ║
        # ╚══════════════════════════════════╝
        with tab5:
            st.markdown("##### 🏥 Market Health Score")
            st.caption("Piyasa sağlığını 5 kritere göre puanlar ve pozisyon büyüklüğünü otomatik ayarlar.")
            st.markdown(mhs_html(mhs_score, mhs_detail), unsafe_allow_html=True)
            st.markdown(metric_grid(
                ("MHS Skoru",  f"{mhs_score} / 5",    "up" if mhs_score >= 4 else ("wn" if mhs_score >= 2 else "dn")),
                ("Aktif Risk", f"%{aktif_risk*100:.1f}", "up" if aktif_risk == RISK_FULL else ("wn" if aktif_risk == RISK_HALF else "dn")),
            ), unsafe_allow_html=True)
            st.markdown("**Risk Dağılımı:**")
            st.markdown(
                f"<div class='sr ok'><span class='sl'>MHS 4-5 (Risk On)</span>"
                f"<span class='sv up'>%{RISK_FULL*100:.1f} — Tam Pozisyon</span></div>"
                f"<div class='sr unk'><span class='sl'>MHS 2-3 (Nötr)</span>"
                f"<span class='sv wn'>%{RISK_HALF*100:.1f} — Yarı Pozisyon</span></div>"
                f"<div class='sr nok'><span class='sl'>MHS 0-1 (Risk Off)</span>"
                f"<span class='sv dn'>%{RISK_OFF*100:.1f} — Küçük / Bekleme</span></div>",
                unsafe_allow_html=True
            )
            if _breadth_pct is None:
                st.info("💡 'Tüm Listeyi Tara' → Breadth verisi yüklensin.")
            st.markdown("**V14 Piyasa Rejimi:**")
            st.markdown(regime_html(regime), unsafe_allow_html=True)
            st.caption("MHS 4-5 → Tam risk. MHS 2-3 → Dikkatli. MHS 0-1 → Çık / Bekle.")

        # ╔══════════════════════════════════╗
        # ║  TAB 6 — V15 PRO               ║
        # ╚══════════════════════════════════╝
        with tab6:
            st.markdown("##### 🔬 V15 Pro — Adaptif Sinyal Özeti")
            st.caption("RSI Percentile · ADX Slope · Sektör RS · ATR Percentile · VCP")
            st.markdown(metric_grid(
                ("RSI (14)",        f"{rsi:.1f}",              rz_cls),
                ("RSI Percentile",  f"P{rsi_pct_val:.0f}",    "up" if rsi_pct_ok else "wn"),
                ("ADX (14)",        f"{adx_val:.1f}",         "up" if adx_ok else "wn"),
                ("ADX Slope",       f"{'↑' if adx_slope_ok else '↓'}{adx_slope_val:.2f}",
                 "up" if adx_slope_ok else "dn"),
                ("ATR Percentile",  f"P{atr_pct_val:.0f}",    "up" if atr_pct_ok else "wn"),
                ("VCP Skoru",       f"{vcp_s}/3",             "up" if vcp_ok else ("wn" if vcp_s==1 else "dn")),
            ), unsafe_allow_html=True)

            st.markdown(sec_div("RSI Percentile Yorumu"), unsafe_allow_html=True)
            st.markdown(
                f"<div class='sr {'ok' if rsi_pct_ok else 'unk'}'>"
                f"<span class='sl'>RSI={rsi:.1f} → Son 252 barda P{rsi_pct_val:.0f}'de</span>"
                f"<span class='sv {'up' if rsi_pct_ok else 'wn'}'>"
                f"{'Güçlü Konum' if rsi_pct_ok else 'Henüz Üst Banda Girmedi'}</span></div>",
                unsafe_allow_html=True
            )
            st.caption("RSI=62 tek başına anlamsız. Ama P92'deyse son 252 barda %92'lik üst konumda — çok anlamlı.")

            st.markdown(sec_div("ADX Slope Yorumu"), unsafe_allow_html=True)
            st.markdown(
                f"<div class='sr {'ok' if adx_slope_ok else 'nok'}'>"
                f"<span class='sl'>ADX={adx_val:.1f} · Eğim {ADX_SLOPE_BARS} bar</span>"
                f"<span class='sv {'up' if adx_slope_ok else 'dn'}'>"
                f"{'↑ Trend güçleniyor' if adx_slope_ok else '↓ Trend zayıflıyor'} ({adx_slope_val:+.2f})</span></div>",
                unsafe_allow_html=True
            )
            st.caption("ADX=30 ama düşüyorsa trend güç kaybediyor. Slope pozitif olanlar false breakout'u temizler.")

            st.markdown(sec_div("Sektör RS — Çift Referans"), unsafe_allow_html=True)
            if rs_sektor_ok is None:
                st.info(f"ℹ️ {secilen} için sektör haritasında eşleşme yok.")
            else:
                xu_lbl  = f"✅ {secilen} > XU100" if rs_xu100_ok else f"❌ {secilen} < XU100"
                sek_lbl = f"✅ {secilen} > {sektor_sym or '?'}" if rs_sektor_ok else f"❌ {secilen} < {sektor_sym or '?'}"
                st.markdown(
                    f"<div class='sr {'ok' if rs_xu100_ok else 'nok'}'>"
                    f"<span class='sl'>RS vs XU100</span>"
                    f"<span class='sv {'up' if rs_xu100_ok else 'dn'}'>{xu_lbl}</span></div>"
                    f"<div class='sr {'ok' if rs_sektor_ok else 'nok'}'>"
                    f"<span class='sl'>RS vs Sektör ({sektor_sym or '?'})</span>"
                    f"<span class='sv {'up' if rs_sektor_ok else 'dn'}'>{sek_lbl}</span></div>",
                    unsafe_allow_html=True
                )
                if rs_xu100_ok and not rs_sektor_ok:
                    st.warning(f"⚠️ {secilen} XU100'ü geçiyor ama sektörünü ({sektor_sym}) geçemiyor.")
                elif rs_xu100_ok and rs_sektor_ok:
                    st.success(f"💎 Çift RS pozitif — Hem sektör hem piyasa lideri!")

            st.markdown(sec_div("ATR Percentile"), unsafe_allow_html=True)
            st.markdown(
                f"<div class='sr {'ok' if atr_pct_ok else 'unk'}'>"
                f"<span class='sl'>ATR Percentile (Son {ATR_PCT_LOOKBACK} bar)</span>"
                f"<span class='sv {'up' if atr_pct_ok else 'wn'}'>P{atr_pct_val:.0f} — "
                f"{'İdeal Bölge' if atr_pct_ok else ('Çok Düşük' if atr_pct_val <= 10 else 'Çok Yüksek')}</span></div>",
                unsafe_allow_html=True
            )

            st.markdown(sec_div("VCP — Volatility Contraction Pattern"), unsafe_allow_html=True)
            vcp_css = "ok" if vcp_ok else ("unk" if vcp_s == 1 else "nok")
            vcp_cls = "up" if vcp_ok else ("wn" if vcp_s == 1 else "dn")
            st.markdown(
                f"<div class='sr {vcp_css}'>"
                f"<span class='sl'>VCP Skoru (Minervini)</span>"
                f"<span class='sv {vcp_cls}'>{vcp_s}/3 — "
                f"{'Pattern Hazır 💎' if vcp_ok else ('Gelişiyor 🔄' if vcp_s==1 else 'Pattern Yok ⏳')}</span></div>"
                f"<div class='sr {'ok' if vcp_price else 'nok'}'><span class='sl'>① Fiyat Volatilitesi Daralıyor</span>"
                f"<span class='sv {'up' if vcp_price else 'dn'}'>{'✅' if vcp_price else '❌'}</span></div>"
                f"<div class='sr {'ok' if vcp_vol else 'nok'}'><span class='sl'>② Hacim Daralıyor (&lt;%75 ort.)</span>"
                f"<span class='sv {'up' if vcp_vol else 'dn'}'>{'✅' if vcp_vol else '❌'}</span></div>"
                f"<div class='sr {'ok' if vcp_rs else 'nok'}'><span class='sl'>③ Fiyat Momentumu Yukarı</span>"
                f"<span class='sv {'up' if vcp_rs else 'dn'}'>{'✅' if vcp_rs else '❌'}</span></div>",
                unsafe_allow_html=True
            )

        # ╔══════════════════════════════════╗
        # ║  TAB 7 — V16 YENİ (3 filtre)   ║
        # ╚══════════════════════════════════╝
        with tab7:
            st.markdown("##### ⚡ V16 — DI Spread · OBV Breakout · VWAP")
            st.caption(
                "ChatGPT analizinden seçilen 3 kritik filtre. "
                "Bu üç filtre gerçek trend gücünü ve kurumsal para akışını ölçer."
            )

            # ── DI SPREAD ────────────────────────────────────────────────────
            st.markdown(sec_div("① DI Spread Filtresi — Gerçek Trend Ayrışması"), unsafe_allow_html=True)
            di_cls  = "ok" if di_spread_ok else "nok"
            di_vcls = "up" if di_spread_ok else "dn"
            st.markdown(
                f"<div class='sr {di_cls}'>"
                f"<span class='sl'>+DI − −DI Farkı (Eşik: >{DI_SPREAD_MIN})</span>"
                f"<span class='sv {di_vcls}'>{di_spread_val:+.1f} — "
                f"{'Güçlü Ayrışma 💪' if di_spread_ok else 'Zayıf Ayrışma ⚠️'}</span></div>",
                unsafe_allow_html=True
            )
            st.markdown(metric_grid(
                ("+DI",        f"{plus_di:.1f}",    "up"),
                ("-DI",        f"{minus_di:.1f}",   "dn"),
                ("Fark",       f"{di_spread_val:+.1f}", "up" if di_spread_ok else "dn"),
                ("Eşik",       f"> {DI_SPREAD_MIN}", "wn"),
            ), unsafe_allow_html=True)
            if di_spread_ok:
                st.success(
                    f"💪 **Güçlü Ayrışma ({di_spread_val:.1f}):** +DI ile -DI arasındaki fark {DI_SPREAD_MIN}'in üstünde. "
                    f"Bu, yükseliş yönünün gerçek anlamda baskın olduğunu gösterir. "
                    f"ADX=28, +DI=42, -DI=15 gibi bir tablo çok daha güçlüdür.")
            else:
                st.warning(
                    f"⚠️ **Zayıf Ayrışma ({di_spread_val:.1f}):** +DI ile -DI arasında yeterli fark yok. "
                    f"Örnek: ADX=30, +DI=27, -DI=25 → ADX güçlü görünse de trend yönü belirsiz. "
                    f"False breakout riski yüksek.")
            st.caption("Neden önemli? ADX tek başına trend yönü söylemez. DI Spread olmadan ADX güçlü görünüp yanlış yönde olabilir.")

            # ── OBV BREAKOUT ─────────────────────────────────────────────────
            st.markdown(sec_div("② OBV Breakout — Kurumsal Para Girişi Teyidi"), unsafe_allow_html=True)
            obv_cls  = "ok" if obv_brk_ok else ("unk" if obv_ok else "nok")
            obv_vcls = "up" if obv_brk_ok else ("wn" if obv_ok else "dn")
            st.markdown(
                f"<div class='sr {obv_cls}'>"
                f"<span class='sl'>OBV vs Son {OBV_BRK_LOOKBACK}-bar Zirvesi</span>"
                f"<span class='sv {obv_vcls}'>"
                f"{'🚀 Zirveyi Kırdı — Kurumsal Giriş!' if obv_brk_ok else ('📈 MA20 üstünde ama zirve yok' if obv_ok else '📉 OBV Zayıf')}"
                f"</span></div>",
                unsafe_allow_html=True
            )
            st.markdown(metric_grid(
                ("OBV Şimdiki",  f"{obv_now:,.0f}",    "up" if obv_ok else "dn"),
                ("OBV MA20",     f"{obv_ma:,.0f}",     ""),
                ("OBV 20-bar Max", f"{obv_high20:,.0f}", "wn"),
                ("Breakout",     "✅ Evet" if obv_brk_ok else "❌ Hayır",
                 "up" if obv_brk_ok else "dn"),
            ), unsafe_allow_html=True)
            if obv_brk_ok:
                st.success(
                    "🚀 **OBV Yeni Zirve:** OBV son 20 barın maksimumunu kırdı. "
                    "Bu, kurumsal para akışının ivme kazandığını ve fiyat kırılımını desteklediğini gösterir. "
                    "En kaliteli hacim sinyali!")
            elif obv_ok:
                st.info(
                    "📈 **OBV Pozitif ama Zirve Yok:** OBV MA20 üstünde ancak henüz "
                    f"son {OBV_BRK_LOOKBACK} barın zirvesini kırmadı. "
                    "Kurumsal birikim devam ediyor, kırılım için bekle.")
            else:
                st.warning(
                    "📉 **OBV Zayıf:** OBV MA20 altında. Fiyat yükselirken OBV yükselmiyorsa "
                    "bu dağıtım (distribution) işareti olabilir — dikkat!")
            st.caption("V15'te OBV > MA20 yeterliydi. V16'da OBV'nin son 20 barın zirvesini kırması şartı eklendi — daha seçici.")

            # ── VWAP ─────────────────────────────────────────────────────────
            st.markdown(sec_div("③ VWAP Filtresi — Kurumsal Maliyet Seviyesi"), unsafe_allow_html=True)
            if vwap_val is not None and not pd.isna(vwap_val):
                vwap_dist_pct = (fiyat / vwap_val - 1) * 100
                vw_cls  = "ok" if (fiyat >= vwap_val) else "nok"
                vw_vcls = "up" if (fiyat >= vwap_val) else "dn"
                vwap_lbl = "Fiyat VWAP Üstünde ✅" if fiyat >= vwap_val else "Fiyat VWAP Altında ❌"
                st.markdown(
                    f"<div class='sr {vw_cls}'>"
                    f"<span class='sl'>VWAP = {vwap_val:.2f} TL  |  Fiyat = {fiyat:.2f} TL</span>"
                    f"<span class='sv {vw_vcls}'>{vwap_lbl} ({vwap_dist_pct:+.2f}%)</span></div>",
                    unsafe_allow_html=True
                )
                st.markdown(metric_grid(
                    ("VWAP",           f"{vwap_val:.2f} TL",       ""),
                    ("Fiyat",          f"{fiyat:.2f} TL",          "up" if fiyat >= vwap_val else "dn"),
                    ("VWAP Farkı",     f"{vwap_dist_pct:+.2f}%",  "up" if fiyat >= vwap_val else "dn"),
                    ("Konum",          "Üstünde" if fiyat >= vwap_val else "Altında",
                     "up" if fiyat >= vwap_val else "dn"),
                ), unsafe_allow_html=True)
                if fiyat >= vwap_val:
                    st.success(
                        f"✅ **VWAP Üstü ({vwap_dist_pct:+.2f}%):** Fiyat günlük VWAP'ın üzerinde. "
                        "VWAP, kurumsal yatırımcıların ortalama maliyet seviyesidir. "
                        "Bu seviyenin üzerinde işlem görmek, alıcıların kontrolde olduğunu gösterir.")
                else:
                    st.error(
                        f"❌ **VWAP Altı ({vwap_dist_pct:+.2f}%):** Fiyat günlük VWAP'ın altında. "
                        "Kurumsal yatırımcıların çoğu zararda — satış baskısı devam edebilir. "
                        "VWAP üzerine çıkış için beklemek önerilir.")
                st.caption(
                    "VWAP (Volume Weighted Average Price): Hacimle ağırlıklandırılmış ortalama fiyat. "
                    "Her gün sıfırlanır. Kurumsal fonlar ve algoritmalar bu seviyeyi referans alır."
                )
            else:
                st.warning("📡 VWAP hesaplanamadı — veri yeterli değil.")

            # Özet bölümü
            st.markdown(sec_div("V16 Özet Skoru (3/3)"), unsafe_allow_html=True)
            v16_toplam = int(di_spread_ok) + int(obv_brk_ok) + int(vwap_ok is True)
            v16_cls = "ok" if v16_toplam == 3 else ("unk" if v16_toplam >= 2 else "nok")
            v16_vcls = "up" if v16_toplam == 3 else ("wn" if v16_toplam >= 2 else "dn")
            v16_lbl = {3:"💎 Tüm V16 Filtreleri Geçti — En Kaliteli Sinyal!",
                       2:"🟡 2/3 V16 Filtresi Geçti — Kısmi Onay",
                       1:"⚠️ 1/3 V16 Filtresi — Dikkatli Ol",
                       0:"🔴 V16 Filtreleri Geçilemedi — Bekle"}
            st.markdown(
                f"<div class='sr {v16_cls}'>"
                f"<span class='sl'>V16 Toplam (DI Spread + OBV Brk + VWAP)</span>"
                f"<span class='sv {v16_vcls}'>{v16_toplam}/3 — {v16_lbl[v16_toplam]}</span></div>",
                unsafe_allow_html=True
            )
            st.caption(
                "V16 = 22 filtre toplam.  \n"
                f"✅ DI Spread > {DI_SPREAD_MIN}: {'Geçti' if di_spread_ok else 'Geçemedi'}  \n"
                f"✅ OBV Breakout: {'Geçti' if obv_brk_ok else 'Geçemedi'}  \n"
                f"✅ VWAP Üstü: {'Geçti' if (vwap_ok is True) else 'Geçemedi'}"
            )
    else:
        st.warning("Seçili hisse için veri alınamadı.")