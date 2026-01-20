import os

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
RAW_DIR = os.path.join(DATA_DIR, 'raw')
PROCESSED_DIR = os.path.join(DATA_DIR, 'processed')

# Strategy Configuration
STRATEGY_CONFIG = {
    'GLD_STRATEGY': {
        'TICKER': 'GLD',
        'RISK_FREE_TICKER': '^IRX',
        'VOLATILITY_TICKER': 'GVZ',  # Gold VIX
        'MA_WINDOW': 200,
        'CAPITAL_RATIO': {
            'CASH': 0.90,
            'OPTION': 0.10
        },
        'OPTION_MATURITY_YEARS': 1.0,
        'STRIKE_METHOD': 'ATM', # or 'OTM_5'
        'START_DATE': '2005-01-01', # GLD started late 2004
    },
    'TLT_STRATEGY': {
        'TICKER': 'TLT',
        'RISK_FREE_TICKER': '^IRX',
        'VOLATILITY_TICKER': 'VXTLT', # TLT VIX
        'MA_WINDOW': 200,
        'CAPITAL_RATIO': {
            'CASH': 0.90,
            'OPTION': 0.10
        },
        'OPTION_MATURITY_YEARS': 1.0,
        'STRIKE_METHOD': 'ATM',
        'START_DATE': '2003-01-01',
    }
}
