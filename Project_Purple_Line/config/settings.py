import os

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
RAW_DIR = os.path.join(DATA_DIR, 'raw')
PROCESSED_DIR = os.path.join(DATA_DIR, 'processed')

# Strategy Configuration
STRATEGY_CONFIG = {
    'GLD_STRATEGY': {
        'NAME': 'Gold (GLD)',
        'TICKER': 'GLD',
        'RISK_FREE_TICKER': '^IRX',
        'VOLATILITY_TICKER': 'GVZ',  # Gold VIX
        'MA_WINDOW': 200,
        'CAPITAL_RATIO': {'CASH': 0.90, 'OPTION': 0.10},
        'OPTION_MATURITY_YEARS': 1.0,
        'STRIKE_METHOD': 'ATM',
        'START_DATE': '2005-01-01',
    },
    'TLT_STRATEGY': {
        'NAME': 'Treasury 20Y+ (TLT)',
        'TICKER': 'TLT',
        'RISK_FREE_TICKER': '^IRX',
        'VOLATILITY_TICKER': 'VXTLT', # TLT VIX (Often missing, fallback to HV)
        'MA_WINDOW': 200,
        'CAPITAL_RATIO': {'CASH': 0.90, 'OPTION': 0.10},
        'OPTION_MATURITY_YEARS': 1.0,
        'STRIKE_METHOD': 'ATM',
        'START_DATE': '2003-01-01',
    },
    'TWII_STRATEGY': {
        'NAME': 'Taiwan Index (^TWII)',
        'TICKER': '^TWII',
        'RISK_FREE_TICKER': '^IRX', # Using US Rate as proxy for global generic risk-free or cash
        'VOLATILITY_TICKER': None, # Use Historical Volatility
        'MA_WINDOW': 200,
        'CAPITAL_RATIO': {'CASH': 0.90, 'OPTION': 0.10},
        'OPTION_MATURITY_YEARS': 1.0,
        'STRIKE_METHOD': 'ATM',
        'START_DATE': '2000-01-01',
    }
}
