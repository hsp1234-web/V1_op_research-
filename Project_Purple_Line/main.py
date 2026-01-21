import sys
import os
import logging
import argparse
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from datetime import datetime, date
from config.settings import STRATEGY_CONFIG
from src.dataloader import DataLoader
from src.pricing import calculate_call_price
from src.backtester import Backtester

# 引入 ETL 模組
from src.fetcher.taifex import TaifexDownloader
from src.fetcher.parser import TaifexParser
from src.database import Database

# 設定日誌記錄 (Configure Logging)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_taifex_etl(start_date_str, end_date_str):
    """
    執行台灣期交所 (TAIFEX) 的 ETL 流程。
    """
    logging.info(f"啟動 TAIFEX ETL 任務: {start_date_str} 至 {end_date_str}")

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        logging.error("日期格式錯誤，請使用 YYYY-MM-DD")
        return

    downloader = TaifexDownloader()
    parser = TaifexParser()
    db = Database()

    count_futures = 0
    count_options = 0

    # 下載並處理
    for trade_date, fut_bytes, opt_bytes in downloader.download_range(start_date, end_date):
        # 處理期貨
        if fut_bytes:
            df_fut = parser.parse_futures(fut_bytes)
            if not df_fut.empty:
                db.upsert_futures(df_fut)
                count_futures += len(df_fut)

        # 處理選擇權
        if opt_bytes:
            df_opt = parser.parse_options(opt_bytes)
            if not df_opt.empty:
                db.upsert_options(df_opt)
                count_options += len(df_opt)

    logging.info(f"ETL 任務完成。總計處理期貨筆數: {count_futures}, 選擇權筆數: {count_options}")

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
    parser = argparse.ArgumentParser(description="Project Purple Line - 策略回測與資料 ETL")

    # 子命令: ETL
    parser.add_argument('--etl', action='store_true', help='執行 TAIFEX ETL 資料下載與清洗')
    parser.add_argument('--start', type=str, default='2024-01-01', help='ETL 開始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default=datetime.today().strftime('%Y-%m-%d'), help='ETL 結束日期 (YYYY-MM-DD)')

    args = parser.parse_args()

    if args.etl:
        run_taifex_etl(args.start, args.end)
        return

    # 若無 --etl 參數，則執行預設的回測流程
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
