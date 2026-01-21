import sqlite3
import pandas as pd
import logging
import os
from sqlalchemy import create_engine, text

class Database:
    """
    SQLite 資料庫管理器 (輕量化設計)。

    Schema:
    1. futures_daily: 期貨日行情
    2. options_daily: 選擇權日行情
    """

    def __init__(self, db_path='data/taifex.db'):
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path

        # 確保資料夾存在
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        # 使用 SQLAlchemy 建立 Engine
        self.engine = create_engine(f'sqlite:///{db_path}')
        self._init_schema()

    def _init_schema(self):
        """初始化資料表結構"""
        try:
            with self.engine.connect() as conn:
                # Table 1: futures_daily
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS futures_daily (
                        trade_date DATE NOT NULL,
                        symbol TEXT NOT NULL,
                        expiry TEXT NOT NULL,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume INTEGER,
                        oi INTEGER,
                        PRIMARY KEY (trade_date, symbol, expiry)
                    );
                """))

                # Table 2: options_daily
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS options_daily (
                        trade_date DATE NOT NULL,
                        symbol TEXT NOT NULL,
                        expiry TEXT NOT NULL,
                        strike REAL NOT NULL,
                        call_put TEXT NOT NULL,
                        close REAL,
                        oi INTEGER,
                        implied_vol REAL,
                        PRIMARY KEY (trade_date, symbol, expiry, strike, call_put)
                    );
                """))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Schema 初始化失敗: {e}")

    def upsert_futures(self, df: pd.DataFrame):
        """
        更新或插入期貨資料 (Upsert)。

        由於 SQLite 的 UPSERT 語法較新，這裡使用先刪後插或 Replace 策略。
        但在大量資料下，pandas to_sql 的 'append' 較快，若要避免重複鍵錯誤，
        可以先檢查或用 INSERT OR REPLACE。

        這裡採用: pandas to_sql(temp) -> SQL INSERT OR REPLACE -> Drop temp
        """
        if df.empty:
            return

        try:
            with self.engine.begin() as conn: # Transaction
                # 寫入暫存表
                df.to_sql('temp_futures', conn, if_exists='replace', index=False)

                # 執行 Upsert (SQLite syntax)
                sql = """
                    INSERT OR REPLACE INTO futures_daily (trade_date, symbol, expiry, open, high, low, close, volume, oi)
                    SELECT trade_date, symbol, expiry, open, high, low, close, volume, oi
                    FROM temp_futures;
                """
                conn.execute(text(sql))
                conn.execute(text("DROP TABLE temp_futures"))

            self.logger.info(f"Upserted {len(df)} futures records.")
        except Exception as e:
            self.logger.error(f"期貨寫入失敗: {e}")

    def upsert_options(self, df: pd.DataFrame):
        """
        更新或插入選擇權資料。
        """
        if df.empty:
            return

        try:
            with self.engine.begin() as conn:
                df.to_sql('temp_options', conn, if_exists='replace', index=False)

                # 處理 implied_vol 欄位是否存在
                cols = "trade_date, symbol, expiry, strike, call_put, close, oi"
                select_cols = cols
                if 'implied_vol' in df.columns:
                    cols += ", implied_vol"
                    select_cols += ", implied_vol"
                else:
                    cols += ", implied_vol"
                    select_cols += ", NULL" # 若無 IV，補 NULL

                sql = f"""
                    INSERT OR REPLACE INTO options_daily ({cols})
                    SELECT {select_cols}
                    FROM temp_options;
                """
                conn.execute(text(sql))
                conn.execute(text("DROP TABLE temp_options"))

            self.logger.info(f"Upserted {len(df)} options records.")
        except Exception as e:
            self.logger.error(f"選擇權寫入失敗: {e}")
