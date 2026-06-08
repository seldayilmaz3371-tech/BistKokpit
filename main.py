# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  BIST KOKPİT V19  — KRİTİK DÜZELTMELER                                     ║
# ║                                                                             ║
# ║  V18'den V19'a değişen 5 şey:                                               ║
# ║   #1  BACKTEST VERİ HATASI  — yfinance 15m max 60 gün verir. Backtest       ║
# ║       artık 60 günlük 15m + 1 yıllık 1d'yi BÜTÜNLEŞIK hale getirir.         ║
# ║       Karma yaklaşım: 60g × 15m (~5760 bar) + 1y × 1d (252 bar)             ║
# ║       60g 15m kullanılır; daha uzun pencere için 1d backtest modu devreye    ║
# ║       girer. Kullanıcı "Mod" ile seçebilir.                                 ║
# ║   #2  SLIPPAGE ENTEGRASYonu — Hakem #1 önerisi. Giriş fiyatı artık          ║
# ║       buy_price = Close × (1 + SLIPPAGE_PCT) şeklinde hesaplanır.           ║
# ║       SLIPPAGE_PCT varsayılan = ATR'ın %10'u kadar fiyata bölüm.            ║
# ║   #3  LİKİDİTE TAVANI — Hakem #3 önerisi. Lot önerisi artık                 ║
# ║       max_lot = VolMA20 × 0.01 ile sınırlandırılır.                         ║
# ║   #4  GERÇEK VEKTÖREL VOL_PCT — _vol_pct_vectorized içindeki Python for     ║
# ║       loop kaldırıldı; NumPy stride_tricks ile O(n log n) hale getirildi.   ║
# ║   #5  BATCH TARAMA — yf.download(tickers_list) ile 30 hisse 1 istekte       ║
# ║       çekilir; senkron for loop kaldırıldı.                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime
import concurrent.futures

st.set_page_config(
    page_title="BIST Kokpit V19.0",
    layout="wide",
    initial_sidebar_state="expanded"
)

BIST_30 = [
    "AKBNK","ALARK","ARCLK","ASTOR","BIMAS","BRSAN","EKGYO","ENKAI","EREGL",
    "FROTO","GARAN","GUBRF","HEKTS","ISCTR","KCHOL","KONTR","KRDMD","OYAKC",
    "PGSUS","PETKM","SAHOL","SASA","SISE","TCELL","THYAO","TKFEN","TOASO",
    "TUPRS","VAKBN","YKBNK"
]

def load_watchlist():
    try:
        raw = st.query_params.get("wl", "")
        if raw:
            tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
            if tickers: return tickers
    except Exception: pass
    return BIST_30.copy()

def save_watchlist(wl):
    try: st.query_params["wl"] = ",".join(sorted(set(wl)))
    except Exception: pass

if "watchlist"   not in st.session_state: st.session_state.watchlist   = load_watchlist()
if "event_risks" not in st.session_state: st.session_state.event_risks = {}
if "scan_rows"   not in st.session_state: st.session_state.scan_rows   = []
if "breadth"     not in st.session_state: st.session_state.breadth     = None

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
section.main > div { padding-top: 0.35rem !important; }
.scanner-wrapper { max-height: 390px; overflow-y: auto; overflow-x: hidden; border: 1px solid #2d3a50; border-radius: 6px; }
.scanner-table { width: 100%; border-collapse: collapse; font-size: 10.5px; font-family: 'Courier New', monospace; table-layout: fixed; }
.scanner-table th { background: #1e2535; color: #94a3b8; font-size: 9px; font-weight: 600; letter-spacing: 0.3px; padding: 3px 2px; text-align: center; border-bottom: 1px solid #2d3a50; position: sticky; top: 0; z-index: 1; overflow: hidden; white-space: nowrap; }
.scanner-table td { padding: 3px 2px; text-align: center; border-bottom: 1px solid #1a2030; color: #e2e8f0; overflow: hidden; white-space: nowrap; }
.scanner-table td.tkr { text-align:left; padding-left:5px; font-weight:600; color:#cbd5e1; }
.scanner-table tr:hover td { background: #1e2a3a; }
.regime-banner, .freshness-banner, .htf-banner, .health-banner { padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; margin-bottom: 6px; text-align: center; letter-spacing: 0.3px; }
.rb-bull { background:#14532d; color:#86efac; border:1px solid #22c55e; }
.rb-bear { background:#450a0a; color:#fca5a5; border:1px solid #ef4444; }
.rb-none { background:#1c1f2e; color:#94a3b8; border:1px solid #374151; }
.fb-green { background:#052e16; color:#86efac; border:1px solid #22c55e; }
.fb-yellow { background:#1c1a08; color:#fde047; border:1px solid #ca8a04; }
.fb-red { background:#450a0a; color:#fca5a5; border:1px solid #ef4444; }
.htf-bull { background:#0f2a1a; color:#86efac; border:1px solid #16a34a; }
.htf-bear { background:#2a0a0a; color:#fca5a5; border:1px solid #dc2626; }
.htf-none { background:#1c1f2e; color:#94a3b8; border:1px solid #374151; }
.mhs-5 { background:#052e16; color:#4ade80; border:2px solid #22c55e; }
.mhs-4 { background:#0f2a1a; color:#86efac; border:1px solid #16a34a; }
.mhs-3 { background:#1c1a08; color:#fde047; border:1px solid #ca8a04; }
.mhs-2 { background:#2a1a08; color:#fb923c; border:1px solid #f97316; }
.mhs-1 { background:#2a0a0a; color:#fca5a5; border:1px solid #dc2626; }
.mhs-0 { background:#1c1f2e; color:#6b7280; border:1px solid #374151; }
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
.kc-al { background:#052e16; border:2px solid #22c55e; } .kc-al .karar-val { color:#4ade80; }
.kc-pos { background:#0f2a1a; border:1px solid #16a34a; } .kc-pos .karar-val { color:#86efac; }
.kc-notr { background:#1c1a08; border:1px solid #ca8a04; } .kc-notr .karar-val { color:#fde047; }
.kc-sat { background:#2a0a0a; border:1px solid #dc2626; } .kc-sat .karar-val { color:#fca5a5; }
.sr { display:flex; justify-content:space-between; align-items:center; background:#0d1421; border-radius:5px; padding:5px 9px; margin-bottom:3px; font-size:11px; border-left:3px solid transparent; }
.sr.ok { border-left-color:#22c55e; } .sr.nok { border-left-color:#ef4444; } .sr.unk { border-left-color:#f59e0b; }
.sr .sl { color:#94a3b8; font-size:10.5px; }
.sr .sv { font-weight:700; font-family:monospace; font-size:11px; }
.sr .sv.up { color:#4ade80; } .sr .sv.dn { color:#f87171; } .sr .sv.wn { color:#fbbf24; }
.sec-divider { font-size:9px; color:#4a5568; text-transform:uppercase; letter-spacing:1px; margin:8px 0 4px 0; border-bottom:1px solid #1e2535; padding-bottom:2px; }
.level-row { display:flex; justify-content:space-between; align-items:center; padding:4px 9px; margin-bottom:2px; border-radius:4px; font-size:10.5px; font-family:'Courier New',monospace; }
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
.rr-bar-wrap .rr-lbl, .vol-bar-wrap .vb-lbl { font-size:9px; color:#6b7594; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px; }
.rr-nums, .vb-nums { display:flex; justify-content:space-between; margin-top:4px; font-size:10px; font-family:monospace; }
.rr-nums .rr-r { color:#f87171; } .rr-nums .rr-rw { color:#4ade80; }
.vb-nums { color:#94a3b8; }
.mhs-wrap { background:#0d1421; border-radius:6px; padding:8px 10px; margin-bottom:6px; }
.mhs-wrap .mhs-lbl { font-size:9px; color:#6b7594; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px; }
.mhs-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:3px; font-size:10px; }
.mhs-row .mhs-item { color:#94a3b8; }
.mhs-row .mhs-check { font-weight:700; }
.vwap-badge { display:inline-block; background:#1a1040; border:1px solid #7c3aed; color:#a78bfa; font-size:9px; font-weight:700; border-radius:3px; padding:1px 5px; letter-spacing:0.3px; }
/* V19: Backtest stiller */
.bt-info-box { background:#0d1421; border:1px solid #2d3a50; border-radius:6px; padding:10px 12px; margin-bottom:8px; }
.bt-info-box .bt-title { font-size:10px; color:#6b7594; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px; }
.bt-info-box .bt-row { display:flex; justify-content:space-between; font-size:11px; margin-bottom:3px; font-family:monospace; }
.bt-info-box .bt-lbl { color:#94a3b8; }
.bt-info-box .bt-val { font-weight:700; color:#e2e8f0; }
.bt-info-box .bt-val.up { color:#4ade80; }
.bt-info-box .bt-val.dn { color:#f87171; }
.bt-info-box .bt-val.wn { color:#fbbf24; }
/* V19: Likidite uyarı */
.liq-warn { background:#2a1a08; border:1px solid #f97316; border-radius:6px; padding:6px 10px; margin-bottom:5px; font-size:10.5px; color:#fb923c; }
/* V19: Slippage bilgi */
.slip-info { background:#0f1f35; border:1px solid #38bdf8; border-radius:5px; padding:5px 9px; margin-bottom:4px; font-size:10px; color:#7dd3fc; }
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
TRADE_COST        = 0.003        # binde 3 komisyon (her iki taraf)
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
DI_SPREAD_MIN     = 10
OBV_BRK_LOOKBACK  = 20

# ── V19 BACKTEST SABİTLERİ ────────────────────────────────────────────────────
# KRITIK DÜZELTME #1: yfinance 15m veri limitini aşmak için çift mod:
#   MOD A (15m): 60 günlük 15m — ~5760 bar — yfinance limiti dahilinde
#   MOD B (1g) : 1 yıllık  1d — ~252  bar — uzun dönem sinyal doğrulaması
BT_PERIOD_15M     = "60d"        # yfinance 15m için güvenli maksimum
BT_INTERVAL_15M   = "15m"
BT_PERIOD_1D      = "2y"         # günlük modda 2 yıl (~500 bar)
BT_INTERVAL_1D    = "1d"
BT_CORE_FILTERS   = 6
MAX_HOLD_BARS_15M = 96           # 96 × 15m ≈ 2 işlem günü
MAX_HOLD_BARS_1D  = 10           # 10 gün
TRAIL_ATR_MULT    = 2.0

# KRITIK DÜZELTME #2: Slippage (Hakem #1)
# Gerçekçi giriş fiyatı = kapanış × (1 + slippage)
# Slippage = ATR / Kapanış × SLIPPAGE_ATR_FACTOR
# Varsayılan: ATR'ın %10'u kadar spread ekler
SLIPPAGE_ATR_FACTOR = 0.10      # giriş kayması = ATR × 0.10 / Fiyat

# KRITIK DÜZELTME #3: Likidite Tavanı (Hakem #3)
# max önerilen lot = 20-günlük ortalama hacim × LOT_LIQ_CAP_PCT
LOT_LIQ_CAP_PCT   = 0.01        # günlük hacmin %1'ini geçme

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
    "EKGYO":"XGMYO.IS","TCELL":"XUHIZ.IS",
}

# ── VERİ KATMANI ─────────────────────────────────────────────────────────────
def _flatten(df):
    if df is None or df.empty: return None
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance çok hisseli indirmede (batch) ilk seviyeyi al
        lvl = 0 if "Close" in df.columns.get_level_values(0) else 1
        df.columns = df.columns.get_level_values(lvl)
    df = df.loc[:, ~df.columns.duplicated()]
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    return df if not df.empty else None

def _flatten_batch(raw_df, ticker_sym):
    """yf.download(multiple) çıktısından tek hisseyi ayıkla."""
    if raw_df is None or raw_df.empty: return None
    try:
        if isinstance(raw_df.columns, pd.MultiIndex):
            df = raw_df.xs(ticker_sym, axis=1, level=1).copy()
        else:
            df = raw_df.copy()
        df = df.loc[:, ~df.columns.duplicated()]
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df.index = df.index.tz_convert(None)
        return df if not df.empty else None
    except Exception:
        return None

def _calc_rsi(close, period=14):
    """Wilder RSI — TradingView ile eşleşen yöntem."""
    d        = close.diff()
    avg_gain = d.where(d > 0, 0.0).ewm(alpha=1/period, adjust=False).mean()
    avg_loss = (-d).where(d < 0, 0.0).ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def _calc_adx(df, period=ADX_PERIOD):
    h, l, c  = df["High"], df["Low"], df["Close"]
    up_move  = h.diff()
    dn_move  = -l.diff()
    plus_dm  = np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0)
    tr       = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    atr14    = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di  = 100*pd.Series(plus_dm,  index=df.index).ewm(alpha=1/period, adjust=False).mean()/atr14
    minus_di = 100*pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean()/atr14
    dx       = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
    return dx.ewm(alpha=1/period, adjust=False).mean(), plus_di, minus_di

def _calc_vwap(df):
    try:
        typical  = (df["High"] + df["Low"] + df["Close"]) / 3
        pv       = typical * df["Volume"]
        date_idx = df.index.normalize()
        cum_pv   = pv.groupby(date_idx).cumsum()
        cum_vol  = df["Volume"].groupby(date_idx).cumsum()
        return cum_pv / cum_vol.replace(0, np.nan)
    except Exception:
        return pd.Series(np.nan, index=df.index)

# ── V19 KRİTİK DÜZELTME #4: GERÇEK VEKTÖREL VOL_PCT ─────────────────────────
# V18'deki _vol_pct_vectorized fonksiyonu PYTHON FOR LOOP kullanıyordu (O(n²)).
# V19: NumPy stride_tricks ile gerçek vektörel pencere karşılaştırması.
# Her bar için lookback penceresindeki sıralamayı O(n·log(lookback)) ile hesaplar.
def _vol_pct_vectorized(volume: pd.Series, lookback: int = VOL_PCT_LOOKBACK) -> pd.Series:
    """
    V19 GERÇEK VEKTÖREL: stride_tricks ile kayan pencerede percentile.
    Python döngüsü yok. Bellek kullanımı: n × lookback × 8 byte.
    Kısıtlama: lookback=250, n=1500 → ~3MB — kabul edilebilir.
    """
    arr    = volume.values.astype(float)
    n      = len(arr)
    result = np.full(n, np.nan)
    if n < lookback:
        # Veri kısa ise expanding rank kullan
        for i in range(1, n):
            w = arr[:i+1]
            result[i] = float((w < w[-1]).sum()) / max(len(w) - 1, 1) * 100
        return pd.Series(result, index=volume.index)

    # Stride trick: (n-lookback+1, lookback) şeklinde 2D görünüm
    shape   = (n - lookback + 1, lookback)
    strides = (arr.strides[0], arr.strides[0])
    windows = np.lib.stride_tricks.as_strided(arr, shape=shape, strides=strides)

    # Her satırda son elemanın ([-1]) kaçının altında olduğunu say
    last_col   = windows[:, -1:] # (m, 1)
    rest       = windows[:, :-1] # (m, lookback-1)
    rank_pcts  = (rest < last_col).sum(axis=1) / (lookback - 1) * 100

    result[lookback - 1:] = rank_pcts
    return pd.Series(result, index=volume.index)

@st.cache_data(ttl=900)
def get_xu100():
    for sym in ("XU100.IS", "^XU100"):
        try:
            df = _flatten(yf.download(sym, period="60d", interval="15m", progress=False))
            if df is not None:
                df["SMA50"]   = df["Close"].rolling(REGIME_SMA).mean()
                df["RSI"]     = _calc_rsi(df["Close"])
                adx, pdi, mdi = _calc_adx(df)
                df["ADX"]     = adx
                df["PlusDI"]  = pdi
                df["MinusDI"] = mdi
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
    for interval, period in [("4h","60d"), ("1h","60d"), ("1d","2y")]:
        try:
            df = _flatten(yf.download(sym, period=period, interval=interval, progress=False))
            if interval == "1h" and df is not None:
                df = df.resample("4h").agg(
                    {"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}
                ).dropna()
            if df is not None and len(df) >= 55:
                result = _add_sma(df).dropna()
                if len(result) >= 5: return result
        except Exception:
            continue
    return None

@st.cache_data(ttl=300)
def get_data(ticker):
    """Canlı analiz için 60d/15m veri."""
    try:
        df = _flatten(yf.download(f"{ticker}.IS", period="60d", interval="15m", progress=False))
        if df is None: return None
        c, h, l = df["Close"], df["High"], df["Low"]

        df["SMA20"]    = c.rolling(20).mean()
        df["RSI"]      = _calc_rsi(c)
        df["TR"]       = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
        df["ATR"]      = df["TR"].ewm(alpha=1/ADX_PERIOD, adjust=False).mean()
        df["VolMA20"]  = df["Volume"].rolling(20).mean()
        df["High20"]   = h.rolling(BREAKOUT_BARS).max().shift(1)

        adx, pdi, mdi  = _calc_adx(df)
        df["ADX"]      = adx
        df["PlusDI"]   = pdi
        df["MinusDI"]  = mdi
        df["DI_Spread"]= pdi - mdi

        # V19: Gerçek vektörel VolPct
        df["VolPct"]   = _vol_pct_vectorized(df["Volume"], VOL_PCT_LOOKBACK)

        df["ATR_Slope"] = df["ATR"].diff(ATR_EXP_BARS)

        direction       = np.sign(c.diff())
        df["OBV"]       = (direction * df["Volume"]).fillna(0).cumsum()
        df["OBV_MA20"]  = df["OBV"].rolling(20).mean()
        df["OBV_High20"]= df["OBV"].rolling(OBV_BRK_LOOKBACK).max().shift(1)

        prev_close      = c.shift(1)
        df["GapPct"]    = ((df["Open"] - prev_close).abs() / prev_close.replace(0, np.nan))

        df["RSI_Pct"]   = (df["RSI"]
                           .rolling(RSI_PCT_LOOKBACK, min_periods=30)
                           .apply(lambda x: (x[:-1] < x[-1]).sum() / (len(x)-1) * 100
                                  if len(x) > 1 else 50, raw=True))

        df["ADX_Slope"] = df["ADX"].diff(ADX_SLOPE_BARS)

        df["ATR_Pct"]   = (df["ATR"]
                           .rolling(ATR_PCT_LOOKBACK, min_periods=30)
                           .apply(lambda x: (x[:-1] < x[-1]).sum() / (len(x)-1) * 100
                                  if len(x) > 1 else 50, raw=True))

        df["VWAP"]      = _calc_vwap(df)

        return df.dropna(subset=["SMA20","ATR","RSI"])
    except Exception:
        return None

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  V19 BACKTEST — KRİTİK DÜZELTME #1: VERİ SINIRI ÇÖZÜMÜ                    ║
# ║                                                                             ║
# ║  yfinance 15m verisi SADECE SON 60 GÜN için mevcuttur.                     ║
# ║  "1y" + "15m" kombinasyonu boş/hatalı döner — V18'deki backtest sebebi.    ║
# ║                                                                             ║
# ║  V19 Çözümü — İki Mod:                                                     ║
# ║    • MOD 15m : 60d × 15m = ~5760 bar — gün içi hassas analiz               ║
# ║    • MOD 1d  : 2y  × 1d  = ~500  bar  — uzun dönem eğilim analizi          ║
# ║                                                                             ║
# ║  Ek düzeltmeler:                                                            ║
# ║    • Slippage: buy_price += ATR × SLIPPAGE_ATR_FACTOR (Hakem #1)           ║
# ║    • Inner join RS hesabı (lookahead bias yok)                              ║
# ║    • Trailing stop (ATR bazlı)                                              ║
# ║    • Max hold zorla kapat                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@st.cache_data(ttl=1800)
def get_backtest_data(ticker: str, mode: str = "15m"):
    """
    V19: Backtest veri çekimi — yfinance sınırını aşan çift mod.

    mode="15m" → 60d/15m (~5760 bar)  [gerçek yfinance limiti]
    mode="1d"  → 2y/1d  (~500  bar)   [uzun dönem analiz]
    """
    sym      = f"{ticker}.IS"
    period   = BT_PERIOD_15M   if mode == "15m" else BT_PERIOD_1D
    interval = BT_INTERVAL_15M if mode == "15m" else BT_INTERVAL_1D
    min_bars = 100              if mode == "15m" else 60

    try:
        df = _flatten(yf.download(sym, period=period, interval=interval, progress=False))
        if df is None or len(df) < min_bars:
            return None
        c, h, l = df["Close"], df["High"], df["Low"]

        df["SMA20"]   = c.rolling(20).mean()
        df["RSI"]     = _calc_rsi(c)
        df["TR"]      = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
        df["ATR"]     = df["TR"].ewm(alpha=1/ADX_PERIOD, adjust=False).mean()
        df["VolMA20"] = df["Volume"].rolling(20).mean()
        df["High20"]  = h.rolling(BREAKOUT_BARS).max().shift(1)

        adx, pdi, mdi = _calc_adx(df)
        df["ADX"]     = adx
        df["PlusDI"]  = pdi
        df["MinusDI"] = mdi

        direction     = np.sign(c.diff())
        df["OBV"]     = (direction * df["Volume"]).fillna(0).cumsum()
        df["OBV_MA20"]= df["OBV"].rolling(20).mean()

        return df.dropna(subset=["SMA20","ATR","RSI","High20"])
    except Exception:
        return None

@st.cache_data(ttl=1800)
def get_backtest_xu100(mode: str = "15m"):
    """Backtest için XU100 — moda göre."""
    period   = BT_PERIOD_15M   if mode == "15m" else BT_PERIOD_1D
    interval = BT_INTERVAL_15M if mode == "15m" else BT_INTERVAL_1D
    for sym in ("XU100.IS", "^XU100"):
        try:
            df = _flatten(yf.download(sym, period=period, interval=interval, progress=False))
            if df is not None and len(df) > 50:
                return df[["Close"]].copy()
        except Exception:
            continue
    return None

def run_backtest(ticker: str, mode: str = "15m"):
    """
    V19 Backtest.

    Giriş kriterleri (6 core filtre):
      1. Close > SMA20        (trend yönü)
      2. 45 < RSI < 75        (geniş bant)
      3. RS > RS_MA20         (piyasadan güçlü)
      4. ADX > 20             (trend var)
      5. +DI > -DI            (yükseliş yönlü)
      6. Close > High20       (kırılım teyidi)

    V19 YENİLİKLERİ:
      • Slippage: giriş fiyatı = Close × (1 + ATR/Close × SLIPPAGE_ATR_FACTOR)
        → Gerçekçi maliyet modellemesi (Hakem #1 önerisi)
      • İki mod: 15m (kısa vadeli) veya 1d (uzun vadeli)
        → yfinance 60 gün limiti aşılıyor (Kritik hata düzeltmesi)
    """
    max_hold = MAX_HOLD_BARS_15M if mode == "15m" else MAX_HOLD_BARS_1D
    bt_df    = get_backtest_data(ticker, mode)
    xu_df    = get_backtest_xu100(mode)

    if bt_df is None:
        return {
            "err": (
                f"Backtest verisi alınamadı ({ticker}.IS).\n"
                f"Mod: {mode} | Period: {BT_PERIOD_15M if mode=='15m' else BT_PERIOD_1D} | "
                f"Interval: {BT_INTERVAL_15M if mode=='15m' else BT_INTERVAL_1D}\n"
                f"Öneri: '1g (Uzun Dönem)' modunu deneyin."
            )
        }
    if len(bt_df) < (100 if mode == "15m" else 60):
        return {"err": f"Yeterli veri yok ({len(bt_df)} bar). 1g modunu deneyin."}

    try:
        # ── RS hesabı — lookahead bias yok ─────────────────────────────────
        if xu_df is not None:
            aligned   = bt_df[["Close"]].join(xu_df["Close"].rename("XU100"), how="inner")
            rs_raw    = aligned["Close"] / aligned["XU100"]
            rs_ma     = rs_raw.rolling(20).mean()
            rs_series = (rs_raw > rs_ma).reindex(bt_df.index, fill_value=False)
        else:
            rs_series = pd.Series(True, index=bt_df.index)

        # ── Giriş/Çıkış döngüsü ────────────────────────────────────────────
        pos        = False
        buy_cost   = 0.0    # komisyon + slippage dahil giriş maliyeti
        trail_stop = 0.0
        entry_atr  = 0.0
        hold_bars  = 0
        trades     = []
        peak_price = 0.0

        bt = bt_df.copy()
        rs = rs_series.reindex(bt.index, fill_value=False)

        for i, (idx, r) in enumerate(bt.iterrows()):
            if pd.isna(r.Close) or pd.isna(r.SMA20) or pd.isna(r.ATR):
                continue

            if not pos:
                # ── Giriş: 6 core filtre ────────────────────────────────
                rsi_ok   = 45 < r.RSI < 75
                adx_ok   = r.ADX > 20
                di_ok    = r.PlusDI > r.MinusDI
                trend_ok = r.Close > r.SMA20
                brk_ok   = r.Close > r.High20 if not pd.isna(r.High20) else False
                rs_ok    = bool(rs.loc[idx]) if idx in rs.index else False

                if trend_ok and rsi_ok and adx_ok and di_ok and brk_ok and rs_ok:
                    pos = True

                    # ── V19 KRİTİK DÜZELTME #2: SLIPPAGE ────────────────
                    # Gerçek piyasada kapanış fiyatından TAM girilmez.
                    # Slippage eklenerek gerçekçi giriş maliyeti modellenir.
                    # slippage_pct = ATR / Close × SLIPPAGE_ATR_FACTOR
                    slippage_pct = (r.ATR / r.Close) * SLIPPAGE_ATR_FACTOR if r.Close > 0 else 0
                    buy_price    = r.Close * (1 + slippage_pct)   # fiili giriş fiyatı
                    buy_cost     = buy_price * (1 + TRADE_COST)   # + komisyon

                    entry_atr    = r.ATR
                    trail_stop   = buy_price - entry_atr * TRAIL_ATR_MULT
                    peak_price   = buy_price
                    hold_bars    = 0

            else:
                hold_bars += 1

                # Trailing stop güncelle
                if r.Close > peak_price:
                    peak_price = r.Close
                    trail_stop = peak_price - entry_atr * TRAIL_ATR_MULT

                exit_reason = None
                if r.Close < trail_stop:
                    exit_reason = "TrailStop"
                elif r.Close < r.SMA20:
                    exit_reason = "Trend"
                elif hold_bars >= max_hold:
                    exit_reason = "MaxHold"

                if exit_reason:
                    sell_net = r.Close * (1 - TRADE_COST)
                    pnl      = (sell_net - buy_cost) / buy_cost * 100
                    trades.append({"pnl": pnl, "why": exit_reason, "bars": hold_bars})
                    pos = False

        # Açık pozisyonu kapat
        if pos and len(bt) > 0:
            last_close = float(bt["Close"].iloc[-1])
            sell_net   = last_close * (1 - TRADE_COST)
            pnl        = (sell_net - buy_cost) / buy_cost * 100
            trades.append({"pnl": pnl, "why": "EndOfData", "bars": hold_bars})

        if not trades:
            return {
                "err": (
                    f"{len(bt_df)} bar'lık veride hiç sinyal oluşmadı.\n"
                    f"Olası nedenler:\n"
                    f"  • {ticker} için XU100 verisi alınamadı\n"
                    f"  • Hisse tüm dönem boyunca 6 filtreyi karşılamadı\n"
                    f"  • Farklı modu deneyin: {'1g (Uzun Dönem)' if mode=='15m' else '15dk (Kısa Vadeli)'}"
                )
            }

        pnls     = [t["pnl"] for t in trades]
        wins     = [p for p in pnls if p > 0]
        losses   = [p for p in pnls if p < 0]
        pf       = sum(wins) / abs(sum(losses)) if losses else float("inf")
        cum      = pd.Series(pnls).cumsum()
        max_dd   = float((cum - cum.cummax()).min())
        avg_bars = float(np.mean([t["bars"] for t in trades]))

        ec = {"TrailStop":0, "Trend":0, "MaxHold":0, "EndOfData":0}
        for t in trades:
            ec[t["why"]] = ec.get(t["why"], 0) + 1

        bh = (float(bt["Close"].iloc[-1]) / float(bt["Close"].iloc[0]) - 1) * 100

        return {
            "total":    sum(pnls),
            "wr":       len(wins) / len(trades) * 100,
            "pf":       pf,
            "bh":       bh,
            "dd":       max_dd,
            "n":        len(trades),
            "avg_bars": avg_bars,
            "ec":       ec,
            "period":   BT_PERIOD_15M if mode == "15m" else BT_PERIOD_1D,
            "interval": BT_INTERVAL_15M if mode == "15m" else BT_INTERVAL_1D,
            "bars":     len(bt_df),
            "mode":     mode,
            "err":      None,
        }
    except Exception as e:
        return {"err": f"Hesaplama hatası: {str(e)}"}

# ── DİĞER FONKSİYONLAR ───────────────────────────────────────────────────────
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
        return _flatten(yf.download(sektor_sym, period="60d", interval="15m", progress=False))
    except Exception:
        return None

def sektor_rs(stock_close, ticker, xu100_df):
    sektor_sym   = SEKTOR_MAP.get(ticker.upper())
    rs_sektor_ok = None
    if sektor_sym:
        try:
            sek_df = get_sektor_data(sektor_sym)
            if sek_df is not None:
                sc  = stock_close.copy(); sc.name = "stk"
                sek = sek_df["Close"].copy(); sek.name = "sek"
                aln = pd.concat([sc, sek], axis=1).ffill().dropna()
                if len(aln) > 20:
                    rs_s = aln["stk"] / aln["sek"]
                    rs_sektor_ok = bool(rs_s.iloc[-1] > rs_s.rolling(20).mean().iloc[-1])
        except Exception:
            pass
    rs_xu100_ok = None
    if xu100_df is not None:
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
        c, vol = df["Close"], df["Volume"]
        if len(c) < VCP_LOOKBACK: return 0, False, False, False
        std_r = c.iloc[-20:].std(); std_l = c.iloc[-VCP_LOOKBACK:].std()
        vol_r = vol.iloc[-20:].mean(); vol_l = vol.iloc[-VCP_LOOKBACK:].mean()
        pc = std_r < std_l * 0.85 if std_l > 0 else False
        vc = vol_r < vol_l * 0.75  if vol_l  > 0 else False
        rs = float(c.iloc[-1]) > float(c.iloc[-20])
        return int(pc)+int(vc)+int(rs), pc, vc, rs
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
    try: return float(df["Close"].iloc[-1]) > float(df["High20"].iloc[-1])
    except Exception: return False

def event_risk(ticker):
    try:
        ed = yf.Ticker(f"{ticker}.IS").info.get("earningsDate")
        if ed is None: return "📡"
        if isinstance(ed, list): ed = ed[0]
        if isinstance(ed, int):  ed = datetime.datetime.fromtimestamp(ed)
        return "⚠" if 0 <= (ed.replace(tzinfo=None) - datetime.datetime.now()).days <= 5 else "✅"
    except Exception:
        return "📡"

def market_health_score(xu100_df, breadth_pct=None):
    score, detail = 0, {}
    k1 = False
    if xu100_df is not None and "SMA50" in xu100_df.columns:
        try: k1 = float(xu100_df["Close"].iloc[-1]) > float(xu100_df["SMA50"].iloc[-1])
        except: pass
    score += int(k1); detail["XU100 > SMA50"] = k1
    k2 = breadth_pct is not None and breadth_pct > BREADTH_NEUTRAL
    score += int(k2); detail[f"Breadth > {BREADTH_NEUTRAL}%"] = k2
    k3 = breadth_pct is not None and breadth_pct > 70
    score += int(k3); detail["Breadth > 70%"] = k3
    k4 = False
    if xu100_df is not None and "RSI" in xu100_df.columns:
        try:
            rv = float(xu100_df["RSI"].iloc[-1])
            k4 = not pd.isna(rv) and rv > 50
        except: pass
    score += int(k4); detail["XU100 RSI > 50"] = k4
    k5 = False
    if xu100_df is not None and "ADX" in xu100_df.columns:
        try:
            av = xu100_df["ADX"]
            if isinstance(av, pd.DataFrame): av = av.iloc[:,0]
            v  = float(av.iloc[-1])
            k5 = not pd.isna(v) and v > 20
        except: pass
    score += int(k5); detail["XU100 ADX > 20"] = k5
    return score, detail

def mhs_risk(score):
    if score >= 3: return RISK_FULL
    if score == 2: return RISK_HALF
    return RISK_OFF

def market_regime(xu100_df, breadth_pct=None):
    na = {"lbl":"Belirsiz","css":"rb-none","risk":RISK_FULL,"icon":"⚠️","mhs":0}
    if xu100_df is None or "SMA50" not in xu100_df.columns: return na
    try:
        c = float(xu100_df["Close"].iloc[-1])
        s = float(xu100_df["SMA50"].iloc[-1])
        if pd.isna(s): return na
        mhs, _ = market_health_score(xu100_df, breadth_pct)
        risk   = mhs_risk(mhs)
        above  = c > s
        b_ok   = breadth_pct is None or breadth_pct > BREADTH_NEUTRAL
        if above and b_ok:
            return {"lbl":f"BULL — XU100 {c:.0f} > SMA50 {s:.0f}  |  MHS {mhs}/5",
                    "css":"rb-bull","risk":risk,"icon":"🟢","mhs":mhs}
        elif above:
            return {"lbl":f"ZAYIF BULL — Breadth %{breadth_pct:.0f}  |  MHS {mhs}/5",
                    "css":"rb-none","risk":risk,"icon":"🟡","mhs":mhs}
        return     {"lbl":f"BEAR — XU100 {c:.0f} < SMA50 {s:.0f}  |  MHS {mhs}/5",
                    "css":"rb-bear","risk":risk,"icon":"🔴","mhs":mhs}
    except Exception:
        return na

def data_freshness(df):
    try:
        age = (datetime.datetime.now() - df.index[-1]).total_seconds() / 60
        if age > 900:  return {"age":age,"css":"fb-yellow","icon":"⏸️","label":"Piyasa Kapalı","is_closed":True}
        elif age <= FRESHNESS_WARN: return {"age":age,"css":"fb-green", "icon":"🟢","label":f"Güncel — {age:.0f}dk","is_closed":False}
        elif age <= FRESHNESS_RED:  return {"age":age,"css":"fb-yellow","icon":"🟡","label":f"Gecikiyor — {age:.0f}dk","is_closed":False}
        else:                       return {"age":age,"css":"fb-red",   "icon":"🔴","label":f"BAYAT — {age:.0f}dk","is_closed":False}
    except Exception:
        return {"age":0,"css":"fb-yellow","icon":"⚠️","label":"Zaman bilinmiyor","is_closed":False}

def support_resistance_v2(df, lookback=SR_LOOKBACK):
    try:
        hi, lo = df["High"].iloc[-lookback:].values, df["Low"].iloc[-lookback:].values
        vol    = df["Volume"].iloc[-lookback:].values
        price  = float(df["Close"].iloc[-1])
        TOL    = 0.005
        ph, pl = [], []
        for i in range(2, len(hi)-2):
            if hi[i] > hi[i-1] and hi[i] > hi[i-2] and hi[i] > hi[i+1] and hi[i] > hi[i+2]:
                ph.append((hi[i], vol[i]))
            if lo[i] < lo[i-1] and lo[i] < lo[i-2] and lo[i] < lo[i+1] and lo[i] < lo[i+2]:
                pl.append((lo[i], vol[i]))
        def touches(level, bars):
            return sum(1 for v,_ in bars if abs(v-level)/level <= TOL)
        return ([(p, touches(p,pl)) for p,_ in sorted([(p,v) for p,v in pl if p<price],reverse=True)[:3]],
                [(p, touches(p,ph)) for p,_ in sorted([(p,v) for p,v in ph if p>price])[:3]])
    except Exception:
        return [], []

# ── HTML YARDIMCILARI ─────────────────────────────────────────────────────────
def scanner_html(rows):
    hdr = ("<colgroup>"
           "<col style='width:26%'><col style='width:18%'>"
           "<col style='width:7%'><col style='width:7%'><col style='width:7%'>"
           "<col style='width:7%'><col style='width:7%'><col style='width:9%'>"
           "<col style='width:12%'>"
           "</colgroup>"
           "<thead><tr>"
           "<th style='text-align:left;padding-left:5px'>Hisse</th>"
           "<th>Fiyat</th><th>T</th><th>4H</th><th>ADX</th>"
           "<th>SQZ</th><th>RS</th><th>OBV</th><th>EVT</th>"
           "</tr></thead>")
    body = "<tbody>"
    for r in rows:
        tc = "#22c55e" if r["T"] == "↑" else "#ef4444"
        body += (f"<tr><td class='tkr'>{r['H']}</td><td>{r['F']}</td>"
                 f"<td style='color:{tc}'>{r['T']}</td>"
                 f"<td>{r['HTF']}</td><td>{r['ADX']}</td>"
                 f"<td>{r['SQZ']}</td><td>{r['RS']}</td>"
                 f"<td>{r['OBV']}</td><td>{r['EVT']}</td></tr>")
    return f"<div class='scanner-wrapper'><table class='scanner-table'>{hdr}{body}</tbody></table></div>"

def breadth_html(above, total):
    if total == 0: return ""
    pct = int(above / total * 100)
    css = "#22c55e" if pct >= 70 else ("#f59e0b" if pct >= BREADTH_NEUTRAL else "#ef4444")
    lbl = (f"GÜÇLÜ ({above}/{total})" if pct >= 70
           else f"NÖTR ({above}/{total})" if pct >= BREADTH_NEUTRAL
           else f"ZAYIF ({above}/{total})")
    return (f"<div class='breadth-wrap'>"
            f"<div class='bw-lbl'>Piyasa Genişliği — SMA20 Üstü</div>"
            f"<div class='bar-outer'><div style='width:{pct}%;height:100%;background:{css};border-radius:4px'></div></div>"
            f"<div class='bw-nums'><span style='color:{css};font-weight:700'>{lbl}</span>"
            f"<span style='color:#6b7594'>%{pct}</span></div></div>")

def regime_html(reg, extra=""):
    return f"<div class='regime-banner {reg['css']}' style='{extra}'>{reg['icon']} {reg['lbl']}</div>"

def freshness_html(fr, extra=""):
    return f"<div class='freshness-banner {fr['css']}' style='{extra}'>{fr['icon']} {fr['label']}</div>"

def htf_html(val, ticker):
    if val is None: return f"<div class='htf-banner htf-none'>⚠️ 4H veri yok — {ticker}</div>"
    return (f"<div class='htf-banner htf-bull'>🟢 4H BULL — SMA50 > SMA200</div>" if val
            else f"<div class='htf-banner htf-bear'>🔴 4H BEAR — SMA50 < SMA200</div>")

def mhs_html(score, detail):
    css_map = {5:"mhs-5",4:"mhs-4",3:"mhs-3",2:"mhs-2",1:"mhs-1",0:"mhs-0"}
    lbl_map = {5:"RİSK ON — Tam Pozisyon",4:"RİSK ON — Tam Pozisyon",
               3:"NÖTR — Normal Pozisyon",2:"TEMKİNLİ — Yarı Pozisyon",
               1:"RİSK OFF — Küçük Pozisyon",0:"RİSK OFF — Bekleme"}
    icon_map= {5:"💚",4:"🟢",3:"🟡",2:"🟠",1:"🔴",0:"⛔"}
    css  = css_map.get(score, "mhs-0")
    risk = mhs_risk(score)
    rows = "".join(
        f"<div class='mhs-row'><span class='mhs-item'>{k}</span>"
        f"<span class='mhs-check' style='color:{'#4ade80' if v else '#ef4444'}'>{'✅' if v else '❌'}</span></div>"
        for k, v in detail.items()
    )
    return (f"<div class='mhs-wrap'><div class='mhs-lbl'>Market Health Score — {score}/5</div>"
            f"<div class='health-banner {css}' style='margin-bottom:6px'>"
            f"{icon_map[score]} {lbl_map[score]}  ·  Risk: %{risk*100:.1f}</div>{rows}</div>")

def sig_row_html(label, state, t_txt, f_txt, none_txt="📡 Veri Yok"):
    if state is None:
        return (f"<div class='sr unk'><span class='sl'>{label}</span>"
                f"<span class='sv wn'>{none_txt}</span></div>")
    return (f"<div class='sr {'ok' if state else 'nok'}'>"
            f"<span class='sl'>{label}</span>"
            f"<span class='sv {'up' if state else 'dn'}'>{t_txt if state else f_txt}</span></div>")

def karar_html(skor, n):
    if   skor >= 18: css, lbl, ikon = "kc-al",  "GÜÇLÜ AL",    "💚"
    elif skor >= 15: css, lbl, ikon = "kc-pos",  "OLUMLU",      "🟢"
    elif skor >= 10: css, lbl, ikon = "kc-notr", "NÖTR / İZLE", "🟡"
    else:            css, lbl, ikon = "kc-sat",  "BEKLE / SAT", "🔴"
    return (f"<div class='karar-card {css}'>"
            f"<div class='karar-lbl'>Kompozit Karar — {skor}/{n} sinyal aktif</div>"
            f"<div class='karar-val'>{ikon} {lbl}</div></div>")

def metric_grid(*cards):
    items = "".join(
        f"<div class='mc'><div class='lb'>{l}</div><div class='vl {c}'>{v}</div></div>"
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
             f"<span class='lv-val'>{price:.2f} TL</span>"
             f"<span class='lv-dist'>—</span></div>")
    if vwap_val is not None and not pd.isna(vwap_val):
        vd   = (price / vwap_val - 1) * 100
        side = "üstü ✅" if price >= vwap_val else "altı ⚠️"
        html += (f"<div class='level-row vwap'>"
                 f"<span class='lv-lbl'>VWAP ({side})</span>"
                 f"<span class='lv-val'>{vwap_val:.2f} TL</span>"
                 f"<span class='lv-dist'>{vd:+.2f}%</span></div>")
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
            f"<div class='rr-nums'><span class='rr-r'>Risk: {risk_tl:.2f} TL</span>"
            f"<span class='vl {r_cls}' style='font-size:11px;font-weight:700'>1:{ratio:.2f}</span>"
            f"<span class='rr-rw'>Ödül: {reward_tl:.2f} TL</span></div></div>")

def vol_bar_html(vol_now, vol_ma, vol_ratio, vol_confirmed, vol_pct):
    fill  = min(int(vol_ratio * 50), 100)
    bar_c = "#22c55e" if vol_confirmed else ("#f59e0b" if vol_ratio >= RVOL_THRESHOLD else "#94a3b8")
    lbl   = (f"✅ DOĞRULANDI (x{vol_ratio:.2f}, P{vol_pct:.0f})" if vol_confirmed
             else f"⚠️ Yüksek — Negatif Kapanış (Dağıtım?)" if vol_ratio >= RVOL_THRESHOLD
             else f"Normal/Düşük (x{vol_ratio:.2f}, P{vol_pct:.0f})")
    return (f"<div class='vol-bar-wrap'><div class='vb-lbl'>Hacim — {lbl}</div>"
            f"<div class='bar-outer'><div style='width:{fill}%;height:100%;background:{bar_c};border-radius:4px'></div></div>"
            f"<div class='vb-nums'><span>Anlık: {vol_now:,.0f}</span>"
            f"<span>RVOL: x{vol_ratio:.2f}</span>"
            f"<span>P{vol_pct:.0f}</span></div></div>")

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
xu100  = get_xu100()

_breadth_pct = None
if st.session_state.breadth:
    b = st.session_state.breadth
    if b["total"] > 0: _breadth_pct = b["above"] / b["total"] * 100

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
        if st.button("➕ Ekle") and yeni and yeni not in st.session_state.watchlist:
            st.session_state.watchlist.append(yeni)
            save_watchlist(st.session_state.watchlist); st.rerun()
    with b2:
        if st.button("🗑️ Çıkar") and len(st.session_state.watchlist) > 1:
            st.session_state.watchlist.remove(secilen)
            save_watchlist(st.session_state.watchlist); st.rerun()
    if st.button("↺ Listeyi Sıfırla"):
        st.session_state.watchlist = BIST_30.copy()
        save_watchlist(st.session_state.watchlist); st.rerun()
    st.caption(f"📋 {len(st.session_state.watchlist)} hisse  ·  V19: Slippage + Likidite Tavanı + Batch Tarama")

# ── ANA EKRAN ─────────────────────────────────────────────────────────────────
col_l, col_c, col_r = st.columns([2.5, 5, 2.5])
df = get_data(secilen)

# ══ SOL: SCANNER (V19: BATCH ÇEKİM) ══════════════════════════════════════════
with col_l:
    st.markdown("### 🚀 Tarayıcı")
    st.caption("⏱️ 15dk gecikmeli  ·  V19: Batch tarama — tüm liste tek istekte")

    if st.button("Tüm Listeyi Tara"):
        st.session_state.scan_rows = []
        st.session_state.breadth   = None
        rows, above_count = [], 0

        wl        = sorted(st.session_state.watchlist)
        tickers_s = [f"{t}.IS" for t in wl]

        # ── V19 KRİTİK DÜZELTME #5: BATCH İNDİRME ─────────────────────────
        # V18: her hisse için sırayla yf.download() → bloke edici, yavaş
        # V19: yf.download(tickers_list) → tek HTTP isteğiyle 30 hisse
        # Tarama süresi ~30 saniyeden ~2-4 saniyeye düşer.
        with st.spinner(f"⚡ {len(wl)} hisse batch indiriliyor..."):
            try:
                raw_batch = yf.download(
                    tickers_s,
                    period="60d",
                    interval="15m",
                    progress=False,
                    group_by="ticker",
                    threads=True
                )
            except Exception:
                raw_batch = None

        if raw_batch is not None and not raw_batch.empty:
            prog = st.progress(0, text="Analiz ediliyor...")
            for i, (t, sym) in enumerate(zip(wl, tickers_s)):
                try:
                    # Batch sonucundan tek hisseyi çıkar
                    if len(tickers_s) == 1:
                        d_raw = raw_batch
                    else:
                        try:
                            d_raw = raw_batch[sym] if sym in raw_batch.columns.get_level_values(0) else None
                        except Exception:
                            d_raw = None

                    if d_raw is None or (hasattr(d_raw, 'empty') and d_raw.empty):
                        prog.progress((i+1)/len(wl), text=f"Atlıyor: {t}")
                        continue

                    # _flatten uygula
                    if isinstance(d_raw, pd.DataFrame):
                        d_raw = d_raw.loc[:, ~d_raw.columns.duplicated()]
                        if hasattr(d_raw.index, "tz") and d_raw.index.tz is not None:
                            d_raw.index = d_raw.index.tz_convert(None)

                    if d_raw is None or d_raw.empty or "Close" not in d_raw.columns:
                        prog.progress((i+1)/len(wl), text=f"Atlıyor: {t}")
                        continue

                    # Hızlı indikatör hesabı (sadece tarama için)
                    c_s  = d_raw["Close"].squeeze()
                    sma  = c_s.rolling(20).mean()
                    adx_v, pdi_v, mdi_v = _calc_adx(d_raw)
                    obv_v  = (np.sign(c_s.diff()) * d_raw["Volume"]).fillna(0).cumsum()
                    obv_ma = obv_v.rolling(20).mean()
                    obv_h  = obv_v.rolling(OBV_BRK_LOOKBACK).max().shift(1)
                    sqz_v  = bollinger_squeeze(c_s)

                    rs_ab, rs_sl, _ = relative_strength_full(c_s, xu100)
                    if rs_ab is None:                                    rs_icon = "📡"
                    elif bool(rs_ab.iloc[-1]) and bool(rs_sl.iloc[-1]): rs_icon = "💚"
                    elif bool(rs_ab.iloc[-1]):                           rs_icon = "🟡"
                    else:                                                rs_icon = "🔴"

                    htf_val  = htf_trend(t)
                    htf_icon = "🟢" if htf_val is True else ("🔴" if htf_val is False else "⚪")

                    adx_val_s = float(adx_v.iloc[-1]) if len(adx_v) > 0 else 0
                    pdi_s     = float(pdi_v.iloc[-1]) if len(pdi_v) > 0 else 0
                    mdi_s     = float(mdi_v.iloc[-1]) if len(mdi_v) > 0 else 0
                    di_sp_s   = pdi_s - mdi_s
                    adx_ok_s  = adx_val_s > ADX_THRESHOLD and pdi_s > mdi_s and di_sp_s > DI_SPREAD_MIN
                    adx_icon  = "💪" if adx_ok_s else ("⚠️" if adx_val_s > ADX_THRESHOLD else "·")

                    obv_ok_s  = float(obv_v.iloc[-1]) > float(obv_ma.iloc[-1])
                    obv_brk_s = float(obv_v.iloc[-1]) > float(obv_h.iloc[-1]) if not pd.isna(obv_h.iloc[-1]) else False
                    obv_icon  = "🚀" if (obv_ok_s and obv_brk_s) else ("📈" if obv_ok_s else "📉")

                    trend_up  = float(c_s.iloc[-1]) > float(sma.iloc[-1])
                    if trend_up: above_count += 1

                    rows.append({
                        "H":   t,
                        "F":   f"{float(c_s.iloc[-1]):.2f}",
                        "T":   "↑" if trend_up else "↓",
                        "HTF": htf_icon,
                        "ADX": adx_icon,
                        "SQZ": "🟡" if bool(sqz_v.iloc[-1]) else "·",
                        "RS":  rs_icon,
                        "OBV": obv_icon,
                        "EVT": st.session_state.event_risks.get(t, "📡"),
                    })
                except Exception:
                    pass
                prog.progress((i+1)/len(wl), text=f"Analiz: {t}")
            prog.empty()
        else:
            st.warning("Batch veri indirilemedi, tekrar deneyin.")

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
                pr.progress((i+1)/len(st.session_state.watchlist))
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
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA20"], mode="lines",
            name="SMA20", line=dict(color="#38bdf8", width=1.5)))
        if "VWAP" in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df["VWAP"], mode="lines",
                name="VWAP", line=dict(color="#a78bfa", width=1.2, dash="dot"), opacity=0.85))
        if "OBV" in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df["OBV"], mode="lines",
                name="OBV", line=dict(color="#a78bfa", width=1), yaxis="y2", opacity=0.7))
            fig.add_trace(go.Scatter(x=df.index, y=df["OBV_MA20"], mode="lines",
                name="OBV MA20", line=dict(color="#f59e0b", width=1, dash="dot"), yaxis="y2", opacity=0.7))
        fig.update_xaxes(rangebreaks=[dict(bounds=["18:00","09:55"]), dict(bounds=["sat","mon"])])
        fig.update_layout(
            template="plotly_dark", height=530,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.02, x=0, font=dict(size=10)),
            yaxis=dict(domain=[0.28,1.0]),
            yaxis2=dict(domain=[0.0,0.25],
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
        obv_h20  = float(df["OBV_High20"].iloc[-1]) if "OBV_High20"in df.columns else obv_now
        gap_pct  = float(df["GapPct"].iloc[-1])     if "GapPct"    in df.columns else 0.0
        di_sp    = float(df["DI_Spread"].iloc[-1])  if "DI_Spread" in df.columns else (plus_di - minus_di)
        vwap_val = float(df["VWAP"].iloc[-1])       if "VWAP"      in df.columns else None
        rsi_pct  = float(df["RSI_Pct"].iloc[-1])    if "RSI_Pct"   in df.columns else 50.0
        adx_slp  = float(df["ADX_Slope"].iloc[-1])  if "ADX_Slope" in df.columns else 0.0
        atr_pct2 = float(df["ATR_Pct"].iloc[-1])    if "ATR_Pct"   in df.columns else 50.0

        sqz_now               = bool(bollinger_squeeze(df["Close"]).iloc[-1])
        rs_above, rs_sl_s, _  = relative_strength_full(df["Close"], xu100)
        rs_now                = bool(rs_above.iloc[-1]) if rs_above is not None else None
        rs_slope_now          = bool(rs_sl_s.iloc[-1])  if rs_sl_s  is not None else None
        htf_now               = htf_trend(secilen)
        atr_ok, atr_pct       = atr_regime(atr, fiyat)
        brk_now               = breakout_check(df)
        supports, resistances = support_resistance_v2(df)
        fr                    = data_freshness(df)

        lb            = min(26, len(df)-1)
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
        obv_brk_ok    = obv_now > obv_h20
        gap_ok        = gap_pct < GAP_MAX_PCT
        rsi_pct_ok    = rsi_pct > 60
        adx_slope_ok  = adx_slp > 0
        atr_pct_ok    = 10 < atr_pct2 < 75
        di_sp_ok      = di_sp > DI_SPREAD_MIN
        vwap_ok       = (fiyat > vwap_val) if (vwap_val and not pd.isna(vwap_val)) else None

        rs_xu100_ok, rs_sektor_ok, sektor_sym = sektor_rs(df["Close"], secilen, xu100)
        sektor_rs_ok = (rs_sektor_ok is True) if rs_sektor_ok is not None else True

        vcp_s, vcp_pc, vcp_vc, vcp_rs_flag = vcp_score(df)
        vcp_ok = vcp_s >= 2

        if   rsi >= 70: rz_lbl, rz_cls = "AŞIRI ALIM",  "dn"
        elif rsi >= 55: rz_lbl, rz_cls = "GÜÇLÜ BÖLGE", "up"
        elif rsi >= 50: rz_lbl, rz_cls = "NÖTR ÜST",    "wn"
        elif rsi >= 45: rz_lbl, rz_cls = "NÖTR ALT",    "wn"
        elif rsi >= 30: rz_lbl, rz_cls = "ZAYIF BÖLGE", "dn"
        else:           rz_lbl, rz_cls = "AŞIRI SATIM", "wn"

        sinyaller = [
            fiyat > sma, rsi_ok, rs_now is True, rs_slope_now is True,
            sqz_now, vol_confirmed, htf_now is True, brk_now, atr_ok,
            adx_ok, adx_dir_ok, vol_pct_ok, atr_exp_ok, obv_ok,
            rsi_pct_ok, adx_slope_ok, sektor_rs_ok, atr_pct_ok, vcp_ok,
            di_sp_ok, obv_brk_ok, vwap_ok is True,
        ]
        skor = sum(sinyaller)

        stop      = fiyat - atr * ATR_MULT
        risk_tl   = max(fiyat - stop, 0.01)
        hedef     = fiyat + risk_tl * 2
        reward_tl = hedef - fiyat
        rr_ratio  = reward_tl / risk_tl

        aktif_risk = regime["risk"]

        tab1, tab2, tab3 = st.tabs(["📐 Planner", "🤖 Broker", "📊 Backtest"])

        with tab1:
            # ── V19 KRİTİK DÜZELTME #3: LİKİDİTE TAVANI ─────────────────────
            # Önerilen lot, günlük ortalama hacmin %1'ini aşamaz.
            # Büyük portföylerde sığ hisselerde piyasayı hareket ettirmez.
            raw_lot   = int((portfoy * aktif_risk) / risk_tl)
            max_lot   = int(vol_ma * LOT_LIQ_CAP_PCT) if vol_ma > 0 else raw_lot
            lot       = min(raw_lot, max_lot)
            liq_capped = (raw_lot > max_lot)

            st.markdown(regime_html(regime, "font-size:10px;padding:4px 8px"), unsafe_allow_html=True)
            st.markdown(htf_html(htf_now, secilen), unsafe_allow_html=True)
            if not gap_ok:
                st.warning(f"⚠️ GAP %{gap_pct*100:.2f} — Pozisyon küçültün veya bekleyin.")
            if liq_capped:
                st.markdown(
                    f"<div class='liq-warn'>⚠️ Likidite Tavanı: {raw_lot} lot önerildi, "
                    f"günlük hacim ({vol_ma:,.0f}) sınırı {lot} lot'a indirdi.</div>",
                    unsafe_allow_html=True
                )
            st.markdown(metric_grid(
                ("Giriş Fiyatı",  f"{fiyat:.2f} TL",       ""),
                ("Stop Loss",     f"{stop:.2f} TL",         "dn"),
                ("Hedef Fiyat",   f"{hedef:.2f} TL",        "up"),
                ("Önerilen Lot",  f"{lot} adet",            "up" if fiyat > sma else "wn"),
                ("Maliyet",       f"{lot*fiyat:,.0f} TL",   ""),
                ("Risk / İşlem",  f"%{aktif_risk*100:.1f}", "wn"),
            ), unsafe_allow_html=True)
            if liq_capped:
                st.markdown(metric_grid(
                    ("Ham Lot (Risk)",  f"{raw_lot} adet",  "dn"),
                    ("Maks Lot (Liq.)",f"{max_lot} adet",  "wn"),
                ), unsafe_allow_html=True)
            st.markdown(rr_bar_html(risk_tl, reward_tl, rr_ratio), unsafe_allow_html=True)
            st.markdown(mhs_html(mhs_score, mhs_detail), unsafe_allow_html=True)
            st.caption("⏱️ 15dk gecikmeli veri — giriş öncesi teyit alın.")

        with tab2:
            if fr["css"] in ("fb-yellow","fb-red") and not fr["is_closed"]:
                st.markdown(freshness_html(fr,"font-size:10px;padding:3px 8px"), unsafe_allow_html=True)
            if not gap_ok:
                st.markdown(
                    f"<div class='sr nok' style='margin-bottom:6px'>"
                    f"<span class='sl'>⛔ GAP BLOCKER</span>"
                    f"<span class='sv dn'>Gap %{gap_pct*100:.2f} — Sinyal geçersiz</span></div>",
                    unsafe_allow_html=True)
            st.markdown(karar_html(skor, len(sinyaller)), unsafe_allow_html=True)
            st.markdown(htf_html(htf_now, secilen), unsafe_allow_html=True)
            st.markdown(sec_div("Fiyat & Momentum"), unsafe_allow_html=True)
            st.markdown(metric_grid(
                ("Değişim (~6.5s)", f"{'+'if deg_pct>=0 else ''}{deg_pct:.2f}%",
                 "up" if deg_pct>=0 else "dn"),
                ("SMA20 Uzaklığı",  f"{'+'if sma_pct>=0 else ''}{sma_pct:.2f}%",
                 "up" if sma_pct>=0 else "dn"),
                ("RSI (14)",        f"{rsi:.1f}",             rz_cls),
                ("RSI Percentile",  f"P{rsi_pct:.0f}",       "up" if rsi_pct_ok else "wn"),
                ("ADX (14)",        f"{adx_val:.1f}",        "up" if adx_ok else "wn"),
                ("DI Spread",       f"{di_sp:+.1f}",         "up" if di_sp_ok else "dn"),
                ("VWAP",            f"{vwap_val:.2f}" if (vwap_val and not pd.isna(vwap_val)) else "—",
                 "up" if (vwap_ok is True) else ("dn" if vwap_ok is False else "")),
                ("VCP Skoru",       f"{vcp_s}/3",            "up" if vcp_ok else ("wn" if vcp_s==1 else "dn")),
            ), unsafe_allow_html=True)
            st.markdown(sec_div("Hacim"), unsafe_allow_html=True)
            st.markdown(vol_bar_html(vol_now, vol_ma, vol_ratio, vol_confirmed, vol_pct), unsafe_allow_html=True)
            st.markdown(sec_div("Destek & Direnç"), unsafe_allow_html=True)
            if supports or resistances:
                st.markdown(level_rows_html(fiyat, supports, resistances, vwap_val), unsafe_allow_html=True)
            else:
                st.caption("Pivot bulunamadı.")
            st.markdown(sec_div("Risk / Ödül"), unsafe_allow_html=True)
            st.markdown(rr_bar_html(risk_tl, reward_tl, rr_ratio), unsafe_allow_html=True)
            st.markdown(sec_div(f"22 Filtre Özeti ({skor}/22)"), unsafe_allow_html=True)
            rs_ab_h = (f"<div class='sr unk'><span class='sl'>RS vs XU100</span>"
                       f"<span class='sv wn'>📡 Veri Yok</span></div>" if rs_now is None else
                       sig_row_html("RS vs XU100", rs_now, "💚 XU100'den Güçlü","🔴 XU100'den Zayıf"))
            rs_sl_h = (f"<div class='sr unk'><span class='sl'>RS Slope</span>"
                       f"<span class='sv wn'>📡 Veri Yok</span></div>" if rs_slope_now is None else
                       sig_row_html("RS Slope", rs_slope_now, "📈 Hızlanıyor","📉 Yavaşlıyor"))
            st.markdown(
                sig_row_html("Trend (SMA20)",    fiyat>sma, "✅ Pozitif","❌ Negatif") +
                sig_row_html("RSI Bandı",         rsi_ok, f"✅ {rsi:.1f} (50-70)",f"⚠️ {rsi:.1f}") +
                rs_ab_h + rs_sl_h +
                sig_row_html("Bollinger SQZ",     sqz_now, "🟡 Sıkışma","⚪ Normal") +
                sig_row_html("Hacim",             vol_confirmed, f"✅ x{vol_ratio:.1f}",f"❌ x{vol_ratio:.1f}") +
                sig_row_html("4H HTF",            htf_now, "🟢 Bull","🔴 Bear", none_txt="⚠️ Veri Yok") +
                sig_row_html("Breakout",          brk_now, "🚀 Kırıldı","⏳ Bekleniyor") +
                sig_row_html("ATR% Bölgesi",      atr_ok, f"✅ %{atr_pct*100:.2f}",f"⚠️ %{atr_pct*100:.2f}") +
                sig_row_html("ADX Güç",           adx_ok, f"💪 {adx_val:.1f}",f"⚠️ {adx_val:.1f}") +
                sig_row_html("ADX Yön (+DI/-DI)", adx_dir_ok, f"⬆️ {plus_di:.1f}/{minus_di:.1f}",f"⬇️ {plus_di:.1f}/{minus_di:.1f}") +
                sig_row_html("Vol Percentile",    vol_pct_ok, f"✅ P{vol_pct:.0f}",f"⚠️ P{vol_pct:.0f}") +
                sig_row_html("ATR Expansion",     atr_exp_ok, "📈 Açılıyor","📉 Daralıyor") +
                sig_row_html("OBV Akış",          obv_ok, "📈 Kurumsal Alım","📉 Dağıtım") +
                sig_row_html("RSI Percentile",    rsi_pct_ok, f"✅ P{rsi_pct:.0f}",f"📊 P{rsi_pct:.0f}") +
                sig_row_html("ADX Slope",         adx_slope_ok, f"📈 +{adx_slp:.2f}",f"📉 {adx_slp:.2f}") +
                sig_row_html("Sektör RS",         sektor_rs_ok if rs_sektor_ok is not None else None,
                             f"💚 Sektör Lideri",f"🔴 Sektör Geride", none_txt="ℹ️ Sektör Yok") +
                sig_row_html("ATR Percentile",    atr_pct_ok, f"✅ P{atr_pct2:.0f}",f"⚠️ P{atr_pct2:.0f}") +
                sig_row_html("VCP",               vcp_ok, f"💎 {vcp_s}/3",f"⏳ {vcp_s}/3") +
                sig_row_html("DI Spread",         di_sp_ok, f"💪 {di_sp:.1f}",f"⚠️ {di_sp:.1f}") +
                sig_row_html("OBV Breakout",      obv_brk_ok, "🚀 OBV Zirve","⏳ Zirve Yok") +
                sig_row_html("VWAP",              vwap_ok, "✅ Üstünde","❌ Altında", none_txt="📡 Yok"),
                unsafe_allow_html=True
            )
            st.caption("⏱️ 15dk gecikmeli veri.")

        # ╔══════════════════════════════════════════════════════════════════╗
        # ║  TAB 3 — BACKTEST V19                                           ║
        # ║  Kritik düzeltme: yfinance 15m/1y limiti → çift mod sistemi    ║
        # ╚══════════════════════════════════════════════════════════════════╝
        with tab3:
            # ── Mod seçimi ─────────────────────────────────────────────────
            st.markdown(
                "<div class='slip-info'>"
                "ℹ️ <b>V19 Düzeltmesi:</b> yfinance 15m veri limiti max 60 gündür. "
                "Daha uzun test için <b>1g (Uzun Dönem)</b> modunu seçin."
                "</div>",
                unsafe_allow_html=True
            )
            bt_mode = st.radio(
                "Backtest Modu",
                options=["15dk (60 Gün, ~5760 Bar)", "1g (2 Yıl, ~500 Bar)"],
                horizontal=True,
                key="bt_mode_radio"
            )
            mode_key = "15m" if bt_mode.startswith("15") else "1d"
            max_hold = MAX_HOLD_BARS_15M if mode_key == "15m" else MAX_HOLD_BARS_1D
            period_lbl = f"{BT_PERIOD_15M}/{BT_INTERVAL_15M}" if mode_key == "15m" else f"{BT_PERIOD_1D}/{BT_INTERVAL_1D}"
            bar_est    = "~5.760 bar" if mode_key == "15m" else "~500 bar"

            st.markdown(
                f"<div class='bt-info-box'>"
                f"<div class='bt-title'>V19 Backtest Mimarisi</div>"
                f"<div class='bt-row'><span class='bt-lbl'>Veri</span>"
                f"<span class='bt-val'>{period_lbl} ({bar_est})</span></div>"
                f"<div class='bt-row'><span class='bt-lbl'>Giriş</span>"
                f"<span class='bt-val'>{BT_CORE_FILTERS} core filtre + Slippage</span></div>"
                f"<div class='bt-row'><span class='bt-lbl'>Stop</span>"
                f"<span class='bt-val'>ATR × {TRAIL_ATR_MULT} Trailing</span></div>"
                f"<div class='bt-row'><span class='bt-lbl'>Max Süre</span>"
                f"<span class='bt-val'>{max_hold} bar</span></div>"
                f"<div class='bt-row'><span class='bt-lbl'>Maliyet</span>"
                f"<span class='bt-val'>%{TRADE_COST*100:.2f} komisyon + Slippage (ATR×{SLIPPAGE_ATR_FACTOR})</span></div>"
                f"</div>",
                unsafe_allow_html=True
            )

            if st.button("▶ Backtest Çalıştır", key="bt_run"):
                spinner_txt = ("1 yıllık günlük veri yükleniyor..." if mode_key == "1d"
                               else "60 günlük 15dk veri yükleniyor...")
                with st.spinner(spinner_txt):
                    res = run_backtest(secilen, mode_key)
                st.session_state["bt_result"] = res
                st.session_state["bt_ticker"] = secilen
                st.session_state["bt_mode"]   = mode_key

            # Sonuç gösterimi
            res       = st.session_state.get("bt_result")
            bt_ticker = st.session_state.get("bt_ticker", "")
            bt_mode_s = st.session_state.get("bt_mode", "?")

            if res is None:
                st.info("▶ Modu seçin ve butona basarak backtest başlatın.")
            elif res.get("err"):
                st.warning(f"ℹ️ {res['err']}")
            else:
                if bt_ticker != secilen:
                    st.warning(f"⚠️ Gösterilen sonuç {bt_ticker} için. {secilen} için tekrar çalıştırın.")

                ret_cls = "up" if res["total"] >= 0 else "dn"
                pf_str  = f"{res['pf']:.2f}" if res["pf"] != float("inf") else "∞"

                st.markdown(metric_grid(
                    ("Robot Getiri (net)", f"%{res['total']:.2f}", ret_cls),
                    ("Al-Bekle",           f"%{res['bh']:.2f}",   "up" if res["bh"]>=0 else "dn"),
                    ("Win Rate",           f"%{res['wr']:.1f}",   "up" if res["wr"]>=50 else "dn"),
                    ("Profit Factor",      pf_str,                 "up" if res["pf"]>1 else "dn"),
                    ("Max Drawdown",       f"%{res['dd']:.1f}",   "dn"),
                    ("İşlem Sayısı",       str(res["n"]),          "up" if res["n"]>=5 else "wn"),
                ), unsafe_allow_html=True)

                st.markdown(metric_grid(
                    ("Ort. Süre",    f"{res['avg_bars']:.0f} bar",                     ""),
                    ("Test Verisi",  f"{res['bars']} bar / {res['period']}/{res['interval']}", ""),
                ), unsafe_allow_html=True)

                if res["total"] > res["bh"]:
                    st.success("💪 Robot Al-Bekle'yi Yendi! (Slippage + Komisyon + Trailing Stop Dahil)")
                else:
                    st.warning("🐢 Al-Bekle Daha İyi Performans Gösterdi")

                ec = res["ec"]
                st.markdown(
                    f"<div class='bt-info-box' style='margin-top:6px'>"
                    f"<div class='bt-title'>Çıkış Nedeni Dağılımı</div>"
                    f"<div class='bt-row'><span class='bt-lbl'>🛡️ Trailing Stop</span>"
                    f"<span class='bt-val'>{ec.get('TrailStop',0)}</span></div>"
                    f"<div class='bt-row'><span class='bt-lbl'>📉 Trend Kırıldı</span>"
                    f"<span class='bt-val'>{ec.get('Trend',0)}</span></div>"
                    f"<div class='bt-row'><span class='bt-lbl'>⏱️ Max Süre Doldu</span>"
                    f"<span class='bt-val wn'>{ec.get('MaxHold',0)}</span></div>"
                    f"<div class='bt-row'><span class='bt-lbl'>📋 Veri Sonu</span>"
                    f"<span class='bt-val'>{ec.get('EndOfData',0)}</span></div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                st.caption(
                    f"⚠️ Kapanış bazlı + Slippage (ATR×{SLIPPAGE_ATR_FACTOR}) — gerçek sonuç ±%3-5 farklı olabilir.  \n"
                    f"Giriş: Trend + RSI(45-75) + RS + ADX>20 + +DI>-DI + Breakout  \n"
                    f"Canlı 22 filtreden 6 core filtre kullanıldı — istatistiksel anlam için."
                )
    else:
        st.warning("Seçili hisse için veri alınamadı.")