import numpy as np
import pandas as pd
from scipy.stats import norm

def calculate_call_price(S, K, T, r, sigma):
    """
    Calculates the price of a European call option using the Black-Scholes-Merton model.
    Fully vectorized for Pandas Series or numpy arrays.
    """
    # Safety check for volatility to avoid division by zero
    # If sigma is 0, d1/d2 explode.
    # In practice, fillna handled NaNs, but 0.0 might exist?
    # Let's clip sigma to a small positive number
    sigma = np.maximum(sigma, 1e-4)

    # Safety check for T
    T = np.maximum(T, 1e-4)

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    call_price = (S * norm.cdf(d1)) - (K * np.exp(-r * T) * norm.cdf(d2))

    return call_price

def calculate_option_daily_return(df, T_years=1.0, strike_method='ATM'):
    """
    計算持有選擇權一天的回報率 (Vectorized)。

    邏輯:
    1. 假設每日再平衡 (Daily Rebalancing)。
    2. 昨日 ($t-1$) 進場建立部位:
       - 標的價格: $S_{t-1}$ (Prev_Close)
       - 履約價 $K$: 根據 strike_method 決定 (例如 ATM 則 K = $S_{t-1}$)
       - 剩餘時間: $T_{start} = 1.0$ (假設買入 1 年期 LEAPS)
       - 買入成本: $P_{buy} = BS(S_{t-1}, K, T_{start}, r_{t-1}, \sigma_{t-1})$

    3. 今日 ($t$) 結算部位損益:
       - 標的價格: $S_t$ (Close)
       - 履約價 $K$: 維持不變 (昨日訂下的)
       - 剩餘時間: $T_{end} = 1.0 - 1/252$ (時間流逝 1 天)
       - 目前價值: $P_{sell} = BS(S_t, K, T_{end}, r_t, \sigma_t)$

    4. 回報率: $(P_{sell} / P_{buy}) - 1$

    Parameters:
    -----------
    df : pd.DataFrame
        Must contain 'Close', 'RiskFree_Daily', 'Sigma_Annual'.

    Returns:
    --------
    pd.Series
        Daily return of the option position.
    """
    # 準備資料
    S_today = df['Close']
    S_prev = df['Close'].shift(1)

    # Risk-Free Rate: 使用當日的 (或昨日的? 通常利率變動小，使用當日即可)
    # 必須年化
    r = df['RiskFree_Daily'] * 252

    # Volatility
    sigma = df['Sigma_Annual']

    # 決定履約價 K
    # 假設我們是在 t-1 收盤時買入 ATM Call，所以 K = S_prev
    if strike_method == 'ATM':
        K = S_prev
    elif strike_method.startswith('OTM_'):
        # 例如 OTM_5 => K = S_prev * 1.05
        pct = float(strike_method.split('_')[1]) / 100.0
        K = S_prev * (1 + pct)
    else:
        K = S_prev # Fallback to ATM

    # 計算 t-1 時的買入成本 (Cost)
    # T = T_years (e.g., 1.0)
    # S = S_prev
    # Sigma = sigma.shift(1) (昨日的波動率? 實務上用當日或昨日皆可，假設昨日買入時是用昨日 Vol 定價)
    # 為了向量化方便且避免過多 shift NaN，我們先用當日 Vol 近似，或者嚴謹一點用 shift
    sigma_prev = sigma.shift(1).bfill()
    r_prev = r.shift(1).bfill()

    cost = calculate_call_price(
        S=S_prev,
        K=K,
        T=T_years,
        r=r_prev,
        sigma=sigma_prev
    )

    # 計算 t 時的持有價值 (Value)
    # T = T_years - 1/252
    # S = S_today
    # K = K (Fixed)
    # Sigma = sigma (今日波動率反映市場變化)
    dt = 1.0 / 252.0
    value = calculate_call_price(
        S=S_today,
        K=K,
        T=T_years - dt,
        r=r,
        sigma=sigma
    )

    # 計算回報率
    # 注意: 第一天 S_prev 為 NaN，cost 為 NaN，return 為 NaN。這符合預期。
    ret = (value / cost) - 1

    return ret.fillna(0.0)
