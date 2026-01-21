import time
import random
import requests
import io
import zipfile
import logging
from datetime import timedelta, date

class TaifexDownloader:
    """
    台灣期貨交易所 (TAIFEX) 資料下載器。

    負責從期交所網站下載「每日行情」與「選擇權每日行情」的 ZIP 檔案。
    不依賴 API，而是直接透過 URL Pattern 構建下載連結。
    """

    BASE_URL = "https://www.taifex.com.tw"

    # 偽裝 User-Agent
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/zip,application/octet-stream',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def download_range(self, start_date: date, end_date: date):
        """
        下載指定日期範圍內的期貨與選擇權資料。

        Args:
            start_date (date): 開始日期
            end_date (date): 結束日期

        Yields:
            tuple: (trade_date, futures_csv_content, options_csv_content)
            - trade_date (date): 交易日期
            - futures_csv_content (bytes or None): 期貨 CSV 原始位元組資料
            - options_csv_content (bytes or None): 選擇權 CSV 原始位元組資料
        """
        # 檢查起始日期是否超過 30 天限制
        limit_date = date.today() - timedelta(days=35) # 30天是官方限制，給予少許寬限緩衝
        if start_date < limit_date:
             self.logger.warning(
                 f"注意：您請求的開始日期 {start_date} 超過官方的「每日行情」保留期限 (約30天)。"
                 f"舊資料可能無法透過此方式下載 (會出現 404)。"
                 f"若需歷史資料，請使用「年度行情」下載功能 (本模組尚未實作)。"
             )

        current_date = start_date
        while current_date <= end_date:
            # 略過週末 (週六、週日)
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            self.logger.info(f"開始處理日期: {current_date}")

            # 下載期貨
            futures_content = self._download_file(current_date, "Futures")

            # 下載選擇權
            options_content = self._download_file(current_date, "Options")

            if futures_content or options_content:
                yield current_date, futures_content, options_content
            else:
                self.logger.warning(f"{current_date} 無資料 (可能是假日或下載失敗)。")

            # 隨機延遲，避免 IP 被鎖
            delay = random.uniform(0.5, 1.5)
            time.sleep(delay)

            current_date += timedelta(days=1)

    def _download_file(self, trade_date: date, product_type: str) -> bytes:
        """
        下載單一檔案並解壓縮回傳 CSV 內容。
        """
        year = trade_date.year
        month = f"{trade_date.month:02d}"
        day = f"{trade_date.day:02d}"

        if product_type == "Futures":
            # https://www.taifex.com.tw/file/taifex/Dailydownload/DailydownloadCSV/Daily_{YYYY}_{MM}_{DD}.zip
            url = f"{self.BASE_URL}/file/taifex/Dailydownload/DailydownloadCSV/Daily_{year}_{month}_{day}.zip"
        elif product_type == "Options":
            # https://www.taifex.com.tw/file/taifex/Dailydownload/OptionsDailydownloadCSV/OptionsDaily_{YYYY}_{MM}_{DD}.zip
            url = f"{self.BASE_URL}/file/taifex/Dailydownload/OptionsDailydownloadCSV/OptionsDaily_{year}_{month}_{day}.zip"
        else:
            return None

        try:
            response = requests.get(url, headers=self.HEADERS, timeout=10)

            if response.status_code == 200:
                # 檢查是否為 ZIP 檔案
                if response.content[:4] == b'PK\x03\x04':
                    return self._extract_zip(response.content)
                else:
                    self.logger.warning(f"[{product_type}] {trade_date} 下載內容非 ZIP 格式 (Status: {response.status_code})")
                    return None
            elif response.status_code == 404:
                # 404 很常見 (假日)，不需要 Error Log
                self.logger.debug(f"[{product_type}] {trade_date} 查無資料 (404)。")
                return None
            else:
                self.logger.error(f"[{product_type}] {trade_date} 下載失敗 HTTP {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"[{product_type}] {trade_date} 發生例外: {e}")
            return None

    def _extract_zip(self, zip_bytes: bytes) -> bytes:
        """
        從 ZIP 二進位資料中解壓縮出第一個檔案 (通常只有一個 CSV)。
        """
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                file_list = zf.namelist()
                if not file_list:
                    return None

                # 假設 ZIP 內只有一個 CSV，或是我們只取第一個
                target_file = file_list[0]
                # 某些 ZIP 可能包含目錄，過濾出 .csv
                for f in file_list:
                    if f.lower().endswith('.csv'):
                        target_file = f
                        break

                return zf.read(target_file)
        except zipfile.BadZipFile:
            self.logger.error("ZIP 檔案損毀")
            return None
        except Exception as e:
            self.logger.error(f"解壓縮失敗: {e}")
            return None
