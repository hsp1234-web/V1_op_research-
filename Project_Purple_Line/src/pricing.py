import numpy as np
import pandas as pd
from scipy.stats import norm

def calculate_call_price(S, K, T, r, sigma):
    """
    Calculates the price of a European call option using the Black-Scholes-Merton model.
    Fully vectorized for Pandas Series or numpy arrays.

    Parameters:
    -----------
    S : pd.Series or float
        Current stock (underlying) price.
    K : pd.Series or float
        Strike price.
    T : float or pd.Series
        Time to maturity in years (e.g., 1.0 for one year).
    r : pd.Series or float
        Risk-free interest rate (annualized).
    sigma : pd.Series or float
        Annualized volatility.

    Returns:
    --------
    pd.Series or float
        Theoretical call option price.
    """

    # Ensure inputs are appropriate types for vectorization if they are scalars mixed with Series
    # However, numpy broadcasting usually handles this automatically.

    # Avoid division by zero for T near 0
    # If T is a series, we might need to handle it carefully, but assuming T is usually > 0 for this strategy.

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    call_price = (S * norm.cdf(d1)) - (K * np.exp(-r * T) * norm.cdf(d2))

    return call_price
