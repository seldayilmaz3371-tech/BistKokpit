import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import datetime

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  BIST PROFESYONEL KOKPİT  V12.0  — tek dosya                              ║
# ║  Sayfa yapısı: sidebar + col[2.5 / 5 / 2.5]  —  değiştirilemez           ║
# ║  V12 değişiklikleri (V11 üzerine):                                          ║
# ║   • Destek/Direnç V2:                                                       ║
# ║       – Lookback 40 → 120 mum (~5 işlem günü)                             ║
# ║       – ATR bazlı cluster birleştirme (ATR * 0.3)                          ║
# ║       – Hacim doğrulaması (pivot hacmi > VolMA20)                          ║
# ║       – %0.5 yakınlık filtresi (gürültü temizleme)                         ║
# ║       – Seviye güç skoru (dokunma sayısı + hacim + yakınlık)               ║
# ║   • 4H Trend Filtresi (yeni veri katmanı + yeni sinyal):                   ║
# ║       – 4 saatlik close > 4H SMA20 → Bull / Bear                           ║
# ║       – Broker tab'ında 7. sinyal olarak gösterilir                        ║
# ║       – Kompozit skor 6 → 7 sinyale yükseldi                              ║
# ║   • Grafik: 4H SMA izlerim artık ayrı renk şerit olarak gösterilir        ║
# ║   • Planner: 4H rejim etiketli risk açıklaması                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

st.set_page_config(
    page_title="BIST Kokpit V12.0",
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

/* ── Destek/Direnç seviye satırı (V12 güç skoru badge) ─ */
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
# V12 yeni sabitler
SR_LOOKBACK       = 120   # destek/direnç lookback (40 → 120)
SR_ATR_CLUSTER    = 0.3   # ATR çarpanı — yakın pivoları birleştir
SR_MIN_DIST_PCT   = 0.005 # %0.5 yakınlık filtresi
H4_SMA_PERIOD     = 20    # 4H SMA periyodu

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
        return df.dropna()
    except Exception:
        return None

# ── YENİ: 4 SAATLİK VERİ ────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def get_data_4h(ticker):
    """
    4 saatlik trend teyidi için veri çeker.
    Close > SMA20(4H) → bull, altında → bear.
    """
    try:
        df = _flatten(yf.download(f"{ticker}.IS", period="60d", interval="1h", progress=False))
        if df is None or df.empty: return None
        # 1h verisini her 4 barda resample → yaklaşık 4H
        df_4h = df.resample("4h").agg({
            "Open":   "first",
            "High":   "max",
            "Low":    "min",
            "Close":  "last",
            "Volume": "sum"
        }).dropna()
        df_4h["SMA20_4H"] = df_4h["Close"].rolling(H4_SMA_PERIOD).mean()
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
    Returns: dict(bull=bool|None, label=str, css=str, icon=str, sma=float|None)
    """
    df = get_data_4h(ticker)
    if df is None or df.empty:
        return {"bull": None, "label": "4H Veri Yok", "css": "h4-none", "icon": "📡", "sma": None}
    try:
        c   = float(df["Close"].iloc[-1])
        sma = float(df["SMA20_4H"].iloc[-1])
        if pd.isna(sma):
            return {"bull": None, "label": "4H Yetersiz Veri", "css": "h4-none", "icon": "📡", "sma": None}
        if c > sma:
            return {"bull": True,  "label": f"4H BULL — {c:.2f} > SMA20 {sma:.2f}",
                    "css": "h4-bull", "icon": "📗", "sma": sma}
        return     {"bull": False, "label": f"4H BEAR — {c:.2f} < SMA20 {sma:.2f}",
                    "css": "h4-bear", "icon": "📕", "sma": sma}
    except Exception:
        return {"bull": None, "label": "4H Hesaplama Hatası", "css": "h4-none", "icon": "⚠️", "sma": None}

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

# ── DESTEK / DİRENÇ V2 ───────────────────────────────────────────────────────
def support_resistance_v2(df, lookback=SR_LOOKBACK):
    """
    V12 — profesyonel seviye tespiti:
    1. Lookback 40 → 120 (yaklaşık 5 işlem günü)
    2. ATR bazlı cluster birleştirme (ATR * SR_ATR_CLUSTER)
    3. Hacim doğrulaması — her pivotur için o bardaki hacim VolMA20'ye kıyasla
    4. %0.5 yakınlık filtresi (gürültü temizleme)
    5. Güç skoru: dokunma sayısı (cluster içi pivot) + hacim bonusu + yakınlık bonusu

    Returns:
        supports    : list[dict]  — {price, score, label}
        resistances : list[dict]  — {price, score, label}
    """
    try:
        lb    = min(lookback, len(df) - 5)
        sub   = df.iloc[-lb:].copy()
        hi    = sub["High"].values
        lo    = sub["Low"].values
        vol   = sub["Volume"].values
        vol_ma = sub["VolMA20"].values
        atr   = float(df["ATR"].iloc[-1])
        price = float(df["Close"].iloc[-1])

        cluster_dist = atr * SR_ATR_CLUSTER

        raw_ph, raw_pl = [], []  # (fiyat, hacim_oranı)
        for i in range(2, len(hi) - 2):
            # Pivot High
            if (hi[i] > hi[i-1] and hi[i] > hi[i-2]
                    and hi[i] > hi[i+1] and hi[i] > hi[i+2]):
                vr = vol[i] / vol_ma[i] if vol_ma[i] > 0 else 1.0
                raw_ph.append((hi[i], vr))
            # Pivot Low
            if (lo[i] < lo[i-1] and lo[i] < lo[i-2]
                    and lo[i] < lo[i+1] and lo[i] < lo[i+2]):
                vr = vol[i] / vol_ma[i] if vol_ma[i] > 0 else 1.0
                raw_pl.append((lo[i], vr))

        def cluster_levels(pivots):
            """ATR bazlı cluster birleştirme + güç skoru hesabı"""
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
                avg_price = sum(p for p, _ in cl) / len(cl)
                avg_vol_r = sum(v for _, v in cl) / len(cl)
                touches   = len(cl)

                # %0.5 yakınlık filtresi — fiyata çok yakın seviyeleri ele
                if abs(avg_price - price) / price < SR_MIN_DIST_PCT:
                    continue

                # Güç skoru (0-10)
                touch_score  = min(touches * 2, 5)        # max 5
                vol_score    = min(avg_vol_r - 1.0, 3)    # max 3, RVOL>1 ise bonus
                vol_score    = max(vol_score, 0)
                dist_pct     = abs(avg_price - price) / price
                near_score   = 2 if dist_pct < 0.03 else (1 if dist_pct < 0.06 else 0)
                score        = touch_score + vol_score + near_score

                if   score >= 7: strength = "GÜÇLÜ"
                elif score >= 4: strength = "ORTA"
                else:            strength = "ZAYIF"

                result.append({
                    "price":    avg_price,
                    "score":    score,
                    "label":    strength,
                    "touches":  touches,
                    "vol_ratio": avg_vol_r,
                })
            return result

        all_res = cluster_levels(raw_ph)
        all_sup = cluster_levels(raw_pl)

        # Fiyat altı → destek, üstü → direnç (tekrar kontrol)
        supports    = sorted([l for l in all_sup if l["price"] < price],
                             key=lambda x: -x["price"])[:3]
        resistances = sorted([l for l in all_res if l["price"] > price],
                             key=lambda x:  x["price"])[:3]

        return supports, resistances

    except Exception:
        return [], []

# ── BACKTEST ─────────────────────────────────────────────────────────────────
def run_backtest(df, xu100_df, h4_bull=None):
    """
    V12: 7. sinyal olarak 4H trend eklenmiştir.
    h4_bull: True/False/None — None ise bu filtre devre dışı
    """
    try:
        sqz      = bollinger_squeeze(df["Close"])
        rs_above, rs_slope, _ = relative_strength_full(df["Close"], xu100_df)
        if rs_above is None:
            return {"err": "XU100 verisi yok"}

        vol_ratio_s = df["Volume"] / df["VolMA20"]
        vol_confirm = (vol_ratio_s > RVOL_THRESHOLD) & (df["Close"] > df["Close"].shift(1))

        bt = pd.concat([
            df[["Close","SMA20","ATR","RSI"]],
            sqz.rename("SQZ"),
            rs_above.rename("RS"),
            rs_slope.rename("RS_SLOPE"),
            vol_confirm.rename("VOL_OK"),
        ], axis=1).ffill().dropna()

        pos, buy_px, stop_px, trades = False, 0.0, 0.0, []
        for _, r in bt.iterrows():
            if not pos:
                rsi_ok  = 50 < r.RSI < 70
                h4_ok   = True if h4_bull is None else h4_bull  # 4H ek filtre
                entry   = (r.Close > r.SMA20 and rsi_ok and r.RS
                           and r.RS_SLOPE and r.SQZ and r.VOL_OK and h4_ok)
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
           "<col style='width:33%'><col style='width:27%'>"
           "<col style='width:8%'><col style='width:10%'>"
           "<col style='width:11%'><col style='width:11%'>"
           "</colgroup>"
           "<thead><tr>"
           "<th style='text-align:left;padding-left:6px'>Hisse</th>"
           "<th>Fiyat</th><th>T</th>"
           "<th title='Bollinger Squeeze'>SQZ</th>"
           "<th title='Relative Strength + Slope'>RS</th>"
           "<th title='Event Risk'>EVT</th>"
           "</tr></thead>")
    body = "<tbody>"
    for r in rows:
        tc = "#22c55e" if r["T"] == "↑" else "#ef4444"
        body += (f"<tr><td class='tkr'>{r['H']}</td><td>{r['F']}</td>"
                 f"<td style='color:{tc}'>{r['T']}</td>"
                 f"<td>{r['SQZ']}</td><td>{r['RS']}</td><td>{r['EVT']}</td></tr>")
    return (f"<div class='scanner-wrapper'>"
            f"<table class='scanner-table'>{hdr}{body}</tbody></table></div>")

def regime_html(reg, extra=""):
    return (f"<div class='regime-banner {reg['css']}' style='{extra}'>"
            f"{reg['icon']} {reg['lbl']}</div>")

def h4_banner_html(h4, extra=""):
    return (f"<div class='h4-banner {h4['css']}' style='{extra}'>"
            f"{h4['icon']} {h4['label']}</div>")

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
    if   skor >= 6: css, lbl, ikon = "kc-al",  "GÜÇLÜ AL",    "💚"
    elif skor >= 5: css, lbl, ikon = "kc-pos",  "OLUMLU",      "🟢"
    elif skor >= 4: css, lbl, ikon = "kc-notr", "NÖTR / İZLE", "🟡"
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

def level_rows_html_v2(price, supports, resistances):
    """
    V12: güç skoru badge'i, dokunma sayısı ve RVOL gösterir.
    supports/resistances: list[dict] (price, score, label, touches, vol_ratio)
    """
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

    # Veri tazelik göstergesi — sidebar
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
                rows.append({
                    "H":   t,
                    "F":   f"{float(d['Close'].iloc[-1]):.2f}",
                    "T":   "↑" if float(d["Close"].iloc[-1]) > float(d["SMA20"].iloc[-1]) else "↓",
                    "SQZ": "🟡" if bool(bollinger_squeeze(d["Close"]).iloc[-1]) else "·",
                    "RS":  rs_icon,
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

        # 4H SMA seviyesi — grafik referansı
        h4_info = h4_trend(secilen)

        # Destek/Direnç V2 seviyeleri — grafik üzerinde çiz
        supports_v2, resistances_v2 = support_resistance_v2(df)

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

        # 4H SMA yatay referans çizgisi
        if h4_info["sma"] is not None:
            fig.add_hline(
                y=h4_info["sma"],
                line_dash="dash",
                line_color="#a78bfa",
                line_width=1.2,
                annotation_text=f"4H SMA20: {h4_info['sma']:.2f}",
                annotation_position="bottom right",
                annotation_font_size=9,
                annotation_font_color="#a78bfa"
            )

        # Destek seviyeleri — yatay çizgi
        for s in supports_v2:
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

        # Direnç seviyeleri — yatay çizgi
        for r in resistances_v2:
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
        # Temel değerler
        fiyat    = float(df["Close"].iloc[-1])
        fiyat_p  = float(df["Close"].iloc[-2]) if len(df) > 1 else fiyat
        atr      = float(df["ATR"].iloc[-1])
        sma      = float(df["SMA20"].iloc[-1])
        rsi      = float(df["RSI"].iloc[-1])
        vol_now  = float(df["Volume"].iloc[-1])
        vol_ma   = float(df["VolMA20"].iloc[-1]) if "VolMA20" in df.columns else vol_now

        # Türetilmiş değerler
        sqz_now              = bool(bollinger_squeeze(df["Close"]).iloc[-1])
        rs_above, rs_slope_s, rs_raw = relative_strength_full(df["Close"], xu100)
        rs_now               = bool(rs_above.iloc[-1])   if rs_above   is not None else None
        rs_slope_now         = bool(rs_slope_s.iloc[-1]) if rs_slope_s is not None else None

        # 4H trend filtresi — V12
        h4_info  = h4_trend(secilen)
        h4_bull  = h4_info["bull"]  # True / False / None

        # Destek/Direnç V2
        supports_v2, resistances_v2 = support_resistance_v2(df)

        fr = data_freshness(df)

        lb        = min(26, len(df) - 1)
        deg_pct   = (fiyat / float(df["Close"].iloc[-lb]) - 1) * 100
        sma_pct   = (fiyat / sma - 1) * 100
        vol_pct   = atr / fiyat * 100
        vol_ratio = vol_now / vol_ma if vol_ma > 0 else 1.0
        vol_confirmed = (vol_ratio >= RVOL_THRESHOLD) and (fiyat > fiyat_p)
        rsi_ok    = 50 < rsi < 70

        # RSI zonu etiketi
        if   rsi >= 70: rz_lbl, rz_cls = "AŞIRI ALIM",  "dn"
        elif rsi >= 55: rz_lbl, rz_cls = "GÜÇLÜ BÖLGE", "up"
        elif rsi >= 50: rz_lbl, rz_cls = "NÖTR ÜST",    "wn"
        elif rsi >= 45: rz_lbl, rz_cls = "NÖTR ALT",    "wn"
        elif rsi >= 30: rz_lbl, rz_cls = "ZAYIF BÖLGE", "dn"
        else:           rz_lbl, rz_cls = "AŞIRI SATIM", "wn"

        # Kompozit skor — 7 filtre (V12)
        sinyaller = [
            fiyat > sma,          # 1. Trend (15m)
            rsi_ok,               # 2. RSI bandı (50-70)
            rs_now is True,       # 3. RS güçlü
            rs_slope_now is True, # 4. RS hızlanıyor
            sqz_now,              # 5. Squeeze
            vol_confirmed,        # 6. Hacim doğrulaması
            h4_bull is True,      # 7. 4H Trend Bull (YENİ)
        ]
        skor = sum(sinyaller)

        # Risk/Ödül
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
            # 4H banner — planner'da da göster
            st.markdown(h4_banner_html(h4_info, "font-size:10px;padding:3px 8px"),
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

            # 1. Kompozit karar
            st.markdown(karar_html(skor, len(sinyaller)), unsafe_allow_html=True)

            # 2. 4H Trend banner
            st.markdown(h4_banner_html(h4_info, "font-size:10px;padding:3px 8px"),
                        unsafe_allow_html=True)

            # 3. Fiyat & Momentum
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

            # 4. Hacim doğrulaması
            st.markdown(sec_div("Hacim Doğrulaması (RVOL)"), unsafe_allow_html=True)
            st.markdown(vol_bar_html(vol_now, vol_ma, vol_ratio, vol_confirmed),
                        unsafe_allow_html=True)

            # 5. Destek / Direnç V2
            st.markdown(sec_div("Destek & Direnç V2 — ATR Cluster · Güç Skoru"), unsafe_allow_html=True)
            if supports_v2 or resistances_v2:
                st.markdown(level_rows_html_v2(fiyat, supports_v2, resistances_v2),
                            unsafe_allow_html=True)
                st.markdown(
                    "<div style='font-size:9px;color:#4a5568;margin-top:3px'>"
                    "Dokunma (x) — RVOL — Güç: GÜÇLÜ≥7 · ORTA≥4 · ZAYIF&lt;4  "
                    f"· Lookback: {SR_LOOKBACK} mum (~5 gün)"
                    "</div>",
                    unsafe_allow_html=True
                )
            else:
                st.caption("Cluster bazlı pivot bulunamadı.")

            # 6. Risk / Ödül
            st.markdown(sec_div("Risk / Ödül"), unsafe_allow_html=True)
            st.markdown(rr_bar_html(risk_tl, reward_tl, rr_ratio), unsafe_allow_html=True)

            # 7. Sinyal detayı — 7 filtre
            st.markdown(sec_div("Sinyal Detayı (7 Filtre — V12)"), unsafe_allow_html=True)

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

            # 4H sinyal satırı
            h4_row = sig_row_html(
                "4H Trend (SMA20)", h4_bull,
                f"📗 Bull — {h4_info['label'].split('—')[1].strip() if '—' in h4_info['label'] else ''}",
                f"📕 Bear — {h4_info['label'].split('—')[1].strip() if '—' in h4_info['label'] else ''}",
                none_txt="📡 4H Veri Yok"
            )

            st.markdown(
                sig_row_html("Trend (SMA20 15m)", fiyat > sma,
                             "✅ Pozitif — Fiyat SMA üstünde",
                             "❌ Negatif — Fiyat SMA altında") +
                sig_row_html("RSI Bandı",          rsi_ok,
                             f"✅ Sağlıklı — {rsi:.1f} (50-70 bandında)",
                             f"⚠️ Bant Dışı — {rsi:.1f} ({'Aşırı Alım' if rsi>=70 else 'Düşük Momentum'})") +
                rs_ab_html + rs_sl_html +
                sig_row_html("Bollinger SQZ",       sqz_now,
                             "🟡 Sıkışma — Enerji Birikti",
                             "⚪ Normal Volatilite") +
                sig_row_html("Hacim Doğrulama",     vol_confirmed,
                             f"✅ RVOL x{vol_ratio:.1f} + Pozitif Kapanış",
                             f"❌ Doğrulanmadı (RVOL x{vol_ratio:.1f})") +
                h4_row,
                unsafe_allow_html=True
            )
            st.caption("⏱️ 15dk gecikmeli veri — giriş öncesi teyit alın.")

        # ╔══════════════════════════════════╗
        # ║  TAB 3 — BACKTEST              ║
        # ╚══════════════════════════════════╝
        with tab3:
            st.caption("Giriş: Trend+RSI(50-70)+RS+RS Slope+SQZ+RVOL+4H Trend  ·  Çıkış: Trend/RS/Stop")
            res = run_backtest(df, xu100, h4_bull=h4_bull)
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

            st.markdown("**4. 4H Trend Filtresi (YENİ — V12)**")
            st.markdown(h4_banner_html(h4_info), unsafe_allow_html=True)
            if h4_bull is None:
                st.info("📡 4H veri çekilemedi.")
            elif h4_bull:
                st.success(f"📗 4H Yükseliş Trendi — Fiyat 4H SMA20 üzerinde.")
            else:
                st.error(f"📕 4H Düşüş Trendi — Dikkatli olun, 15m sinyali zayıf kalır.")
            st.caption("4H trend ters yönde ise 15m sinyaller güvenilirlik kaybeder.")

            st.markdown("**5. Destek/Direnç V2 — En Güçlü Seviyeler**")
            if supports_v2:
                best_sup = max(supports_v2, key=lambda x: x["score"])
                st.success(f"💚 En güçlü destek: {best_sup['price']:.2f} TL  "
                           f"({best_sup['label']} · {best_sup['touches']}x dokunma)")
            if resistances_v2:
                best_res = max(resistances_v2, key=lambda x: x["score"])
                st.error(f"🔴 En güçlü direnç: {best_res['price']:.2f} TL  "
                         f"({best_res['label']} · {best_res['touches']}x dokunma)")
            if not supports_v2 and not resistances_v2:
                st.info("Cluster bazlı seviye bulunamadı.")
            st.caption(f"ATR cluster mesafesi: {float(df['ATR'].iloc[-1])*SR_ATR_CLUSTER:.2f} TL  "
                       f"· Lookback: {SR_LOOKBACK} mum")

            st.markdown("**6. Event Risk**")
            if   evt == "⚠":  st.warning("⚠️ Risk — Yakın bilanço / olay var.")
            elif evt == "✅": st.success("✅ Temiz Takvim.")
            else:              st.info("📡 Sorgulanmamış — Event Risklerini Yükle.")

            st.markdown("**7. Market Regime (XU100 / SMA50)**")
            if   regime["css"] == "rb-bull": st.success(f"🟢 {regime['lbl']}")
            elif regime["css"] == "rb-bear": st.error(f"🔴 {regime['lbl']}")
            else:                             st.warning(f"⚠️ {regime['lbl']}")

            st.markdown("**8. Veri Tazeliği**")
            st.markdown(freshness_html(fr), unsafe_allow_html=True)
    else:
        st.warning("Seçili hisse için veri alınamadı.")