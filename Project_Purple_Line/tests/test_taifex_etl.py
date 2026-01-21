import unittest
from unittest.mock import patch, MagicMock
import io
import zipfile
import pandas as pd
from datetime import date
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.fetcher.taifex import TaifexDownloader
from src.fetcher.parser import TaifexParser
from src.database import Database
from sqlalchemy import text

class TestTaifexETL(unittest.TestCase):

    def create_mock_zip(self, filename, content):
        """Helper to create a zip bytes object containing a file."""
        mem_zip = io.BytesIO()
        with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(filename, content)
        return mem_zip.getvalue()

    @patch('src.fetcher.taifex.requests.get')
    def test_downloader(self, mock_get):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Mock CSV content inside ZIP
        csv_content = "交易日期,契約,到期月份(週別),開盤價,最高價,最低價,收盤價,漲跌價,漲跌%,成交量,結算價,未平倉餘額\n2024/01/01,TX,202401,17000,17100,16900,17050,50,0.3%,1000,17050,50000"
        zip_bytes = self.create_mock_zip("Daily_2024_01_01.csv", csv_content.encode('cp950'))
        mock_response.content = zip_bytes
        mock_get.return_value = mock_response

        downloader = TaifexDownloader()
        # Mock time.sleep to speed up test
        with patch('time.sleep', return_value=None):
            results = list(downloader.download_range(date(2024, 1, 1), date(2024, 1, 1)))

        self.assertEqual(len(results), 1)
        trade_date, fut_content, opt_content = results[0]
        self.assertEqual(trade_date, date(2024, 1, 1))
        # Since we mocked both calls with same response (default mock behavior if not side_effect used properly for different calls)
        # But wait, download_range calls _download_file twice.
        # If mock_get returns same response, both will get the same content.
        # For simplicity, let's assume both calls succeed with same content.
        self.assertIsNotNone(fut_content)
        self.assertIsNotNone(opt_content)

    def test_parser_futures(self):
        parser = TaifexParser()
        # Mock Futures CSV (CP950 encoded)
        # Note: '契約' is 'Symbol', '到期月份(週別)' is 'Expiry', etc.
        # Ensure numbers with commas are quoted
        csv_text = (
            "交易日期,契約,到期月份(週別),開盤價,最高價,最低價,收盤價,漲跌價,漲跌%,成交量,結算價,未平倉餘額\n"
            "2024/01/01,TX ,202401 ,17000,17100,16900,17050,50,0.3%,\"10,000\",17050,50000\n"
            "2024/01/01,MTX,202401 ,17000,17100,16900,17050,50,0.3%,\"5,000\",17050,20000\n"
            "2024/01/01,TE ,202401 ,17000,17100,16900,17050,50,0.3%,100,17050,500\n" # Should be filtered out
        )
        csv_bytes = csv_text.encode('cp950')

        df = parser.parse_futures(csv_bytes)

        self.assertEqual(len(df), 2) # Only TX and MTX
        self.assertTrue('TX' in df['Symbol'].values)
        self.assertTrue('MTX' in df['Symbol'].values)
        self.assertFalse('TE' in df['Symbol'].values)
        self.assertEqual(df.iloc[0]['Volume'], 10000) # Check comma removal
        self.assertEqual(df.iloc[0]['Date'], date(2024, 1, 1))

    def test_parser_options(self):
        parser = TaifexParser()
        # Mock Options CSV
        csv_text = (
            "交易日期,契約,到期月份(週別),履約價格,買賣權代碼,收盤價,未平倉餘額,波動率\n"
            "2024/01/01,TXO,202401 ,17000,C,150,10000, -\n" # IV is '-'
            "2024/01/01,TXO,202401 ,17000,P,100,12000, 15.5\n"
            "2024/01/01,TEO,202401 ,17000,C,150,100, -\n" # Should be filtered out
        )
        csv_bytes = csv_text.encode('cp950')

        df = parser.parse_options(csv_bytes)

        self.assertEqual(len(df), 2) # Only TXO
        self.assertEqual(df.iloc[0]['CallPut'], 'C')
        self.assertEqual(df.iloc[1]['ImpliedVol'], 15.5)
        self.assertTrue(pd.isna(df.iloc[0]['ImpliedVol'])) # '-' becomes NaN

    def test_database(self):
        # Use in-memory DB for testing
        db = Database(db_path=':memory:') # Special path for in-memory SQLite
        # Wait, SQLAlchemy format for memory is sqlite:///:memory: but create_engine handles filepath by prepending sqlite:///
        # My implementation: create_engine(f'sqlite:///{db_path}')
        # So if I pass ':memory:', it becomes 'sqlite:///:memory:'. Correct.

        # Create dummy data
        df_fut = pd.DataFrame({
            'trade_date': [date(2024, 1, 1)],
            'symbol': ['TX'],
            'expiry': ['202401'],
            'open': [17000],
            'high': [17100],
            'low': [16900],
            'close': [17050],
            'volume': [1000],
            'oi': [50000]
        })

        db.upsert_futures(df_fut)

        # Verify insertion
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM futures_daily")).fetchall()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0][1], 'TX')

        # Test Upsert (Update)
        df_fut_update = df_fut.copy()
        df_fut_update['close'] = 17060
        db.upsert_futures(df_fut_update)

        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM futures_daily")).fetchall()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0][6], 17060) # Close price updated

if __name__ == '__main__':
    unittest.main()
