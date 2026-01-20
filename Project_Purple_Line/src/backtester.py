import pandas as pd
import numpy as np
from src.pricing import calculate_option_daily_return

class Backtester:
    """
    策略回測類別 (Backtester Class)

    負責執行策略回測，計算每日資產淨值 (NAV) 與績效指標。
    核心邏輯：
    1. 計算 MA200 趨勢訊號。
    2. Risk-On (Close > MA): 持有現金 (90%) + 合成選擇權 (10%)。
    3. Risk-Off (Close <= MA): 100% 持有現金。
    4. 每日再平衡 (Daily Rebalancing) 以維持固定權重。
    """

    def __init__(self, data, config):
        """
        初始化回測引擎。

        Args:
            data (pd.DataFrame): 包含 Close, RiskFree_Daily, Sigma_Annual 等
            config (dict): 策略參數配置
        """
        self.df = data.copy()
        self.config = config
        self.ma_window = config.get('MA_WINDOW', 200)

        # 讀取資金比例配置
        ratio_config = config.get('CAPITAL_RATIO', {'CASH': 0.9, 'OPTION': 0.1})
        self.cash_ratio = ratio_config['CASH']
        self.option_ratio = ratio_config['OPTION']

    def run_backtest(self):
        """
        執行回測邏輯。

        Returns:
            dict: 包含回測結果的 DataFrame 與績效指標 (metrics)。
        """
        # 1. 計算技術指標 (MA)
        self.df['MA'] = self.df['Close'].rolling(window=self.ma_window).mean()

        # 2. 產生信號 (Signal Generation)
        # Signal = 1 (Risk-On) 當 Close > MA
        # Signal = 0 (Risk-Off) 當 Close <= MA
        # 使用 shift(1) 避免前視偏誤
        self.df['Raw_Signal'] = (self.df['Close'] > self.df['MA']).astype(int)
        self.df['Position'] = self.df['Raw_Signal'].shift(1).fillna(0)

        # 3. 計算每日回報 (Daily Returns)

        # A. 現金部位成長倍數 (Cash Component)
        cash_multiplier = 1 + self.df['RiskFree_Daily']

        # B. 選擇權部位成長倍數 (Option Component)
        # 使用修正後的正確回報計算邏輯: (P_close / P_open) - 1
        T_years = self.config.get('OPTION_MATURITY_YEARS', 1.0)
        strike_method = self.config.get('STRIKE_METHOD', 'ATM')

        # 呼叫 src.pricing 的新函數
        option_ret = calculate_option_daily_return(self.df, T_years, strike_method)
        option_multiplier = 1 + option_ret

        # C. 組合邏輯 (Portfolio Logic - Vectorized)

        # Risk-On: Cash + Option
        risk_on_multiplier = (self.cash_ratio * cash_multiplier) + (self.option_ratio * option_multiplier)

        # Risk-Off: 100% Cash
        risk_off_multiplier = cash_multiplier

        self.df['Strategy_Multiplier'] = np.where(
            self.df['Position'] == 1,
            risk_on_multiplier,
            risk_off_multiplier
        )

        # 4. 計算每日資產淨值 (NAV)
        initial_capital = 100.0
        self.df['NAV'] = initial_capital * self.df['Strategy_Multiplier'].cumprod()

        # 計算 Benchmark NAV
        self.df['Benchmark_Ret'] = self.df['Close'].pct_change().fillna(0)
        self.df['Benchmark_NAV'] = initial_capital * (1 + self.df['Benchmark_Ret']).cumprod()

        # 5. 計算績效指標 (Metrics)
        metrics = self._calculate_metrics()

        return {
            "results": self.df,
            "metrics": metrics
        }

    def _calculate_metrics(self):
        """
        計算 CAGR 與 Max Drawdown。
        """
        total_days = len(self.df)
        if total_days < 1:
            return {"CAGR": 0.0, "Max_DD": 0.0}

        start_nav = self.df['NAV'].iloc[0]
        end_nav = self.df['NAV'].iloc[-1]
        years = total_days / 252.0

        cagr = (end_nav / start_nav) ** (1 / years) - 1

        rolling_max = self.df['NAV'].cummax()
        drawdown = (self.df['NAV'] / rolling_max) - 1
        max_dd = drawdown.min()

        self.df['Drawdown'] = drawdown

        return {
            "CAGR": cagr,
            "Max_DD": max_dd,
            "Final_NAV": end_nav
        }
