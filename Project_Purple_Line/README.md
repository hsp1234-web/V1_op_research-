# Project Purple Line 策略回測系統

本專案實作了一個基於 **趨勢跟隨 (Trend Following)** 與 **合成選擇權 (Synthetic Option)** 的回測引擎，旨在重現並驗證「紫色線」策略的長期績效。該策略透過動態調整資產配置（現金 vs. 槓桿部位），在規避市場下行風險的同時，捕捉上行趨勢的爆發性收益。

---

## 1. 策略概述

*   **核心思想**: 利用長期移動平均線 (MA200) 作為市場多空的濾網。
    *   **Risk-On (多頭市場)**: 當價格站上 MA200，持有 **90% 現金 + 10% 長期買權 (LEAPS Call)**。利用選擇權的非對稱損益特性（有限虧損，無限獲利）與隱含槓桿來放大收益。
    *   **Risk-Off (空頭市場)**: 當價格跌破 MA200，轉為持有 **100% 現金** (或無風險資產)，賺取無風險利率，並規避資產大幅回撤。

---

## 2. 核心邏輯與數學公式

### 2.1 訊號生成 (Signal Generation)
策略每日計算收盤價的 200 日簡單移動平均 (SMA)：
$$ MA_t = \frac{1}{200} \sum_{i=0}^{199} Close_{t-i} $$

交易訊號 ($S_t$) 判定：
*   若 $Close_t > MA_t$，則 $S_t = 1$ (Risk-On)。
*   若 $Close_t \le MA_t$，則 $S_t = 0$ (Risk-Off)。

**注意**: 為了避免前視偏誤 (Look-ahead Bias)，今日的持倉部位由昨日收盤後的訊號決定：
$$ Position_{t} = S_{t-1} $$

### 2.2 資產淨值計算 (NAV Calculation)
每日資產淨值成長取決於當日持倉狀態：

$$ NAV_t = NAV_{t-1} \times Multiplier_t $$

其中 $Multiplier_t$ 定義如下：

1.  **Risk-Off 狀態 ($Position_t = 0$)**:
    $$ Multiplier_t = 1 + r_{daily} $$
    *   $r_{daily}$: 日無風險利率 (來自 `^IRX` 美國 13 週國庫券利率)。

2.  **Risk-On 狀態 ($Position_t = 1$)**:
    $$ Multiplier_t = 0.90 \times (1 + r_{daily}) + 0.10 \times (1 + R_{opt, t}) $$
    *   假設每日再平衡 (Daily Rebalancing) 維持 90/10 權重。
    *   $R_{opt, t}$: 選擇權當日回報率。

### 2.3 選擇權回報計算 (Option Return Logic)
這是本系統最關鍵的數學模型。為了精確捕捉選擇權的 Gamma (價格加速度) 與 Theta (時間衰減)，我們**不使用**簡單的價格變化率，而是模擬持有特定合約過夜的損益。

*   **建倉 (t-1)**: 在昨日收盤時買入價平 (ATM) 買權。
    *   履約價 $K = Close_{t-1}$
    *   剩餘時間 $T = 1.0$ 年
    *   買入成本 $P_{open} = BS(S=Close_{t-1}, K=K, T=1.0, \sigma=\sigma_{t-1}, r=r_{t-1})$

*   **平倉 (t)**: 在今日收盤時計算該合約價值。
    *   標的價格 $S = Close_t$
    *   履約價 $K$ (維持不變)
    *   剩餘時間 $T = 1.0 - \frac{1}{252}$ (時間流逝一天)
    *   平倉價值 $P_{close} = BS(S=Close_t, K=K, T=1.0 - \Delta t, \sigma=\sigma_t, r=r_t)$

*   **回報率**:
    $$ R_{opt, t} = \frac{P_{close}}{P_{open}} - 1 $$

此方法能正確反映當股價大幅上漲時，選擇權由 ATM 轉為 ITM (價內) 所帶來的 Delta 增加與槓桿放大效果。

---

## 3. 系統功能模組

專案採用模組化設計，位於 `src/` 目錄下：

### A. 資料載入模組 (`src/dataloader.py`)
*   **功能**: 負責從 Yahoo Finance 下載 OHLCV 價格數據、無風險利率 (`^IRX`) 與波動率指數 (如 `GVZ`, `VXTLT`)。
*   **強健性設計**:
    *   **自動重試機制**: 遇到網路連線問題時自動重試 (Max Retries = 3)。
    *   **歷史波動率填補**: 當隱含波動率 (IV) 數據缺失或商品下市 (如 `GVZ` 早期數據缺失) 時，系統會自動切換至 **20 日歷史波動率 (Historical Volatility)** 計算模式，確保回測不中斷。

### B. 定價模組 (`src/pricing.py`)
*   **功能**: 實作向量化 (Vectorized) 的 Black-Scholes-Merton 定價模型。
*   **特色**: 包含上述的 `calculate_option_daily_return` 邏輯，支援大量數據的高效運算。

### C. 回測引擎 (`src/backtester.py`)
*   **功能**: 整合資料與策略邏輯，計算每日 NAV、Drawdown (回撤) 與 CAGR (年化報酬率)。
*   **特色**: 全程使用 `pandas` 與 `numpy` 向量運算，完全避免 Python `for` 迴圈，大幅提升回測速度。

### D. 主程式 (`main.py`)
*   **功能**: 讀取設定檔 (`config/settings.py`)，批次執行多個策略 (如 GLD, TLT, TWII)，並繪製對數座標 (Log Scale) 的績效比較圖。

---

## 4. 測試過程與結果

### 4.1 單元測試
我們在 `tests/test_backtester.py` 中建立了完整的測試案例，驗證：
1.  **訊號生成**: 確認 MA200 邏輯正確，且訊號有正確位移 (Shift) 以避免偷看未來數據。
2.  **Risk-Off 回報**: 確認在空手期間，資產僅隨無風險利率增長。
3.  **Metrics 計算**: 驗證 CAGR 與 Max Drawdown 的計算公式準確無誤。

### 4.2 實證回測結果 (截至 2026-01-20)
執行 `main.py` 後的模擬結果顯示策略在長期趨勢明顯的資產上表現優異：

| 標的資產 | 策略代號 | 年化報酬率 (CAGR) | 備註 |
| :--- | :--- | :--- | :--- |
| **黃金 (Gold)** | `GLD` | **12.79%** | 受惠於修正後的 Gamma 計算，捕捉到長線多頭的爆發力。 |
| **台股指數** | `^TWII` | **8.63%** | 穩健增長，有效避開空頭修正。 |
| **美債 20年+** | `TLT` | **2.67%** | 成功避開 2020-2023 的崩盤 (Drawdown 控制優異)，但受限於低利率環境與長期空頭。 |

*(註: 修正回報計算邏輯前，GLD CAGR 僅約 5%。修正後更貼近真實選擇權特性。)*

---

## 5. 執行指南

### 安裝依賴
```bash
pip install -r requirements.txt
# 主要依賴: pandas, numpy, yfinance, matplotlib, scipy
```

### 執行回測
```bash
python main.py
```
程式執行完畢後，將會在根目錄產生 `strategy_analysis.jpg` 圖表，展示策略與買入持有 (Benchmark) 的績效對比。

### 調整參數
若需修改回測區間或資金比例，請編輯 `config/settings.py`：
```python
'GLD_STRATEGY': {
    'MA_WINDOW': 200,          # 均線週期
    'CAPITAL_RATIO': {
        'CASH': 0.90,          # 現金比例
        'OPTION': 0.10         # 選擇權比例
    },
    'STRIKE_METHOD': 'ATM',    # 履約價選擇 (支援 ATM, OTM_5 等)
    ...
}
```
