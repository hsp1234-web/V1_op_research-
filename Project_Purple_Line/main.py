import sys
import os
import logging
from config.settings import STRATEGY_CONFIG
from src.dataloader import DataLoader
from src.pricing import calculate_call_price

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """
    Main entry point for Project Purple Line.
    Currently executes Phase 1 (Data Loading) and Phase 2 (Pricing) verification.
    Future updates will include Phase 3 (Backtesting).
    """
    logging.info("Starting Project Purple Line simulation...")

    # Load Configuration for GLD Strategy
    config = STRATEGY_CONFIG['GLD_STRATEGY']

    # Initialize Data Loader
    loader = DataLoader(start_date=config['START_DATE'])

    try:
        # 1. Fetch and Process Data
        df = loader.fetch_data(
            ticker=config['TICKER'],
            irx_ticker=config['RISK_FREE_TICKER'],
            vol_ticker=config['VOLATILITY_TICKER']
        )
        logging.info(f"Data fetched successfully. Shape: {df.shape}")

        # 2. Calculate Pricing (Verification Step)
        # In the full backtester, this will be dynamic. Here we calculate a daily theoretical price for verification.
        T = config['OPTION_MATURITY_YEARS']

        # Assumption for verification: ATM Call (K = Spot)
        df['Theoretical_Call_Price'] = calculate_call_price(
            S=df['Close'],
            K=df['Close'], # ATM
            T=T,
            r=df['RiskFree_Daily'] * 252, # Annualize for BS
            sigma=df['Sigma_Annual']
        )

        logging.info("Pricing calculation complete. Preview:")
        print(df[['Close', 'RiskFree_Daily', 'Sigma_Annual', 'Theoretical_Call_Price']].tail())

        # Placeholder for Phase 3: Backtester execution
        logging.info("Phase 1 & 2 Complete. Ready for Backtester implementation.")

    except Exception as e:
        logging.error(f"Simulation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
