#!/usr/bin/python3 -u

# Sherwood Crypto Bot
# Version 1.1.0
# Graham Waters

from config import config
from signals import signals
import pandas as pd

class record:
    crypto_ticker = '' # the ticker for the coin on Robinhood.
    quantity = 0.0 # the quantity of the coin that was bought/sold.
    price = 0.0 # the price at which the coin was bought/sold.
    order_id = '' # Robinhood order ID we create and save for this trade
    timestamp = '' # the time the trade was made
    order_type = '' # 'buy' or 'sell'
    def __init__(self,crypto_ticker,quantity,price,order_id,timestamp,order_type):
        """
        Initialize the record class with the crypto ticker, quantity, price, order_id, timestamp, and order_type.
        """
        self.crypto_ticker = crypto_ticker
        self.quantity = float(quantity)
        self.price = float(price)
        self.order_id = order_id
        self.timestamp = timestamp
        self.order_type = order_type
