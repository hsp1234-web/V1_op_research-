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
        'VOLATILITY_TICKER': 'GVZ',
        'MA_WINDOW': 200,
        'CAPITAL_RATIO': {'CASH': 0.90, 'OPTION': 0.10},
        'OPTION_MATURITY_YEARS': 1.0,
        'STRIKE_METHOD': 'ATM', # Can change to 'OTM_5' later
        'START_DATE': '2005-01-01',
    },
    'TLT_STRATEGY': {
        'NAME': 'Treasury 20Y+ (TLT)',
        'TICKER': 'TLT',
        'RISK_FREE_TICKER': '^IRX',
        'VOLATILITY_TICKER': 'VXTLT',
        'MA_WINDOW': 200,
        'CAPITAL_RATIO': {'CASH': 0.90, 'OPTION': 0.10},
        'OPTION_MATURITY_YEARS': 1.0,
        'STRIKE_METHOD': 'ATM',
        'START_DATE': '2003-01-01',
    },
    'TWII_STRATEGY': {
        'NAME': 'Taiwan Index (^TWII)',
        'TICKER': '^TWII',
        'RISK_FREE_TICKER': '^IRX',
        'VOLATILITY_TICKER': None,
        'MA_WINDOW': 200,
        'CAPITAL_RATIO': {'CASH': 0.90, 'OPTION': 0.10},
        'OPTION_MATURITY_YEARS': 1.0,
        'STRIKE_METHOD': 'ATM',
        'START_DATE': '2000-01-01',
    }
}
