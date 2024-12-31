# FetchCurrentHoldings.py

import Login as fyers  # Assuming Login is your Fyers API module

response = fyers.fyers_active.holdings()

print(response)