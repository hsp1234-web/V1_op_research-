import yfinance as yf
import pandas as pd
import numpy as np
import os

class DataLoader:
    def __init__(self, start_date='2000-01-01', end_date=None):
        self.start_date = start_date
        self.end_date = end_date

    def fetch_data(self, ticker, irx_ticker, vol_ticker=None):
        """
        Fetches and aligns data for the strategy.

        Parameters:
        -----------
        ticker : str
            The underlying asset ticker (e.g., 'GLD').
        irx_ticker : str
            The risk-free rate ticker (e.g., '^IRX').
        vol_ticker : str, optional
            The volatility index ticker (e.g., 'GVZ').

        Returns:
        --------
        pd.DataFrame
            Cleaned and aligned DataFrame with columns:
            ['Close', 'RiskFree_Daily', 'Sigma_Annual']
        """
        print(f"Fetching data for {ticker}, {irx_ticker}, {vol_ticker}...")

        # 1. Fetch Underlying
        df_asset = yf.download(ticker, start=self.start_date, end=self.end_date, progress=False, auto_adjust=False)
        if df_asset.empty:
            raise ValueError(f"No data found for {ticker}")

        # yfinance often returns MultiIndex columns if auto_adjust=False is not set properly or just by default in newer versions
        # Let's ensure we get 'Close' properly.
        # If 'Adj Close' is available, use it? Strategy spec says "Close".
        # Usually for backtesting total return, Adj Close is better, but spec says "Close".
        # However, for pure price levels against MA, Close is standard.
        # Let's check columns.

        # Simplify column names if MultiIndex
        if isinstance(df_asset.columns, pd.MultiIndex):
            df_asset.columns = df_asset.columns.get_level_values(0)

        asset_series = df_asset['Close'].rename('Close')

        # 2. Fetch Risk-Free Rate (^IRX)
        df_irx = yf.download(irx_ticker, start=self.start_date, end=self.end_date, progress=False, auto_adjust=False)
        if isinstance(df_irx.columns, pd.MultiIndex):
            df_irx.columns = df_irx.columns.get_level_values(0)

        # IRX is in percent (e.g., 4.5), need to convert to daily float
        # Formula: rate / 100 / 252
        rf_series = df_irx['Close'].rename('RiskFree_Daily')
        rf_series = rf_series / 100.0 / 252.0

        # 3. Fetch or Calculate Volatility
        if vol_ticker:
            df_vol = yf.download(vol_ticker, start=self.start_date, end=self.end_date, progress=False, auto_adjust=False)
            if isinstance(df_vol.columns, pd.MultiIndex):
                df_vol.columns = df_vol.columns.get_level_values(0)

            # VIX indices are annualized percent (e.g., 20.0 => 20% vol)
            # Need to convert to decimal (0.20) for BS model
            vol_series = df_vol['Close'].rename('Sigma_Annual') / 100.0
        else:
            vol_series = pd.Series(dtype=float)

        # 4. Align Data
        # Merge all into one dataframe on Date index
        df_combined = pd.DataFrame(index=asset_series.index)
        df_combined = df_combined.join(asset_series, how='left')
        df_combined = df_combined.join(rf_series, how='left')

        if not vol_series.empty:
            df_combined = df_combined.join(vol_series, how='left')
            # If vol data is missing (e.g. before GVZ existed), we fill later
            df_combined['Sigma_Source'] = 'Implied'
            df_combined.loc[df_combined['Sigma_Annual'].isna(), 'Sigma_Source'] = 'Historical'
        else:
            df_combined['Sigma_Annual'] = np.nan
            df_combined['Sigma_Source'] = 'Historical'

        # 5. Fill Missing Volatility with Historical Volatility
        # "Log Returns rolling std dev (window=20) * sqrt(252)"

        # Calculate Log Returns
        log_returns = np.log(df_combined['Close'] / df_combined['Close'].shift(1))

        # Calculate Rolling Volatility (Annualized)
        hist_vol = log_returns.rolling(window=20).std() * np.sqrt(252)

        # Fill NaN in Sigma_Annual with hist_vol
        df_combined['Sigma_Annual'] = df_combined['Sigma_Annual'].fillna(hist_vol)

        # 6. Fill Missing Risk Free Rate
        # Forward fill first, then maybe backfill or set to 0 if really missing at start
        df_combined['RiskFree_Daily'] = df_combined['RiskFree_Daily'].ffill()

        # If there are still NaNs (e.g. start of dataset), fill with 0 or a small number?
        # Let's assume ffill handles most. If ^IRX starts later than GLD, we might have issues.
        # For now, backfill to ensure we have rates.
        df_combined['RiskFree_Daily'] = df_combined['RiskFree_Daily'].bfill()

        # Drop rows where we still don't have critical data (e.g., first 20 days for hist vol if implied missing)
        df_combined = df_combined.dropna()

        return df_combined

if __name__ == "__main__":
    # Test execution
    loader = DataLoader(start_date='2020-01-01')
    try:
        data = loader.fetch_data('GLD', '^IRX', 'GVZ')
        print("Data Head:")
        print(data.head())
        print("\nData Tail:")
        print(data.tail())
        print(f"\nShape: {data.shape}")

        # Verify Volatility Filling
        print(f"\nMissing Volatility Count: {data['Sigma_Annual'].isna().sum()}")
    except Exception as e:
        print(f"Error: {e}")
