import yfinance as yf
import pandas as pd
import numpy as np
import logging
import time

class DataLoader:
    def __init__(self, start_date='2000-01-01', end_date=None):
        self.start_date = start_date
        self.end_date = end_date
        self.logger = logging.getLogger(__name__)

    def _download_with_retry(self, ticker, max_retries=3):
        """Helper to download with retries."""
        for i in range(max_retries):
            try:
                df = yf.download(ticker, start=self.start_date, end=self.end_date, progress=False, auto_adjust=False)
                if not df.empty:
                    # Simplify MultiIndex columns if present
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    return df
            except Exception as e:
                self.logger.warning(f"Attempt {i+1} failed for {ticker}: {e}")
                time.sleep(1)
        self.logger.error(f"Failed to download {ticker} after {max_retries} attempts.")
        return pd.DataFrame()

    def fetch_data(self, ticker, irx_ticker, vol_ticker=None):
        """
        Fetches and aligns data for the strategy.

        邏輯改進:
        1. 強健的下載重試機制。
        2. 當隱含波動率 (IV) 缺失時，自動使用歷史波動率 (HV) 填補。
        3. 確保資料對齊。
        """
        self.logger.info(f"開始下載資料: {ticker}, {irx_ticker}, {vol_ticker if vol_ticker else 'N/A'}")

        # 1. Fetch Underlying Asset
        df_asset = self._download_with_retry(ticker)
        if df_asset.empty:
            raise ValueError(f"No data found for {ticker}")

        asset_series = df_asset['Close'].rename('Close')

        # 2. Fetch Risk-Free Rate
        df_irx = self._download_with_retry(irx_ticker)
        if df_irx.empty:
            self.logger.warning(f"Risk-free rate {irx_ticker} download failed. Using 0% as fallback temporarily.")
            rf_series = pd.Series(0.0, index=asset_series.index, name='RiskFree_Daily')
        else:
            # IRX is percentage (e.g. 4.5 -> 0.045 -> daily)
            rf_series = df_irx['Close'].rename('RiskFree_Daily')
            rf_series = rf_series / 100.0 / 252.0

        # 3. Fetch or Calculate Volatility
        vol_series = pd.Series(dtype=float, name='Sigma_Annual')
        vol_source_name = 'Historical'

        if vol_ticker:
            df_vol = self._download_with_retry(vol_ticker)
            if not df_vol.empty:
                # VIX indices are in percent (e.g. 20.0 -> 0.20)
                vol_series = df_vol['Close'].rename('Sigma_Annual') / 100.0
                vol_source_name = 'Implied'
            else:
                self.logger.warning(f"Volatility ticker {vol_ticker} returned empty data. Switching to Historical Volatility.")

        # 4. Align Data
        df_combined = pd.DataFrame(index=asset_series.index)
        df_combined = df_combined.join(asset_series, how='left')
        df_combined = df_combined.join(rf_series, how='left')

        # Join Volatility (could be empty or partial)
        df_combined = df_combined.join(vol_series, how='left')
        df_combined['Sigma_Source'] = vol_source_name

        # 5. Fill Missing Volatility with Historical Volatility
        # Calculate Log Returns
        log_returns = np.log(df_combined['Close'] / df_combined['Close'].shift(1))

        # Calculate 20-day Historical Volatility (Annualized)
        hist_vol = log_returns.rolling(window=20).std() * np.sqrt(252)

        # Fill NaN in Sigma_Annual with hist_vol
        # This covers two cases:
        # a) Vol ticker was invalid/empty (all NaNs)
        # b) Vol ticker has shorter history than asset

        missing_vol_mask = df_combined['Sigma_Annual'].isna()
        if missing_vol_mask.any():
            self.logger.info(f"Filling {missing_vol_mask.sum()} missing volatility days with Historical Volatility.")
            df_combined.loc[missing_vol_mask, 'Sigma_Source'] = 'Historical'
            df_combined.loc[missing_vol_mask, 'Sigma_Annual'] = hist_vol[missing_vol_mask]

        # 6. Final Cleanup
        # Risk Free Rate filling
        df_combined['RiskFree_Daily'] = df_combined['RiskFree_Daily'].ffill().bfill().fillna(0.0)

        # Drop initial rows where volatility calculation is impossible (first 20 days)
        df_combined = df_combined.dropna()

        self.logger.info(f"Data aligned successfully. Shape: {df_combined.shape}")
        return df_combined
