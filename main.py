import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import datetime

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  BIST PROFESYONEL KOKPİT  V13.0  — tek dosya                              ║
# ║  Sayfa yapısı: sidebar + col[2.5 / 5 / 2.5]  —  değiştirilemez           ║
# ║  V13 değişiklikleri (V12 üzerine):                                          ║
# ║   • Breakout Kalite Filtresi (8. sinyal):                                   ║
# ║       – Close > High.rolling(20).max().shift(1)                             ║
# ║       – Yalancı sıkışma kırılımlarını etkili biçimde eler                  ║
# ║   • ATR Rejim Filtresi (9. sinyal):                                         ║
# ║       – ATR% = ATR / Close * 100 > ATR_PCT_MIN (varsayılan %1.2)           ║
# ║       – Ölü / hareketsiz hisseleri ve düşük volatilite dönemlerini eler    ║
# ║   • 4H Trend Yükseltmesi: SMA20 → EMA20/EMA50 Çaprazı                     ║
# ║       – EMA20_4H > EMA50_4H → Bull  (daha güvenilir trend teyidi)          ║
# ║       – Eski SMA20 mantığı tamamen kaldırıldı                               ║
# ║   • Destek/Direnç V3:                                                       ║
# ║       – Lookback 120 → 200 mum (~8 işlem günü)                             ║
# ║       – Hacim ağırlıklı fiyat kümelenmesi (VWAP proxy)                     ║
# ║       – Minimum pivot kalite skoru eşiği: küçük dönüş noktaları atlanır    ║
# ║       – Güç skoru üst sınırı 10 → 12 (daha hassas ayrıştırma)             ║
# ║   • Kompozit skor 7 → 9 sinyale yükseldi                                  ║
# ║   • Backtest: 9 filtreli giriş koşulu                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

st.set_page_config(
    page_title="BIST Kokpit V13.0",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
section.main > div { padding-top: 0.35rem !important; }

/* ── Scanner tablo ──────────────────────────────────── */
.scanner-wrapper {
    max-height: 420px; overflow-y: auto; overflow-x: hidden;
    border: 1px solid #2d3a50; border-radius: 6px;
}
.scanner-table {
    width: 100%; border-collapse: collapse;
    font-size: 11.5px; font-family: 'Courier New', monospace;
    table-layout: fixed;
}
.scanner-table th {
    background: #1e2535; color: #94a3b8; font-size: 10px; font-weight: 600;
    letter-spacing: 0.4px; padding: 4px 3px; text-align: center;
    border-bottom: 1px solid #2d3a50;
    position: sticky; top: 0; z-index: 1;
    overflow: hidden; white-space: nowrap;
}
.scanner-table td {
    padding: 3px 3px; text-align: center;
    border-bottom: 1px solid #1a2030; color: #e2e8f0;
    overflow: hidden; white-space: nowrap;
}
.scanner-table td.tkr { text-align:left; padding-left:6px; font-weight:600; color:#cbd5e1; }
.scanner-table tr:hover td { background: #1e2a3a; }

/* ── Rejim banner ───────────────────────────────────── */
.regime-banner {
    padding: 5px 10px; border-radius: 6px; font-size: 11px; font-weight: 700;
    margin-bottom: 7px; text-align: center; letter-spacing: 0.3px;
}
.rb-bull { background:#14532d; color:#86efac; border:1px solid #22c55e; }
.rb-bear { background:#450a0a; color:#fca5a5; border:1px solid #ef4444; }
.rb-none { background:#1c1f2e; color:#94a3b8; border:1px solid #374151; }

/* ── 4H Rejim banner ────────────────────────────────── */
.h4-banner {
    padding: 4px 10px; border-radius: 5px; font-size: 11px; font-weight: 600;
    margin-bottom: 5px; text-align: center;
}
.h4-bull { background:#0a2318; color:#86efac; border:1px solid #16a34a; }
.h4-bear { background:#2a0a0a; color:#fca5a5; border:1px solid #dc2626; }
.h4-none { background:#1a1c2e; color:#94a3b8; border:1px solid #374151; }

/* ── ATR Rejim banner ───────────────────────────────── */
.atr-banner {
    padding: 4px 10px; border-radius: 5px; font-size: 11px; font-weight: 600;
    margin-bottom: 5px; text-align: center;
}
.atr-active { background:#0a1a2e; color:#93c5fd; border:1px solid #3b82f6; }
.atr-dead   { background:#1f1a0a; color:#fcd34d; border:1px solid #b45309; }
.atr-none   { background:#1a1c2e; color:#94a3b8; border:1px solid #374151; }

/* ── Veri tazelik banner ────────────────────────────── */
.freshness-banner {
    padding: 4px 10px; border-radius: 5px; font-size: 11px; font-weight: 600;
    margin-bottom: 6px; text-align: center;
}
.fb-green  { background:#052e16; color:#86efac; border:1px solid #22c55e; }
.fb-yellow { background:#1c1a08; color:#fde047; border:1px solid #ca8a04; }
.fb-red    { background:#450a0a; color:#fca5a5; border:1px solid #ef4444; }

/* ── 2-sütun metrik grid ────────────────────────────── */
.mg { display:grid; grid-template-columns:1fr 1fr; gap:4px; margin-bottom:5px; }
.mc {
    background:#1a1f2e; border:1px solid #2d3448;
    border-radius:6px; padding:6px 8px; text-align:center;
}
.mc .lb { font-size:9px; color:#6b7594; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:1px; }
.mc .vl { font-size:13px; font-weight:700; color:#e2e8f0; font-family:'Courier New',monospace; }
.mc .vl.up { color:#22c55e; }
.mc .vl.dn { color:#ef4444; }
.mc .vl.wn { color:#f59e0b; }

/* ── Kompozit karar kartı ───────────────────────────── */
.karar-card { border-radius:8px; padding:10px 14px; margin-bottom:8px; text-align:center; }
.karar-card .karar-lbl { font-size:9px; color:#94a3b8; text-transform:uppercase; letter-spacing:0.6px; }
.karar-card .karar-val { font-size:18px; font-weight:800; letter-spacing:0.5px; margin-top:2px; }
.kc-al   { background:#052e16; border:2px solid #22c55e; }
.kc-pos  { background:#0f2a1a; border:1px solid #16a34a; }
.kc-notr { background:#1c1a08; border:1px solid #ca8a04; }
.kc-sat  { background:#2a0a0a; border:1px solid #dc2626; }
.kc-al   .karar-val { color:#4ade80; }
.kc-pos  .karar-val { color:#86efac; }
.kc-notr .karar-val { color:#fde047; }
.kc-sat  .karar-val { color:#fca5a5; }

/* ── Sinyal satırı ──────────────────────────────────── */
.sr {
    display:flex; justify-content:space-between; align-items:center;
    background:#0d1421; border-radius:5px;
    padding:5px 9px; margin-bottom:3px; font-size:11px;
    border-left: 3px solid transparent;
}
.sr.ok  { border-left-color:#22c55e; }
.sr.nok { border-left-color:#ef4444; }
.sr.unk { border-left-color:#f59e0b; }
.sr .sl { color:#94a3b8; font-size:10.5px; }
.sr .sv { font-weight:700; font-family:monospace; font-size:11px; }
.sr .sv.up { color:#4ade80; }
.sr .sv.dn { color:#f87171; }
.sr .sv.wn { color:#fbbf24; }

/* ── Bölüm ayırıcı başlık ───────────────────────────── */
.sec-divider {
    font-size:9px; color:#4a5568; text-transform:uppercase;
    letter-spacing:1px; margin:8px 0 4px 0;
    border-bottom:1px solid #1e2535; padding-bottom:2px;
}

/* ── Destek/Direnç seviye satırı ───────────────────── */
.level-row {
    display:flex; justify-content:space-between; align-items:center;
    padding: 4px 9px; margin-bottom:2px; border-radius:4px;
    font-size:11px; font-family:'Courier New',monospace;
}
.level-row.res { background:#2a0a0a; border-left:3px solid #ef4444; }
.level-row.sup { background:#052e16; border-left:3px solid #22c55e; }
.level-row.cur { background:#0f1f35; border-left:3px solid #38bdf8; }
.level-row .lv-lbl { color:#94a3b8; font-size:10px; }
.level-row .lv-val { font-weight:700; }
.level-row.res .lv-val { color:#f87171; }
.level-row.sup .lv-val { color:#4ade80; }
.level-row.cur .lv-val { color:#38bdf8; }
.level-row .lv-dist    { font-size:10px; color:#6b7594; }
.level-row .lv-badge   { font-size:9px; padding:1px 5px; border-radius:3px; font-weight:700; }
.lv-strong { background:#14532d; color:#86efac; }
.lv-mid    { background:#1c2a0a; color:#bef264; }
.lv-weak   { background:#1a1a2e; color:#6b7594; }

/* ── Risk/Ödül göstergesi ───────────────────────────── */
.rr-bar-wrap {
    background:#0d1421; border-radius:6px; padding:8px 10px; margin-bottom:5px;
}
.rr-bar-wrap .rr-lbl { font-size:9px; color:#6b7594; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:5px; }
.rr-bar-outer { background:#1e2535; border-radius:4px; height:10px; width:100%; overflow:hidden; }
.rr-nums { display:flex; justify-content:space-between; margin-top:4px; font-size:10px; font-family:monospace; }
.rr-nums .rr-r  { color:#f87171; }
.rr-nums .rr-rw { color:#4ade80; }

/* ── Hacim çubuğu ───────────────────────────────────── */
.vol-bar-wrap {
    background:#0d1421; border-radius:6px; padding:8px 10px; margin-bottom:5px;
}
.vol-bar-wrap .vb-lbl { font-size:9px; color:#6b7594; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:5px; }
.vol-bar-outer { background:#1e2535; border-radius:4px; height:10px; width:100%; overflow:hidden; }
.vb-nums { display:flex; justify-content:space-between; margin-top:4px; font-size:10px; font-family:monospace; color:#94a3b8; }

/* ── ATR Rejim çubuğu ───────────────────────────────── */
.atr-reg-wrap {
    background:#0d1421; border-radius:6px; padding:8px 10px; margin-bottom:5px;
}
.atr-reg-wrap .ar-lbl { font-size:9px; color:#6b7594; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:5px; }
.atr-reg-outer { background:#1e2535; border-radius:4px; height:10px; width:100%; overflow:hidden; }
.ar-nums { display:flex; justify-content:space-between; margin-top:4px; font-size:10px; font-family:monospace; color:#94a3b8; }
</style>
""", unsafe_allow_html=True)

# ── SABITLER ─────────────────────────────────────────────────────────────────
BIST_30 = [
    "AKBNK","ALARK","ARCLK","ASTOR","BIMAS","BRSAN","EKGYO","ENKAI","EREGL",
    "FROTO","GARAN","GUBRF","HEKTS","ISCTR","KCHOL","KONTR","KRDMD","OYAKC",
    "PGSUS","PETKM","SAHOL","SASA","SISE","TCELL","THYAO","TKFEN","TOASO",
    "TUPRS","VAKBN","YKBNK"
]
SQUEEZE_LOOKBACK  = 250   # ~2 haftalık 15m pencere
REGIME_SMA        = 50    # XU100 SMA periyodu
RISK_FULL         = 0.02  # bull rejim risk oranı
RISK_HALF         = 0.01  # bear rejim risk oranı
ATR_MULT          = 1.5   # stop mesafesi çarpanı
RVOL_THRESHOLD    = 1.5   # hacim doğrulama eşiği
RS_SLOPE_BARS     = 5     # RS slope hesabı için bar sayısı
FRESHNESS_WARN    = 20    # dk — sarı eşik
FRESHNESS_RED     = 40    # dk — kırmızı eşik
# V12 sabitler
SR_LOOKBACK       = 200   # destek/direnç lookback (120 → 200, ~8 işlem günü)
SR_ATR_CLUSTER    = 0.3   # ATR çarpanı — yakın pivoları birleştir
SR_MIN_DIST_PCT   = 0.005 # %0.5 yakınlık filtresi
# V13 yeni sabitler
H4_EMA_FAST       = 20    # 4H EMA hızlı periyot (eski: SMA20)
H4_EMA_SLOW       = 50    # 4H EMA yavaş periyot (YENİ: çapraz filtresi)
BREAKOUT_BARS     = 20    # Breakout kalite filtresi: son N mumun zirvesi
ATR_PCT_MIN       = 1.2   # ATR% minimum eşiği — ölü hisseleri eler

if "watchlist"   not in st.session_state: st.session_state.watchlist   = BIST_30.copy()
if "event_risks" not in st.session_state: st.session_state.event_risks = {}
if "scan_rows"   not in st.session_state: st.session_state.scan_rows   = []

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
                return df
        except Exception:
            continue
    return None

@st.cache_data(ttl=300)
def get_data(ticker):
    try:
        df = _flatten(yf.download(f"{ticker}.IS", period="60d", interval="15m", progress=False))
        if df is None: return None
        c = df["Close"]
        df["SMA20"]   = c.rolling(20).mean()
        d = c.diff()
        df["RSI"]     = 100 - (100 / (1 + d.where(d > 0, 0.0).rolling(14).mean()
                                          / (-d.where(d < 0, 0.0)).rolling(14).mean()))
        df["TR"]      = pd.concat([
            df["High"] - df["Low"],
            (df["High"] - c.shift()).abs(),
            (df["Low"]  - c.shift()).abs()
        ], axis=1).max(axis=1)
        df["ATR"]     = df["TR"].rolling(14).mean()
        df["VolMA20"] = df["Volume"].rolling(20).mean()
        # V13: Breakout kalite için rolling max
        df["HH20"]    = df["High"].rolling(BREAKOUT_BARS).max()
        return df.dropna()
    except Exception:
        return None

# ── 4 SAATLİK VERİ — V13 EMA ÇAPRAZ ─────────────────────────────────────────
@st.cache_data(ttl=600)
def get_data_4h(ticker):
    """
    V13: SMA20 → EMA20/EMA50 çaprazı.
    EMA20_4H > EMA50_4H → Bull (daha güvenilir trend teyidi)
    """
    try:
        df = _flatten(yf.download(f"{ticker}.IS", period="60d", interval="1h", progress=False))
        if df is None or df.empty: return None
        df_4h = df.resample("4h").agg({
            "Open":   "first",
            "High":   "max",
            "Low":    "min",
            "Close":  "last",
            "Volume": "sum"
        }).dropna()
        # V13: EMA20 ve EMA50 (SMA yerine)
        df_4h["EMA20_4H"] = df_4h["Close"].ewm(span=H4_EMA_FAST, adjust=False).mean()
        df_4h["EMA50_4H"] = df_4h["Close"].ewm(span=H4_EMA_SLOW, adjust=False).mean()
        df_4h["ATR_4H"]   = pd.concat([
            df_4h["High"] - df_4h["Low"],
            (df_4h["High"] - df_4h["Close"].shift()).abs(),
            (df_4h["Low"]  - df_4h["Close"].shift()).abs()
        ], axis=1).max(axis=1).rolling(14).mean()
        df_4h["VolMA20_4H"] = df_4h["Volume"].rolling(20).mean()
        return df_4h.dropna()
    except Exception:
        return None

def h4_trend(ticker):
    """
    V13: EMA20 > EMA50 çaprazı → Bull / Bear
    Returns: dict(bull, label, css, icon, ema_fast, ema_slow)
    """
    df = get_data_4h(ticker)
    if df is None or df.empty:
        return {"bull": None, "label": "4H Veri Yok", "css": "h4-none", "icon": "📡",
                "ema_fast": None, "ema_slow": None}
    try:
        ema_f = float(df["EMA20_4H"].iloc[-1])
        ema_s = float(df["EMA50_4H"].iloc[-1])
        if pd.isna(ema_f) or pd.isna(ema_s):
            return {"bull": None, "label": "4H Yetersiz Veri", "css": "h4-none", "icon": "📡",
                    "ema_fast": None, "ema_slow": None}
        if ema_f > ema_s:
            return {"bull": True,
                    "label": f"4H BULL — EMA20 {ema_f:.2f} > EMA50 {ema_s:.2f}",
                    "css": "h4-bull", "icon": "📗",
                    "ema_fast": ema_f, "ema_slow": ema_s}
        return     {"bull": False,
                    "label": f"4H BEAR — EMA20 {ema_f:.2f} < EMA50 {ema_s:.2f}",
                    "css": "h4-bear", "icon": "📕",
                    "ema_fast": ema_f, "ema_slow": ema_s}
    except Exception:
        return {"bull": None, "label": "4H Hesaplama Hatası", "css": "h4-none", "icon": "⚠️",
                "ema_fast": None, "ema_slow": None}

# ── V13: ATR REJİM FİLTRESİ ──────────────────────────────────────────────────
def atr_regime(df):
    """
    ATR% = ATR / Close * 100 > ATR_PCT_MIN → aktif volatilite
    Ölü / hareketsiz hisseleri eler.
    Returns: dict(active, atr_pct, label, css, icon)
    """
    try:
        atr   = float(df["ATR"].iloc[-1])
        price = float(df["Close"].iloc[-1])
        atr_p = atr / price * 100
        if atr_p >= ATR_PCT_MIN:
            return {"active": True,
                    "atr_pct": atr_p,
                    "label": f"ATR% {atr_p:.2f} — Volatilite Yeterli",
                    "css": "atr-active", "icon": "💠"}
        return     {"active": False,
                    "atr_pct": atr_p,
                    "label": f"ATR% {atr_p:.2f} — Düşük Volatilite (Ölü Hisse?)",
                    "css": "atr-dead", "icon": "🪨"}
    except Exception:
        return {"active": None, "atr_pct": 0,
                "label": "ATR Hesaplanamadı", "css": "atr-none", "icon": "⚠️"}

# ── V13: BREAKOUT KALİTE FİLTRESİ ────────────────────────────────────────────
def breakout_quality(df):
    """
    Close > HH20.shift(1) → gerçek breakout
    Yalancı sıkışma kırılımlarını eler.
    Returns: dict(ok, close, hh20, label)
    """
    try:
        close = float(df["Close"].iloc[-1])
        hh20  = float(df["HH20"].shift(1).iloc[-1])
        ok    = close > hh20
        if ok:
            label = f"✅ Yeni Zirve — {close:.2f} > {BREAKOUT_BARS}m Max {hh20:.2f}"
        else:
            label = f"❌ Zirve Yok — {close:.2f} ≤ {BREAKOUT_BARS}m Max {hh20:.2f}"
        return {"ok": ok, "close": close, "hh20": hh20, "label": label}
    except Exception:
        return {"ok": None, "close": 0, "hh20": 0, "label": "Breakout hesaplanamadı"}

# ── İNDİKATÖR FONKSİYONLARI ─────────────────────────────────────────────────
def bollinger_squeeze(close):
    try:
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        sma  = close.rolling(20).mean()
        bb_w = (4 * close.rolling(20).std()) / sma
        thr  = bb_w.rolling(SQUEEZE_LOOKBACK, min_periods=30).quantile(0.15)
        return bb_w < thr
    except Exception:
        return pd.Series(False, index=close.index)

def relative_strength_full(stock_close, xu100_df):
    if xu100_df is None or xu100_df.empty:
        return None, None, None
    try:
        if isinstance(stock_close, pd.DataFrame): stock_close = stock_close.iloc[:, 0]
        xu = xu100_df["Close"].copy(); xu.name = "idx"
        sc = stock_close.copy();       sc.name = "stk"
        aln = pd.concat([sc, xu], axis=1).ffill().dropna()
        if aln.empty: return None, None, None
        rs       = aln["stk"] / aln["idx"]
        rs_ma    = rs.rolling(20).mean()
        rs_above = rs > rs_ma
        rs_slope = rs.diff(RS_SLOPE_BARS) > 0
        return rs_above, rs_slope, rs
    except Exception:
        return None, None, None

def event_risk(ticker):
    try:
        ed = yf.Ticker(f"{ticker}.IS").info.get("earningsDate")
        if ed is None: return "📡"
        if isinstance(ed, list): ed = ed[0]
        if isinstance(ed, int):  ed = datetime.datetime.fromtimestamp(ed)
        return "⚠" if 0 <= (ed.replace(tzinfo=None) - datetime.datetime.now()).days <= 5 else "✅"
    except Exception:
        return "📡"

def market_regime(xu100_df):
    na = {"lbl":"Belirsiz","css":"rb-none","risk":RISK_FULL,"icon":"⚠️"}
    if xu100_df is None or "SMA50" not in xu100_df.columns: return na
    try:
        c, s = float(xu100_df["Close"].iloc[-1]), float(xu100_df["SMA50"].iloc[-1])
        if pd.isna(s): return na
        if c > s:
            return {"lbl":f"BULL — XU100 {c:.0f} > SMA50 {s:.0f}",
                    "css":"rb-bull","risk":RISK_FULL,"icon":"🟢"}
        return     {"lbl":f"BEAR — XU100 {c:.0f} < SMA50 {s:.0f}",
                    "css":"rb-bear","risk":RISK_HALF,"icon":"🔴"}
    except Exception:
        return na

def data_freshness(df):
    try:
        age = (datetime.datetime.now() - df.index[-1]).total_seconds() / 60
        if age > 900:
            return {"age": age, "css": "fb-yellow", "icon": "⏸️",
                    "label": "Piyasa Kapalı", "is_closed": True}
        elif age <= FRESHNESS_WARN:
            return {"age": age, "css": "fb-green", "icon": "🟢",
                    "label": f"Güncel — {age:.0f}dk önce", "is_closed": False}
        elif age <= FRESHNESS_RED:
            return {"age": age, "css": "fb-yellow", "icon": "🟡",
                    "label": f"Gecikiyor — {age:.0f}dk önce", "is_closed": False}
        else:
            return {"age": age, "css": "fb-red", "icon": "🔴",
                    "label": f"BAYAT — {age:.0f}dk önce", "is_closed": False}
    except Exception:
        return {"age": 0, "css": "fb-yellow", "icon": "⚠️",
                "label": "Zaman bilinmiyor", "is_closed": False}

# ── DESTEK / DİRENÇ V3 ───────────────────────────────────────────────────────
def support_resistance_v3(df, lookback=SR_LOOKBACK):
    """
    V13 — kurumsal seviye tespiti:
    1. Lookback 120 → 200 mum (~8 işlem günü)
    2. ATR bazlı cluster birleştirme (ATR * SR_ATR_CLUSTER)
    3. Hacim ağırlıklı ortalama fiyat (VWAP proxy) — daha hassas seviye merkezi
    4. Minimum pivot kalite skoru eşiği — küçük dönüşler atlanır
    5. %0.5 yakınlık filtresi
    6. Güç skoru max 12 (V12: 10) — daha hassas ayrıştırma

    Returns:
        supports    : list[dict]  — {price, score, label, touches, vol_ratio}
        resistances : list[dict]  — {price, score, label, touches, vol_ratio}
    """
    try:
        lb    = min(lookback, len(df) - 5)
        sub   = df.iloc[-lb:].copy()
        hi    = sub["High"].values
        lo    = sub["Low"].values
        cl    = sub["Close"].values
        vol   = sub["Volume"].values
        vol_ma = sub["VolMA20"].values
        atr   = float(df["ATR"].iloc[-1])
        price = float(df["Close"].iloc[-1])

        cluster_dist = atr * SR_ATR_CLUSTER

        raw_ph, raw_pl = [], []  # (fiyat, hacim, hacim_oranı)
        for i in range(3, len(hi) - 3):
            vr = vol[i] / vol_ma[i] if vol_ma[i] > 0 else 1.0
            # Pivot High — 3 bar sol/sağ (V12: 2 bar) → daha temiz pivotlar
            if (hi[i] > hi[i-1] and hi[i] > hi[i-2] and hi[i] > hi[i-3]
                    and hi[i] > hi[i+1] and hi[i] > hi[i+2] and hi[i] > hi[i+3]):
                raw_ph.append((hi[i], vol[i], vr))
            # Pivot Low
            if (lo[i] < lo[i-1] and lo[i] < lo[i-2] and lo[i] < lo[i-3]
                    and lo[i] < lo[i+1] and lo[i] < lo[i+2] and lo[i] < lo[i+3]):
                raw_pl.append((lo[i], vol[i], vr))

        def cluster_levels(pivots):
            """
            ATR bazlı cluster birleştirme.
            V13: Hacim ağırlıklı fiyat ortalaması (VWAP proxy) kullanılır.
            """
            if not pivots: return []
            pivots_s = sorted(pivots, key=lambda x: x[0])
            clusters = []
            cur = [pivots_s[0]]
            for pv in pivots_s[1:]:
                if abs(pv[0] - cur[-1][0]) <= cluster_dist:
                    cur.append(pv)
                else:
                    clusters.append(cur)
                    cur = [pv]
            clusters.append(cur)

            result = []
            for cl in clusters:
                # V13: Hacim ağırlıklı ortalama fiyat
                total_vol  = sum(v for _, v, _ in cl)
                if total_vol > 0:
                    vwap_price = sum(p * v for p, v, _ in cl) / total_vol
                else:
                    vwap_price = sum(p for p, _, _ in cl) / len(cl)
                avg_vol_r  = sum(vr for _, _, vr in cl) / len(cl)
                touches    = len(cl)

                # %0.5 yakınlık filtresi
                if abs(vwap_price - price) / price < SR_MIN_DIST_PCT:
                    continue

                # Güç skoru (0-12, V12: 0-10)
                touch_score = min(touches * 2, 6)          # max 6 (V12: 5)
                vol_score   = min(avg_vol_r - 1.0, 4)      # max 4 (V12: 3)
                vol_score   = max(vol_score, 0)
                dist_pct    = abs(vwap_price - price) / price
                near_score  = 2 if dist_pct < 0.03 else (1 if dist_pct < 0.06 else 0)
                score       = touch_score + vol_score + near_score

                # V13: Minimum kalite eşiği — tek dokunuşlu zayıf pivotlar atlanır
                if touches < 2 and avg_vol_r < 1.2:
                    continue

                if   score >= 8: strength = "GÜÇLÜ"   # V12: 7
                elif score >= 5: strength = "ORTA"     # V12: 4
                else:            strength = "ZAYIF"

                result.append({
                    "price":     vwap_price,
                    "score":     score,
                    "label":     strength,
                    "touches":   touches,
                    "vol_ratio": avg_vol_r,
                })
            return result

        all_res = cluster_levels(raw_ph)
        all_sup = cluster_levels(raw_pl)

        supports    = sorted([l for l in all_sup if l["price"] < price],
                             key=lambda x: -x["price"])[:3]
        resistances = sorted([l for l in all_res if l["price"] > price],
                             key=lambda x:  x["price"])[:3]

        return supports, resistances

    except Exception:
        return [], []

# ── BACKTEST ─────────────────────────────────────────────────────────────────
def run_backtest(df, xu100_df, h4_bull=None, atr_active=None, breakout_ok=None):
    """
    V13: 9 sinyalli giriş koşulu.
    h4_bull, atr_active, breakout_ok: None ise ilgili filtre devre dışı
    """
    try:
        sqz      = bollinger_squeeze(df["Close"])
        rs_above, rs_slope, _ = relative_strength_full(df["Close"], xu100_df)
        if rs_above is None:
            return {"err": "XU100 verisi yok"}

        vol_ratio_s = df["Volume"] / df["VolMA20"]
        vol_confirm = (vol_ratio_s > RVOL_THRESHOLD) & (df["Close"] > df["Close"].shift(1))

        # Breakout serisi
        hh20_shift = df["HH20"].shift(1)
        bkout_series = df["Close"] > hh20_shift

        # ATR% serisi
        atr_pct_series = df["ATR"] / df["Close"] * 100
        atr_ok_series  = atr_pct_series > ATR_PCT_MIN

        bt = pd.concat([
            df[["Close","SMA20","ATR","RSI"]],
            sqz.rename("SQZ"),
            rs_above.rename("RS"),
            rs_slope.rename("RS_SLOPE"),
            vol_confirm.rename("VOL_OK"),
            bkout_series.rename("BKT"),
            atr_ok_series.rename("ATR_OK"),
        ], axis=1).ffill().dropna()

        pos, buy_px, stop_px, trades = False, 0.0, 0.0, []
        for _, r in bt.iterrows():
            if not pos:
                rsi_ok  = 50 < r.RSI < 70
                h4_ok   = True if h4_bull is None else h4_bull
                atr_ok  = True if atr_active is None else bool(r.ATR_OK)
                bkt_ok  = True if breakout_ok is None else bool(r.BKT)
                entry   = (r.Close > r.SMA20 and rsi_ok and r.RS
                           and r.RS_SLOPE and r.SQZ and r.VOL_OK
                           and h4_ok and atr_ok and bkt_ok)
                if entry:
                    pos, buy_px = True, r.Close
                    stop_px = buy_px - r.ATR * ATR_MULT
            else:
                reason = ("Trend" if r.Close < r.SMA20 else
                          "RS"    if not r.RS           else
                          "Stop"  if r.Close < stop_px  else None)
                if reason:
                    trades.append({"pnl": (r.Close - buy_px) / buy_px * 100, "why": reason})
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
           "<col style='width:28%'><col style='width:22%'>"
           "<col style='width:7%'><col style='width:9%'>"
           "<col style='width:9%'><col style='width:9%'>"
           "<col style='width:8%'><col style='width:8%'>"
           "</colgroup>"
           "<thead><tr>"
           "<th style='text-align:left;padding-left:6px'>Hisse</th>"
           "<th>Fiyat</th><th>T</th>"
           "<th title='Bollinger Squeeze'>SQZ</th>"
           "<th title='Relative Strength + Slope'>RS</th>"
           "<th title='Breakout Kalite'>BKT</th>"
           "<th title='ATR Rejim'>ATR</th>"
           "<th title='Event Risk'>EVT</th>"
           "</tr></thead>")
    body = "<tbody>"
    for r in rows:
        tc = "#22c55e" if r["T"] == "↑" else "#ef4444"
        body += (f"<tr><td class='tkr'>{r['H']}</td><td>{r['F']}</td>"
                 f"<td style='color:{tc}'>{r['T']}</td>"
                 f"<td>{r['SQZ']}</td><td>{r['RS']}</td>"
                 f"<td>{r['BKT']}</td><td>{r['ATR']}</td>"
                 f"<td>{r['EVT']}</td></tr>")
    return (f"<div class='scanner-wrapper'>"
            f"<table class='scanner-table'>{hdr}{body}</tbody></table></div>")

def regime_html(reg, extra=""):
    return (f"<div class='regime-banner {reg['css']}' style='{extra}'>"
            f"{reg['icon']} {reg['lbl']}</div>")

def h4_banner_html(h4, extra=""):
    return (f"<div class='h4-banner {h4['css']}' style='{extra}'>"
            f"{h4['icon']} {h4['label']}</div>")

def atr_banner_html(atr_reg, extra=""):
    return (f"<div class='atr-banner {atr_reg['css']}' style='{extra}'>"
            f"{atr_reg['icon']} {atr_reg['label']}</div>")

def freshness_html(fr, extra=""):
    return (f"<div class='freshness-banner {fr['css']}' style='{extra}'>"
            f"{fr['icon']} {fr['label']}</div>")

def sig_row_html(label, state, t_txt, f_txt, none_txt="📡 Veri Yok"):
    if state is None:
        return (f"<div class='sr unk'><span class='sl'>{label}</span>"
                f"<span class='sv wn'>{none_txt}</span></div>")
    cls  = "ok" if state else "nok"
    vcls = "up" if state else "dn"
    return (f"<div class='sr {cls}'><span class='sl'>{label}</span>"
            f"<span class='sv {vcls}'>{t_txt if state else f_txt}</span></div>")

def karar_html(skor, n):
    # V13: 9 sinyal — eşikler güncellendi
    if   skor >= 8: css, lbl, ikon = "kc-al",  "GÜÇLÜ AL",    "💚"
    elif skor >= 6: css, lbl, ikon = "kc-pos",  "OLUMLU",      "🟢"
    elif skor >= 5: css, lbl, ikon = "kc-notr", "NÖTR / İZLE", "🟡"
    else:           css, lbl, ikon = "kc-sat",  "BEKLE / SAT", "🔴"
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

def strength_badge(label):
    css = "lv-strong" if label == "GÜÇLÜ" else ("lv-mid" if label == "ORTA" else "lv-weak")
    return f"<span class='lv-badge {css}'>{label}</span>"

def level_rows_html_v3(price, supports, resistances):
    html = ""
    for r in reversed(resistances):
        dist = (r["price"] / price - 1) * 100
        html += (f"<div class='level-row res'>"
                 f"<span class='lv-lbl'>Direnç {strength_badge(r['label'])}</span>"
                 f"<span class='lv-val'>{r['price']:.2f} TL</span>"
                 f"<span class='lv-dist'>+{dist:.2f}% · {r['touches']}x · RVOL {r['vol_ratio']:.1f}</span>"
                 f"</div>")
    html += (f"<div class='level-row cur'>"
             f"<span class='lv-lbl'>Güncel Fiyat</span>"
             f"<span class='lv-val'>{price:.2f} TL</span>"
             f"<span class='lv-dist'>—</span></div>")
    for s in supports:
        dist = (price / s["price"] - 1) * 100
        html += (f"<div class='level-row sup'>"
                 f"<span class='lv-lbl'>Destek {strength_badge(s['label'])}</span>"
                 f"<span class='lv-val'>{s['price']:.2f} TL</span>"
                 f"<span class='lv-dist'>-{dist:.2f}% · {s['touches']}x · RVOL {s['vol_ratio']:.1f}</span>"
                 f"</div>")
    return html

def rr_bar_html(risk_tl, reward_tl, ratio):
    total  = risk_tl + reward_tl
    r_pct  = int(risk_tl / total * 100) if total > 0 else 50
    rw_pct = 100 - r_pct
    r_cls  = "up" if ratio >= 2.0 else ("wn" if ratio >= 1.0 else "dn")
    return (f"<div class='rr-bar-wrap'>"
            f"<div class='rr-lbl'>Risk / Ödül Oranı</div>"
            f"<div class='rr-bar-outer'>"
            f"<div style='display:flex;height:100%'>"
            f"<div style='width:{r_pct}%;height:100%;background:#ef4444;border-radius:4px 0 0 4px'></div>"
            f"<div style='width:{rw_pct}%;height:100%;background:#22c55e;border-radius:0 4px 4px 0'></div>"
            f"</div></div>"
            f"<div class='rr-nums'>"
            f"<span class='rr-r'>Risk: {risk_tl:.2f} TL</span>"
            f"<span class='vl {r_cls}' style='font-size:11px;font-weight:700'>1:{ratio:.2f}</span>"
            f"<span class='rr-rw'>Ödül: {reward_tl:.2f} TL</span>"
            f"</div></div>")

def vol_bar_html(vol_now, vol_ma, vol_ratio, vol_confirmed):
    fill_pct  = min(int(vol_ratio * 50), 100)
    bar_color = "#22c55e" if vol_confirmed else ("#f59e0b" if vol_ratio >= RVOL_THRESHOLD else "#94a3b8")
    if vol_confirmed:
        label = f"✅ DOĞRULANDI (x{vol_ratio:.2f}) — Pozitif Kapanış"
    elif vol_ratio >= RVOL_THRESHOLD:
        label = f"⚠️ YÜKSEK HACİM (x{vol_ratio:.2f}) — Negatif Kapanış (Dağıtım?)"
    else:
        label = f"Düşük/Normal Hacim (x{vol_ratio:.2f})"
    return (f"<div class='vol-bar-wrap'>"
            f"<div class='vb-lbl'>Hacim Doğrulaması — {label}</div>"
            f"<div class='vol-bar-outer'>"
            f"<div style='width:{fill_pct}%;height:100%;background:{bar_color};border-radius:4px'></div>"
            f"</div>"
            f"<div class='vb-nums'>"
            f"<span>Anlık: {vol_now:,.0f}</span>"
            f"<span>RVOL: x{vol_ratio:.2f}</span>"
            f"<span>Ort(20): {vol_ma:,.0f}</span>"
            f"</div></div>")

def atr_reg_bar_html(atr_pct, active):
    fill = min(int(atr_pct / (ATR_PCT_MIN * 2) * 100), 100)
    bar_color = "#3b82f6" if active else "#b45309"
    eşik_str  = f"Eşik: %{ATR_PCT_MIN}"
    return (f"<div class='atr-reg-wrap'>"
            f"<div class='ar-lbl'>ATR Rejim Filtresi — ATR% = {atr_pct:.2f}  ·  {eşik_str}</div>"
            f"<div class='atr-reg-outer'>"
            f"<div style='width:{fill}%;height:100%;background:{bar_color};border-radius:4px'></div>"
            f"</div>"
            f"<div class='ar-nums'>"
            f"<span>ATR%: {atr_pct:.2f}</span>"
            f"<span style='color:{'#3b82f6' if active else '#f59e0b'}'>"
            f"{'✅ Volatilite Yeterli' if active else '⚠️ Volatilite Yetersiz'}</span>"
            f"<span>Min: %{ATR_PCT_MIN}</span>"
            f"</div></div>")

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
xu100  = get_xu100()
regime = market_regime(xu100)

with st.sidebar:
    st.header("⚙️ Kontrol Paneli")
    st.markdown(regime_html(regime), unsafe_allow_html=True)

    secilen = st.selectbox("Hisse Seçin:", sorted(st.session_state.watchlist))
    portfoy = st.number_input(
        f"Portföy (TL)  ·  Aktif risk: %{regime['risk']*100:.0f}",
        min_value=1000, value=100_000, step=10_000
    )

    df_sb = get_data(secilen)
    if df_sb is not None:
        fr_sb = data_freshness(df_sb)
        st.markdown(freshness_html(fr_sb), unsafe_allow_html=True)
    else:
        st.error("🔴 Veri Bağlantısı Koptu")

    st.divider()
    st.subheader("📝 Liste Yönetimi")
    yeni = st.text_input("Hisse Ekle (Örn: ASELS):").upper().strip()
    b1, b2 = st.columns(2)
    with b1:
        if st.button("➕ Ekle") and yeni and yeni not in st.session_state.watchlist:
            st.session_state.watchlist.append(yeni); st.rerun()
    with b2:
        if st.button("🗑️ Çıkar") and len(st.session_state.watchlist) > 1:
            st.session_state.watchlist.remove(secilen); st.rerun()

# ── ANA EKRAN ─────────────────────────────────────────────────────────────────
col_l, col_c, col_r = st.columns([2.5, 5, 2.5])
df = get_data(secilen)

# ══ SOL: SCANNER ══════════════════════════════════════════════════════════════
with col_l:
    st.markdown("### 🚀 Tarayıcı")
    st.caption("⏱️ BIST verileri 15dk gecikmelidir.")

    if st.button("Tüm Listeyi Tara"):
        st.session_state.scan_rows = []
        rows, prog = [], st.progress(0, text="Başlatılıyor...")
        wl = sorted(st.session_state.watchlist)
        for i, t in enumerate(wl):
            d = get_data(t)
            if d is not None:
                rs_ab, rs_sl, _ = relative_strength_full(d["Close"], xu100)
                if rs_ab is None:
                    rs_icon = "📡"
                elif bool(rs_ab.iloc[-1]) and bool(rs_sl.iloc[-1]):
                    rs_icon = "💚"
                elif bool(rs_ab.iloc[-1]):
                    rs_icon = "🟡"
                else:
                    rs_icon = "🔴"
                # V13: Breakout ve ATR ikonları
                bkt = breakout_quality(d)
                atr_r = atr_regime(d)
                rows.append({
                    "H":   t,
                    "F":   f"{float(d['Close'].iloc[-1]):.2f}",
                    "T":   "↑" if float(d["Close"].iloc[-1]) > float(d["SMA20"].iloc[-1]) else "↓",
                    "SQZ": "🟡" if bool(bollinger_squeeze(d["Close"]).iloc[-1]) else "·",
                    "RS":  rs_icon,
                    "BKT": "💥" if bkt["ok"] else "·",
                    "ATR": "💠" if atr_r["active"] else "🪨",
                    "EVT": st.session_state.event_risks.get(t, "📡"),
                })
            prog.progress((i + 1) / len(wl), text=f"Tarıyor: {t}")
        prog.empty()
        st.session_state.scan_rows = rows

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

        h4_info = h4_trend(secilen)
        supports_v3, resistances_v3 = support_resistance_v3(df)
        bkt_info = breakout_quality(df)

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

        # 4H EMA referans çizgileri (V13: iki ayrı EMA)
        if h4_info["ema_fast"] is not None:
            fig.add_hline(
                y=h4_info["ema_fast"],
                line_dash="dash",
                line_color="#a78bfa",
                line_width=1.2,
                annotation_text=f"4H EMA20: {h4_info['ema_fast']:.2f}",
                annotation_position="bottom right",
                annotation_font_size=9,
                annotation_font_color="#a78bfa"
            )
        if h4_info["ema_slow"] is not None:
            fig.add_hline(
                y=h4_info["ema_slow"],
                line_dash="dot",
                line_color="#7c3aed",
                line_width=1.0,
                annotation_text=f"4H EMA50: {h4_info['ema_slow']:.2f}",
                annotation_position="top right",
                annotation_font_size=9,
                annotation_font_color="#7c3aed"
            )

        # V13: Breakout seviyesi — son 20 mumun zirvesi
        if bkt_info["hh20"] > 0:
            dash_style = "solid" if bkt_info["ok"] else "dashdot"
            color_bkt  = "rgba(251,191,36,0.6)" if not bkt_info["ok"] else "rgba(251,191,36,0.3)"
            fig.add_hline(
                y=bkt_info["hh20"],
                line_dash=dash_style,
                line_color=color_bkt,
                line_width=1.0,
                annotation_text=f"BKT({BREAKOUT_BARS}m): {bkt_info['hh20']:.2f}",
                annotation_position="top left",
                annotation_font_size=8,
                annotation_font_color="rgba(251,191,36,0.9)"
            )

        # Destek seviyeleri
        for s in supports_v3:
            dash = "solid" if s["label"] == "GÜÇLÜ" else "dot"
            fig.add_hline(
                y=s["price"],
                line_dash=dash,
                line_color="rgba(34,197,94,0.5)",
                line_width=1,
                annotation_text=f"D {s['price']:.2f} ({s['label']})",
                annotation_position="bottom left",
                annotation_font_size=8,
                annotation_font_color="rgba(34,197,94,0.8)"
            )

        # Direnç seviyeleri
        for r in resistances_v3:
            dash = "solid" if r["label"] == "GÜÇLÜ" else "dot"
            fig.add_hline(
                y=r["price"],
                line_dash=dash,
                line_color="rgba(239,68,68,0.5)",
                line_width=1,
                annotation_text=f"R {r['price']:.2f} ({r['label']})",
                annotation_position="top left",
                annotation_font_size=8,
                annotation_font_color="rgba(239,68,68,0.8)"
            )

        fig.update_xaxes(rangebreaks=[
            dict(bounds=["18:00", "09:55"]),
            dict(bounds=["sat", "mon"])
        ])
        fig.update_layout(
            template="plotly_dark", height=530,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.02, x=0, font=dict(size=10))
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
        vol_ma   = float(df["VolMA20"].iloc[-1]) if "VolMA20" in df.columns else vol_now

        sqz_now              = bool(bollinger_squeeze(df["Close"]).iloc[-1])
        rs_above, rs_slope_s, rs_raw = relative_strength_full(df["Close"], xu100)
        rs_now               = bool(rs_above.iloc[-1])   if rs_above   is not None else None
        rs_slope_now         = bool(rs_slope_s.iloc[-1]) if rs_slope_s is not None else None

        # V13: yeni filtreler
        h4_info   = h4_trend(secilen)
        h4_bull   = h4_info["bull"]
        atr_reg   = atr_regime(df)
        bkt_info  = breakout_quality(df)

        supports_v3, resistances_v3 = support_resistance_v3(df)
        fr = data_freshness(df)

        lb        = min(26, len(df) - 1)
        deg_pct   = (fiyat / float(df["Close"].iloc[-lb]) - 1) * 100
        sma_pct   = (fiyat / sma - 1) * 100
        vol_pct   = atr / fiyat * 100
        vol_ratio = vol_now / vol_ma if vol_ma > 0 else 1.0
        vol_confirmed = (vol_ratio >= RVOL_THRESHOLD) and (fiyat > fiyat_p)
        rsi_ok    = 50 < rsi < 70

        if   rsi >= 70: rz_lbl, rz_cls = "AŞIRI ALIM",  "dn"
        elif rsi >= 55: rz_lbl, rz_cls = "GÜÇLÜ BÖLGE", "up"
        elif rsi >= 50: rz_lbl, rz_cls = "NÖTR ÜST",    "wn"
        elif rsi >= 45: rz_lbl, rz_cls = "NÖTR ALT",    "wn"
        elif rsi >= 30: rz_lbl, rz_cls = "ZAYIF BÖLGE", "dn"
        else:           rz_lbl, rz_cls = "AŞIRI SATIM", "wn"

        # Kompozit skor — 9 sinyal (V13)
        sinyaller = [
            fiyat > sma,              # 1. Trend (15m SMA20)
            rsi_ok,                   # 2. RSI bandı (50-70)
            rs_now is True,           # 3. RS güçlü
            rs_slope_now is True,     # 4. RS hızlanıyor
            sqz_now,                  # 5. Squeeze
            vol_confirmed,            # 6. Hacim doğrulaması
            h4_bull is True,          # 7. 4H EMA20 > EMA50 (YENİ çapraz)
            atr_reg["active"] is True,# 8. ATR% > %1.2 (YENİ)
            bkt_info["ok"] is True,   # 9. Breakout kalite (YENİ)
        ]
        skor = sum(sinyaller)

        stop      = fiyat - atr * ATR_MULT
        risk_tl   = max(fiyat - stop, 0.01)
        hedef     = fiyat + risk_tl * 2
        reward_tl = hedef - fiyat
        rr_ratio  = reward_tl / risk_tl

        tab1, tab2, tab3, tab4 = st.tabs(["📐 Planner", "🤖 Broker", "📊 Backtest", "🎯 Filtreler"])

        # ╔══════════════════════════════════╗
        # ║  TAB 1 — PLANNER               ║
        # ╚══════════════════════════════════╝
        with tab1:
            aktif_risk = regime["risk"]
            lot        = int((portfoy * aktif_risk) / risk_tl)
            maliyet    = lot * fiyat
            st.markdown(regime_html(regime, "font-size:10px;padding:4px 8px"),
                        unsafe_allow_html=True)
            st.markdown(h4_banner_html(h4_info, "font-size:10px;padding:3px 8px"),
                        unsafe_allow_html=True)
            st.markdown(atr_banner_html(atr_reg, "font-size:10px;padding:3px 8px"),
                        unsafe_allow_html=True)
            st.markdown(metric_grid(
                ("Giriş Fiyatı",   f"{fiyat:.2f} TL",       ""),
                ("Stop Loss",      f"{stop:.2f} TL",         "dn"),
                ("Hedef Fiyat",    f"{hedef:.2f} TL",        "up"),
                ("Önerilen Lot",   f"{lot} adet",            "up" if fiyat > sma else "wn"),
                ("Toplam Maliyet", f"{maliyet:,.0f} TL",     ""),
                ("Risk / İşlem",   f"%{aktif_risk*100:.0f}", "wn"),
            ), unsafe_allow_html=True)
            st.markdown(rr_bar_html(risk_tl, reward_tl, rr_ratio), unsafe_allow_html=True)
            st.caption("⏱️ 15dk gecikmeli veri — giriş öncesi teyit alın.")

        # ╔══════════════════════════════════╗
        # ║  TAB 2 — BROKER                ║
        # ╚══════════════════════════════════╝
        with tab2:
            if fr["css"] in ("fb-yellow", "fb-red") and not fr["is_closed"]:
                st.markdown(freshness_html(fr, "font-size:10px;padding:3px 8px"),
                            unsafe_allow_html=True)

            st.markdown(karar_html(skor, len(sinyaller)), unsafe_allow_html=True)
            st.markdown(h4_banner_html(h4_info, "font-size:10px;padding:3px 8px"),
                        unsafe_allow_html=True)

            st.markdown(sec_div("Fiyat & Momentum"), unsafe_allow_html=True)
            st.markdown(metric_grid(
                ("Değişim (~6.5s)", f"{'+'if deg_pct>=0 else ''}{deg_pct:.2f}%",
                 "up" if deg_pct >= 0 else "dn"),
                ("SMA20 Uzaklığı",  f"{'+'if sma_pct>=0 else ''}{sma_pct:.2f}%",
                 "up" if sma_pct >= 0 else "dn"),
                ("RSI (14)",        f"{rsi:.1f}",  rz_cls),
                ("RSI Zonu",        rz_lbl,        rz_cls),
                ("Volatilite ATR%", f"%{vol_pct:.2f}", "wn"),
                ("ATR Değeri",      f"{atr:.2f} TL",   ""),
            ), unsafe_allow_html=True)

            st.markdown(sec_div("Hacim Doğrulaması (RVOL)"), unsafe_allow_html=True)
            st.markdown(vol_bar_html(vol_now, vol_ma, vol_ratio, vol_confirmed),
                        unsafe_allow_html=True)

            # V13: ATR Rejim Çubuğu
            st.markdown(sec_div("ATR Rejim Filtresi (V13)"), unsafe_allow_html=True)
            st.markdown(atr_reg_bar_html(atr_reg["atr_pct"], atr_reg["active"]),
                        unsafe_allow_html=True)

            # V13: Breakout Kalite
            st.markdown(sec_div(f"Breakout Kalite — Son {BREAKOUT_BARS} Mum Zirvesi (V13)"),
                        unsafe_allow_html=True)
            bkt_css = "ok" if bkt_info["ok"] else ("nok" if bkt_info["ok"] is False else "unk")
            bkt_vcls = "up" if bkt_info["ok"] else "dn"
            st.markdown(
                f"<div class='sr {bkt_css}'>"
                f"<span class='sl'>Breakout Kalite</span>"
                f"<span class='sv {bkt_vcls}'>{bkt_info['label']}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

            st.markdown(sec_div(f"Destek & Direnç V3 — VWAP Cluster · {SR_LOOKBACK} Mum"),
                        unsafe_allow_html=True)
            if supports_v3 or resistances_v3:
                st.markdown(level_rows_html_v3(fiyat, supports_v3, resistances_v3),
                            unsafe_allow_html=True)
                st.markdown(
                    "<div style='font-size:9px;color:#4a5568;margin-top:3px'>"
                    "Dokunma (x) — RVOL — Güç: GÜÇLÜ≥8 · ORTA≥5 · ZAYIF&lt;5  "
                    f"· VWAP proxy · Lookback: {SR_LOOKBACK} mum (~8 gün)"
                    "</div>",
                    unsafe_allow_html=True
                )
            else:
                st.caption("Cluster bazlı pivot bulunamadı.")

            st.markdown(sec_div("Risk / Ödül"), unsafe_allow_html=True)
            st.markdown(rr_bar_html(risk_tl, reward_tl, rr_ratio), unsafe_allow_html=True)

            # Sinyal detayı — 9 filtre
            st.markdown(sec_div("Sinyal Detayı (9 Filtre — V13)"), unsafe_allow_html=True)

            if rs_now is None:
                rs_ab_html = (f"<div class='sr unk'><span class='sl'>RS vs XU100</span>"
                              f"<span class='sv wn'>📡 Veri Yok</span></div>")
                rs_sl_html = (f"<div class='sr unk'><span class='sl'>RS Slope (Hız)</span>"
                              f"<span class='sv wn'>📡 Veri Yok</span></div>")
            else:
                rs_ab_html = sig_row_html("RS vs XU100", rs_now,
                                          "💚 XU100'den Güçlü", "🔴 XU100'den Zayıf")
                rs_sl_html = sig_row_html("RS Slope (Hız)", rs_slope_now,
                                          "📈 RS Hızlanıyor — Lider Adayı",
                                          "📉 RS Yavaşlıyor — Dikkat")

            h4_row = sig_row_html(
                "4H EMA Çapraz", h4_bull,
                f"📗 Bull — EMA20>EMA50",
                f"📕 Bear — EMA20<EMA50",
                none_txt="📡 4H Veri Yok"
            )
            atr_row = sig_row_html(
                f"ATR Rejim (≥%{ATR_PCT_MIN})", atr_reg["active"],
                f"💠 Aktif — ATR%{atr_reg['atr_pct']:.2f}",
                f"🪨 Düşük — ATR%{atr_reg['atr_pct']:.2f}",
                none_txt="⚠️ Hesaplanamadı"
            )
            bkt_row = sig_row_html(
                f"Breakout ({BREAKOUT_BARS}m Zirvesi)", bkt_info["ok"],
                f"💥 Yeni Zirve — {bkt_info['close']:.2f} > {bkt_info['hh20']:.2f}",
                f"⏸️ Zirve Yok — {bkt_info['close']:.2f} ≤ {bkt_info['hh20']:.2f}",
                none_txt="📡 Hesaplanamadı"
            )

            st.markdown(
                sig_row_html("Trend (SMA20 15m)", fiyat > sma,
                             "✅ Pozitif — Fiyat SMA üstünde",
                             "❌ Negatif — Fiyat SMA altında") +
                sig_row_html("RSI Bandı", rsi_ok,
                             f"✅ Sağlıklı — {rsi:.1f} (50-70 bandında)",
                             f"⚠️ Bant Dışı — {rsi:.1f} ({'Aşırı Alım' if rsi>=70 else 'Düşük Momentum'})") +
                rs_ab_html + rs_sl_html +
                sig_row_html("Bollinger SQZ", sqz_now,
                             "🟡 Sıkışma — Enerji Birikti",
                             "⚪ Normal Volatilite") +
                sig_row_html("Hacim Doğrulama", vol_confirmed,
                             f"✅ RVOL x{vol_ratio:.1f} + Pozitif Kapanış",
                             f"❌ Doğrulanmadı (RVOL x{vol_ratio:.1f})") +
                h4_row + atr_row + bkt_row,
                unsafe_allow_html=True
            )
            st.caption("⏱️ 15dk gecikmeli veri — giriş öncesi teyit alın.")

        # ╔══════════════════════════════════╗
        # ║  TAB 3 — BACKTEST              ║
        # ╚══════════════════════════════════╝
        with tab3:
            st.caption("Giriş: Trend+RSI(50-70)+RS+RS Slope+SQZ+RVOL+4H EMA Çapraz+ATR Rejim+Breakout  ·  Çıkış: Trend/RS/Stop")
            res = run_backtest(df, xu100,
                               h4_bull=h4_bull,
                               atr_active=atr_reg["active"],
                               breakout_ok=bkt_info["ok"])
            if res.get("err"):
                st.info(f"ℹ️ {res['err']}")
            else:
                ret_cls = "up" if res["total"] >= 0 else "dn"
                pf_str  = f"{res['pf']:.2f}" if res["pf"] != float("inf") else "∞"
                st.markdown(metric_grid(
                    ("Robot Getiri",  f"%{res['total']:.2f}", ret_cls),
                    ("Al-Bekle",      f"%{res['bh']:.2f}",    "up" if res["bh"] >= 0 else "dn"),
                    ("Win Rate",      f"%{res['wr']:.1f}",    "up" if res["wr"] >= 50 else "dn"),
                    ("Profit Factor", pf_str,                  "up" if res["pf"] > 1 else "dn"),
                    ("Max Drawdown",  f"%{res['dd']:.1f}",    "dn"),
                    ("İşlem Sayısı",  str(res["n"]),           ""),
                ), unsafe_allow_html=True)
                if res["total"] > res["bh"]:
                    st.success("💪 Robot Piyasayı Yendi!")
                else:
                    st.warning("🐢 Al-Bekle Daha İyi Performans Gösterdi")
                ec = res["ec"]
                st.markdown(
                    f"<div style='font-size:10px;color:#6b7594;margin-top:4px'>"
                    f"Çıkış → Trend kırıldı: <b>{ec['Trend']}</b>  "
                    f"RS bozuldu: <b>{ec['RS']}</b>  "
                    f"Stop çalıştı: <b>{ec['Stop']}</b></div>",
                    unsafe_allow_html=True
                )
                st.caption("⚠️ Kapanış fiyatı bazlı — gerçek sonuç %5-10 farklı olabilir.")

        # ╔══════════════════════════════════╗
        # ║  TAB 4 — FİLTRELER             ║
        # ╚══════════════════════════════════╝
        with tab4:
            evt = st.session_state.event_risks.get(secilen, "📡")

            st.markdown("**1. Bollinger Squeeze**")
            if sqz_now: st.warning("🟡 Sıkışma Aktif — Patlama yaklaşıyor.")
            else:        st.info("⚪ Sıkışma Yok — Volatilite normal.")

            st.markdown("**2. Relative Strength**")
            if   rs_now is None: st.error("📡 XU100 verisi alınamadı.")
            elif rs_now:         st.success("💚 Güçlü — BIST 100'den daha iyi.")
            else:                st.error("🔴 Zayıf — BIST 100'den daha kötü.")

            st.markdown("**3. RS Slope (Hız)**")
            if   rs_slope_now is None: st.info("📡 Hesaplanamadı.")
            elif rs_slope_now:         st.success("📈 Hızlanıyor — Lider Adayı.")
            else:                      st.warning("📉 Yavaşlıyor — Momentum Zayıflıyor.")

            st.markdown("**4. 4H EMA Çaprazı (V13 — SMA→EMA)**")
            st.markdown(h4_banner_html(h4_info), unsafe_allow_html=True)
            if h4_bull is None:
                st.info("📡 4H veri çekilemedi.")
            elif h4_bull:
                st.success("📗 4H Yükseliş — EMA20 > EMA50 (güvenilir trend teyidi).")
            else:
                st.error("📕 4H Düşüş — EMA20 < EMA50. 15m sinyaller güvenilirlik kaybeder.")
            st.caption("EMA çaprazı, SMA'ya kıyasla geç sinyal ama daha az yanlış alarm üretir.")

            st.markdown(f"**5. ATR Rejim Filtresi (V13 — YENİ)**")
            st.markdown(atr_banner_html(atr_reg), unsafe_allow_html=True)
            st.markdown(atr_reg_bar_html(atr_reg["atr_pct"], atr_reg["active"]),
                        unsafe_allow_html=True)
            if atr_reg["active"]:
                st.success(f"💠 Volatilite yeterli — sistem açık.")
            else:
                st.warning(f"🪨 ATR% {atr_reg['atr_pct']:.2f} < %{ATR_PCT_MIN} — "
                           f"Hisse hareketsiz, sinyaller güvenilmez.")
            st.caption(f"ATR% = ATR / Fiyat × 100. Eşik: %{ATR_PCT_MIN}. "
                       f"Düşük volatilite → sıkışmadan hareket gelmeyebilir.")

            st.markdown(f"**6. Breakout Kalite Filtresi (V13 — YENİ)**")
            if bkt_info["ok"] is True:
                st.success(f"💥 Gerçek Kırılım — Fiyat son {BREAKOUT_BARS} mumun zirvesini geçti!\n"
                           f"Kapanış: {bkt_info['close']:.2f} TL  >  Zirve: {bkt_info['hh20']:.2f} TL")
            elif bkt_info["ok"] is False:
                st.warning(f"⏸️ Zirve Kırılmadı — Sıkışma devam ediyor.\n"
                           f"Kapanış: {bkt_info['close']:.2f} TL  ≤  Zirve: {bkt_info['hh20']:.2f} TL")
            else:
                st.info("📡 Breakout hesaplanamadı.")
            st.caption(f"Close > High.rolling({BREAKOUT_BARS}).max().shift(1) "
                       f"— yalancı sıkışma kırılımlarını eler.")

            st.markdown("**7. Destek/Direnç V3 — En Güçlü Seviyeler**")
            if supports_v3:
                best_sup = max(supports_v3, key=lambda x: x["score"])
                st.success(f"💚 En güçlü destek: {best_sup['price']:.2f} TL  "
                           f"({best_sup['label']} · {best_sup['touches']}x dokunma · "
                           f"RVOL {best_sup['vol_ratio']:.1f})")
            if resistances_v3:
                best_res = max(resistances_v3, key=lambda x: x["score"])
                st.error(f"🔴 En güçlü direnç: {best_res['price']:.2f} TL  "
                         f"({best_res['label']} · {best_res['touches']}x dokunma · "
                         f"RVOL {best_res['vol_ratio']:.1f})")
            if not supports_v3 and not resistances_v3:
                st.info("Cluster bazlı seviye bulunamadı.")
            st.caption(f"VWAP proxy · 3-bar pivot · Lookback: {SR_LOOKBACK} mum · "
                       f"ATR cluster: {float(df['ATR'].iloc[-1])*SR_ATR_CLUSTER:.2f} TL")

            st.markdown("**8. Event Risk**")
            if   evt == "⚠":  st.warning("⚠️ Risk — Yakın bilanço / olay var.")
            elif evt == "✅": st.success("✅ Temiz Takvim.")
            else:              st.info("📡 Sorgulanmamış — Event Risklerini Yükle.")

            st.markdown("**9. Market Regime (XU100 / SMA50)**")
            if   regime["css"] == "rb-bull": st.success(f"🟢 {regime['lbl']}")
            elif regime["css"] == "rb-bear": st.error(f"🔴 {regime['lbl']}")
            else:                             st.warning(f"⚠️ {regime['lbl']}")

            st.markdown("**10. Veri Tazeliği**")
            st.markdown(freshness_html(fr), unsafe_allow_html=True)
    else:
        st.warning("Seçili hisse için veri alınamadı.")