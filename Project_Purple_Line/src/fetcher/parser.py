import pandas as pd
import io
import logging
import numpy as np

class TaifexParser:
    """
    台灣期貨交易所 (TAIFEX) CSV 解析器。

    負責將原始的 Big5/CP950 編碼 CSV 位元組資料，轉換為清洗後的 DataFrame。
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def parse_futures(self, csv_bytes: bytes) -> pd.DataFrame:
        """
        解析期貨每日行情 CSV。

        過濾條件:
        - Symbol: 'TX' (大台), 'MTX' (小台)
        - Expiry: 必須是近月 (這裡只做初步標記，後續處理近月判斷)
        """
        if not csv_bytes:
            return pd.DataFrame()

        try:
            # 讀取 CSV，指定 encoding='cp950'
            # header=0 通常是第一行，但期交所檔案可能有標題行或空白，需注意
            # 通常格式: 交易日期, 契約, 到期月份(週別), 開盤價, 最高價, 最低價, 收盤價, 漲跌價, 漲跌%, 成交量, 結算價, 未平倉餘額, ...
            df = pd.read_csv(io.BytesIO(csv_bytes), encoding='cp950', dayfirst=False)

            # 清洗欄位名稱 (去除空白)
            df.columns = [c.strip() for c in df.columns]

            # 欄位映射
            rename_map = {
                '交易日期': 'Date',
                '契約': 'Symbol', # 部分舊檔可能叫 '契約代碼'
                '契約代碼': 'Symbol',
                '到期月份(週別)': 'Expiry',
                '開盤價': 'Open',
                '最高價': 'High',
                '最低價': 'Low',
                '收盤價': 'Close',
                '成交量': 'Volume',
                '未平倉餘額': 'OI'
            }
            df.rename(columns=rename_map, inplace=True)

            # 檢查必要欄位
            required_cols = ['Date', 'Symbol', 'Expiry', 'Open', 'High', 'Low', 'Close', 'Volume', 'OI']
            # 有些檔案可能沒有 OI (早期資料)，如果沒有，補 0
            for col in required_cols:
                if col not in df.columns:
                    if col == 'OI':
                        df[col] = 0
                    else:
                        # 缺少關鍵欄位，可能讀錯或格式變更
                        self.logger.warning(f"期貨 CSV 缺少欄位: {col}")
                        return pd.DataFrame()

            # 過濾 Symbol (只留 TX, MTX)
            # 需注意 Symbol 可能有空白
            df['Symbol'] = df['Symbol'].astype(str).str.strip()
            df = df[df['Symbol'].isin(['TX', 'MTX'])].copy()

            if df.empty:
                return pd.DataFrame()

            # 數值清洗
            # 1. 去除千分位逗號
            # 2. 處理 '-' (無交易) 為 NaN -> 0 或 ffill (這裡先轉 NaN)
            numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume', 'OI']
            for col in numeric_cols:
                df[col] = df[col].astype(str).str.replace(',', '').str.strip()
                df[col] = pd.to_numeric(df[col], errors='coerce') # '-' 會變成 NaN

            # 填補 NaN (若無成交，Open/High/Low/Close 可能為 NaN，通常可以填 0 或 drop)
            # 策略需要連續價格，這裡暫時 dropna，因為如果是主力合約通常會有成交
            df = df.dropna(subset=['Close'])

            # Expiry 格式清洗 (需保留原始字串，因為可能有 '202401' 或 '202401W1')
            df['Expiry'] = df['Expiry'].astype(str).str.strip()

            # Date 格式清洗 (YYYY/MM/DD -> YYYY-MM-DD)
            # 假設原始是 YYYY/MM/DD
            df['Date'] = pd.to_datetime(df['Date'].astype(str), errors='coerce').dt.date

            return df[required_cols]

        except Exception as e:
            self.logger.error(f"期貨解析失敗: {e}")
            return pd.DataFrame()

    def parse_options(self, csv_bytes: bytes) -> pd.DataFrame:
        """
        解析選擇權每日行情 CSV。

        過濾條件:
        - Symbol: 'TXO' (台指選)
        """
        if not csv_bytes:
            return pd.DataFrame()

        try:
            df = pd.read_csv(io.BytesIO(csv_bytes), encoding='cp950')
            df.columns = [c.strip() for c in df.columns]

            rename_map = {
                '交易日期': 'Date',
                '契約': 'Symbol',
                '契約代碼': 'Symbol',
                '到期月份(週別)': 'Expiry',
                '履約價格': 'Strike',
                '買賣權代碼': 'CallPut',
                '收盤價': 'Close', # 權利金
                '未平倉餘額': 'OI',
                '波動率': 'ImpliedVol' # 選擇權檔可能有隱含波動率
            }
            df.rename(columns=rename_map, inplace=True)

            required_cols = ['Date', 'Symbol', 'Expiry', 'Strike', 'CallPut', 'Close', 'OI']
            for col in required_cols:
                if col not in df.columns:
                    if col == 'OI': df[col] = 0
                    else: return pd.DataFrame()

            # 過濾 Symbol
            df['Symbol'] = df['Symbol'].astype(str).str.strip()
            df = df[df['Symbol'] == 'TXO'].copy()

            if df.empty: return pd.DataFrame()

            # 數值清洗
            numeric_cols = ['Strike', 'Close', 'OI']
            if 'ImpliedVol' in df.columns: numeric_cols.append('ImpliedVol')

            for col in numeric_cols:
                df[col] = df[col].astype(str).str.replace(',', '').str.strip()
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df = df.dropna(subset=['Close'])

            df['Expiry'] = df['Expiry'].astype(str).str.strip()
            df['CallPut'] = df['CallPut'].astype(str).str.strip().str.upper() # 'C' or 'P'
            df['Date'] = pd.to_datetime(df['Date'].astype(str), errors='coerce').dt.date

            # 回傳需要的欄位
            final_cols = required_cols
            if 'ImpliedVol' in df.columns:
                final_cols.append('ImpliedVol')

            return df[final_cols]

        except Exception as e:
            self.logger.error(f"選擇權解析失敗: {e}")
            return pd.DataFrame()
