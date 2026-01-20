import unittest
import pandas as pd
import numpy as np
import sys
import os

# 將專案根目錄加入路徑以便匯入 src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backtester import Backtester

class TestBacktester(unittest.TestCase):
    def setUp(self):
        # 準備模擬資料
        dates = pd.date_range(start='2020-01-01', periods=10, freq='D')

        # 構造 Close 價格：前5天低於 MA (Risk-Off)，後5天高於 MA (Risk-On)
        # 假設 MA Window = 3
        close_prices = [100, 100, 100, 110, 120, 130, 140, 150, 160, 170]

        # 注意: Backtester 現在需要 'Sigma_Annual' 來計算真實選擇權回報
        self.df = pd.DataFrame({
            'Close': close_prices,
            'RiskFree_Daily': [0.0001] * 10, # 萬分之一日利率
            'Sigma_Annual': [0.2] * 10, # 20% 年化波動率
            'Theoretical_Call_Price': [5.0] * 10 # 舊欄位，Backtester 已不再依賴此欄位，但保留無妨
        }, index=dates)

        # 簡單配置
        self.config = {
            'MA_WINDOW': 3,
            'CAPITAL_RATIO': {'CASH': 0.9, 'OPTION': 0.1},
            'OPTION_MATURITY_YEARS': 1.0,
            'STRIKE_METHOD': 'ATM'
        }

    def test_initialization(self):
        tester = Backtester(self.df, self.config)
        self.assertEqual(tester.ma_window, 3)
        self.assertEqual(tester.cash_ratio, 0.9)

    def test_signal_generation(self):
        tester = Backtester(self.df, self.config)
        results = tester.run_backtest()['results']

        # 檢查 MA
        # Day 0, 1: NaN (Window=3 needs 3 obs)
        # Day 2: (100+100+100)/3 = 100. Close=100. Signal=0.
        # Day 3: (100+100+110)/3 = 103.33. Close=110. Signal=1.

        # Signal (Raw_Signal) should be 1 on Day 3
        self.assertEqual(results['Raw_Signal'].iloc[3], 1)

        # Position (Shifted Signal) should be 1 on Day 4
        self.assertEqual(results['Position'].iloc[4], 1)

    def test_nav_calculation_risk_off(self):
        # 測試 Risk-Off 期間 (前幾天)
        tester = Backtester(self.df, self.config)
        results = tester.run_backtest()['results']

        # Day 2 Position is 0 (from Day 1 Signal)
        # NAV growth should be pure cash: 1.0001

        nav_day1 = results['NAV'].iloc[1]
        nav_day2 = results['NAV'].iloc[2]
        expected_growth = 1 + 0.0001

        self.assertAlmostEqual(nav_day2 / nav_day1, expected_growth, places=6)

    def test_metrics(self):
        tester = Backtester(self.df, self.config)
        metrics = tester.run_backtest()['metrics']

        self.assertIn('CAGR', metrics)
        self.assertIn('Max_DD', metrics)
        self.assertIn('Final_NAV', metrics)

        # NAV 應該是大於 100 的 (因為有利率且有漲幅)
        self.assertGreater(metrics['Final_NAV'], 100)

if __name__ == '__main__':
    unittest.main()
