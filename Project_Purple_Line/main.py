import sys
import os
import logging
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from config.settings import STRATEGY_CONFIG
from src.dataloader import DataLoader
from src.pricing import calculate_call_price
from src.backtester import Backtester

# 設定日誌記錄 (Configure Logging)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_strategy(strategy_key):
    """
    執行單一策略的回測流程。
    """
    config = STRATEGY_CONFIG[strategy_key]
    name = config['NAME']
    logging.info(f"=== 開始執行策略: {name} ===")

    loader = DataLoader(start_date=config['START_DATE'])

    try:
        # 1. 獲取資料
        df = loader.fetch_data(
            ticker=config['TICKER'],
            irx_ticker=config['RISK_FREE_TICKER'],
            vol_ticker=config['VOLATILITY_TICKER']
        )

        # 2. 選擇權定價 (Pricing)
        T = config['OPTION_MATURITY_YEARS']
        # 注意: RiskFree_Daily 已經是日利率，轉換為年化利率給 BS 模型
        df['Theoretical_Call_Price'] = calculate_call_price(
            S=df['Close'],
            K=df['Close'], # ATM
            T=T,
            r=df['RiskFree_Daily'] * 252,
            sigma=df['Sigma_Annual']
        )

        # 3. 回測 (Backtest)
        tester = Backtester(df, config)
        results_pack = tester.run_backtest()

        logging.info(f"{name} 完成。CAGR: {results_pack['metrics']['CAGR']:.2%}")
        return results_pack, name

    except Exception as e:
        logging.error(f"{name} 執行失敗: {e}")
        return None, name

def main():
    logging.info("啟動 Project Purple Line 多策略回測...")

    strategies = ['GLD_STRATEGY', 'TLT_STRATEGY', 'TWII_STRATEGY']
    results_map = {}

    # 執行所有策略
    for key in strategies:
        res, name = run_strategy(key)
        if res:
            results_map[name] = res

    if not results_map:
        logging.error("沒有任何策略執行成功。")
        sys.exit(1)

    # 繪製綜合圖表
    logging.info("正在產生綜合分析圖表...")

    # 設定圖表風格 (嘗試使用預設風格，避免字型問題，標籤使用英文)
    plt.style.use('default')

    # 建立 3x1 的子圖
    fig, axes = plt.subplots(len(results_map), 1, figsize=(10, 15), sharex=False)
    if len(results_map) == 1:
        axes = [axes] # Ensure iterable

    for ax, (name, pack) in zip(axes, results_map.items()):
        df = pack['results']
        metrics = pack['metrics']

        # 繪製 Benchmark (Log Scale)
        ax.plot(df.index, df['Benchmark_NAV'], label='Benchmark (Buy & Hold)', color='gray', alpha=0.5, linestyle='--')

        # 繪製 Strategy (Log Scale)
        ax.plot(df.index, df['NAV'], label=f'Purple Line Strategy', color='purple', linewidth=2)

        ax.set_yscale('log')
        ax.set_title(f"{name} Performance\nCAGR: {metrics['CAGR']:.2%} | MaxDD: {metrics['Max_DD']:.2%}")
        ax.legend(loc='upper left')
        ax.grid(True, which="both", ls="-", alpha=0.2)
        ax.set_ylabel('NAV (Log Scale)')

    plt.tight_layout()
    output_path = 'strategy_analysis.jpg'
    plt.savefig(output_path, dpi=150)
    logging.info(f"圖表已儲存至 {output_path}")

if __name__ == "__main__":
    main()
