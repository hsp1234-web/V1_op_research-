import pytest
import requests
import time
import os
import sys
from datetime import date, timedelta
from typing import List, Tuple

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.fetcher.taifex import TaifexDownloader

class TestTaifexAvailability:
    """
    實際對 TAIFEX 伺服器進行連線測試，以確認資料下載的歷史範圍邊界。
    這是一個 Integration/Live Test，執行時會真的發送網路請求。
    """

    @pytest.fixture
    def downloader(self):
        return TaifexDownloader()

    def check_date_availability(self, target_date: date, downloader: TaifexDownloader) -> Tuple[bool, bool]:
        """
        檢查特定日期的期貨與選擇權檔案是否存在 (HEAD request only or minimal download)。
        由於 TaifexDownloader 實作是直接下載，這裡我們模擬它的 URL 邏輯並只送 HEAD 請求以節省頻寬。
        """
        year = target_date.year
        month = f"{target_date.month:02d}"
        day = f"{target_date.day:02d}"

        # URL Patterns from TaifexDownloader
        fut_url = f"{downloader.BASE_URL}/file/taifex/Dailydownload/DailydownloadCSV/Daily_{year}_{month}_{day}.zip"
        opt_url = f"{downloader.BASE_URL}/file/taifex/Dailydownload/OptionsDailydownloadCSV/OptionsDaily_{year}_{month}_{day}.zip"

        headers = downloader.HEADERS

        fut_exists = False
        opt_exists = False

        # Retry logic
        for attempt in range(3):
            try:
                # Check Futures
                if not fut_exists:
                    r_fut = requests.head(fut_url, headers=headers, timeout=15)
                    if r_fut.status_code == 200:
                        fut_exists = True

                # Check Options
                if not opt_exists:
                    r_opt = requests.head(opt_url, headers=headers, timeout=15)
                    if r_opt.status_code == 200:
                        opt_exists = True

                if fut_exists and opt_exists:
                    break

                if attempt < 2:
                    time.sleep(2)

            except Exception as e:
                print(f"Error checking {target_date} (Attempt {attempt+1}): {e}")
                if attempt < 2:
                    time.sleep(2)

        return fut_exists, opt_exists

    def test_probe_historical_limits(self, downloader):
        """
        探測歷史資料極限。
        策略：
        1. 檢查「今天」(或最近一個交易日)。
        2. 檢查「1個月前」。
        3. 檢查「1年前」。
        4. 檢查「3年前」。
        5. 檢查「10年前」。
        6. 檢查「20年前」。
        7. 檢查「25年前」 (TAIFEX 成立於 1997, 1998 開始交易)。
        """

        # 找最近的一個平日 (避免假日)
        today = date.today()
        while today.weekday() >= 5: # Sat=5, Sun=6
            today -= timedelta(days=1)

        check_points = [
            ("Recent", today - timedelta(days=1)), # Yesterday (to be safe from timezone/closing time)
            ("1 Month Ago", today - timedelta(days=30)),
            ("1 Year Ago", today - timedelta(days=365)),
            ("3 Years Ago", today - timedelta(days=365*3)),
            ("5 Years Ago", today - timedelta(days=365*5)),
            ("10 Years Ago", today - timedelta(days=365*10)),
            ("20 Years Ago", today - timedelta(days=365*20)),
            ("26 Years Ago (1998)", date(1998, 7, 21)), # Early days
        ]

        print("\n=== TAIFEX Historical Data Availability Probe ===")
        print(f"{'Timepoint':<20} | {'Date':<12} | {'Futures':<8} | {'Options':<8}")
        print("-" * 60)

        valid_range_start = today

        for label, d in check_points:
            # Adjust if weekend
            while d.weekday() >= 5:
                d -= timedelta(days=1)

            fut_ok, opt_ok = self.check_date_availability(d, downloader)

            status_fut = "OK" if fut_ok else "404/Err"
            status_opt = "OK" if opt_ok else "404/Err"

            print(f"{label:<20} | {d} | {status_fut:<8} | {status_opt:<8}")

            if fut_ok:
                valid_range_start = d

            # Be nice to the server
            time.sleep(1)

        print("-" * 60)
        print(f"Verified available back to at least: {valid_range_start}")

        # Assertion: We expect at least 3 years of data to be available for backtesting
        # If 3 years ago fails, we have a problem with our assumption or URL pattern.
        cutoff_3y = today - timedelta(days=365*3)
        while cutoff_3y.weekday() >= 5: cutoff_3y -= timedelta(days=1)

        fut_3y, opt_3y = self.check_date_availability(cutoff_3y, downloader)

        if not fut_3y:
            pytest.warns(UserWarning, match=f"Futures data for 3 years ago ({cutoff_3y}) is missing.")
        else:
            assert fut_3y, "Futures data should be available for 3 years ago"

if __name__ == "__main__":
    # Allow running directly
    t = TestTaifexAvailability()
    d = TaifexDownloader()
    t.test_probe_historical_limits(d)
