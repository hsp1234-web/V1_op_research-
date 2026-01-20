import sys
import os
import logging
import matplotlib.pyplot as plt
import pandas as pd
from config.settings import STRATEGY_CONFIG
from src.dataloader import DataLoader
from src.pricing import calculate_call_price
from src.backtester import Backtester

# 設定日誌記錄 (Configure Logging)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """
    Project Purple Line 主程式入口點。
    執行資料載入、選擇權定價計算以及策略回測。
    """
    logging.info("開始執行 Project Purple Line 模擬...")

    # 載入 GLD 策略設定 (Load Configuration for GLD Strategy)
    config = STRATEGY_CONFIG['GLD_STRATEGY']

    # 初始化資料載入器 (Initialize Data Loader)
    loader = DataLoader(start_date=config['START_DATE'])

    try:
        # 1. 獲取與處理資料 (Fetch and Process Data)
        df = loader.fetch_data(
            ticker=config['TICKER'],
            irx_ticker=config['RISK_FREE_TICKER'],
            vol_ticker=config['VOLATILITY_TICKER']
        )
        logging.info(f"資料獲取成功。資料形狀: {df.shape}")

        # 2. 計算選擇權定價 (Calculate Pricing)
        # 這一步計算理論上的買權價格，作為回測的輸入
        T = config['OPTION_MATURITY_YEARS']

        # 假設: ATM Call (履約價 K = 當前股價 Spot)
        # 注意: 這裡的 r 需要年化 (RiskFree_Daily * 252)
        df['Theoretical_Call_Price'] = calculate_call_price(
            S=df['Close'],
            K=df['Close'], # ATM
            T=T,
            r=df['RiskFree_Daily'] * 252,
            sigma=df['Sigma_Annual']
        )

        logging.info("選擇權定價計算完成。")

        # 3. 執行策略回測 (Execute Strategy)
        tester = Backtester(df, config)
        results_pack = tester.run_backtest()
        results = results_pack['results']
        metrics = results_pack['metrics']

        # 4. 輸出結果 (Output Results)
        print("-" * 40)
        print("策略回測結果 (Strategy Performance Metrics)")
        print("-" * 40)
        print(f"最終淨值 (Final NAV): {metrics['Final_NAV']:.2f}")
        print(f"年化報酬率 (CAGR): {metrics['CAGR']:.2%}")
        print(f"最大回撤 (Max Drawdown): {metrics['Max_DD']:.2%}")
        print("-" * 40)

        # 5. 繪製圖表 (Plotting)
        # 繪製：標的物走勢 (Log Scale) vs 策略淨值 (Log Scale)
        logging.info("正在產生績效圖表...")

        plt.figure(figsize=(12, 8))

        # 繪製 Benchmark (買入持有)
        plt.plot(results.index, results['Benchmark_NAV'], label='Benchmark (Buy & Hold)', color='gray', alpha=0.6)

        # 繪製策略淨值 (紫色線)
        plt.plot(results.index, results['NAV'], label='Purple Line Strategy', color='purple', linewidth=2)

        plt.yscale('log') # 設定 Y 軸為對數座標
        plt.title('Strategy Performance vs Benchmark (Log Scale)')
        plt.xlabel('Date')
        plt.ylabel('NAV (Log Scale)')
        plt.legend()
        plt.grid(True, which="both", ls="-", alpha=0.2)

        # 儲存圖表
        output_path = 'strategy_performance.png'
        plt.savefig(output_path)
        logging.info(f"圖表已儲存至 {output_path}")

        # 關閉圖表以釋放記憶體
        plt.close()

    except Exception as e:
        logging.error(f"模擬失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
