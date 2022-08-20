#!/usr/bin/python3 -u

# Sherwood Crypto Bot
# Version 1.1.0
# Graham Waters

from math import floor
import pickle
import time, random
from config import config

from tradingview_config import (
    exchanges_dict,
)  # this contains the exchange names for each currency pair.
import pandas as pd
from tradingview_ta import TA_Handler, Interval, Exchange
import tradingview_ta
from robin_stocks import *  # get all functions from robin_stocks
import robin_stocks.robinhood as r
import os.path as path


simulate_pausing = False  # set to True to simulate pausing the bot for debugging purposes.

class signals:  #
    def __init__(self):  #
        self.rsi_buy = False
        self.rsi_sell = False
        self.above_bought = False  # is current price above where we bought the coin?
        self.current_rsi = 50  # current rsi value
    def rsi_signaller(self, current_rsi):
        # buy when RSI is below threshold for a 'buy'
        if float(current_rsi) < float(config["rsi_threshold"]["buy"]):
            return 1  # signal a buy when RSI is below threshold
        elif float(current_rsi) > float(config["rsi_threshold"]["sell"]):
            return -1  # signal a sell when RSI is above threshold
        else:  # signal a neutral when RSI is in between thresholds
            return 0  # do not buy or sell
    def trading_view_suggestion(self, ticker):
        # Trading View suggestions for buying/selling/holding crypto
        """
        Takes in a ticker and returns a 1,-1, or 0 indicating whether or not to buy or sell the ticker. This is based on tradingview_ta data. The exchange this function utilizes is not Kraken. It is Coinbase.

        Args:
            ticker (str): the ticker of the crypto to check.
        """
        assert type(ticker) == str
        pos_df = pd.DataFrame()  # hold the ta data for all of the tickers
        output = TA_Handler(
            symbol=f"{ticker.upper()}USD",
            screener="Crypto",
            exchange="COINBASE",
            interval=Interval.INTERVAL_15_MINUTES,
        )
        output_analysis = output.get_analysis()
        dict2 = (
            output_analysis.summary
        )  # get the summary dictionary. NOTE: Also available is the output_analysis.technical_indicators, for further analysis.

        buyScore = float(dict2["BUY"])
        sellScore = float(dict2["SELL"])
        neutralScore = float(dict2["NEUTRAL"])

        if (
            buyScore > sellScore and buyScore > neutralScore
        ):  # if more suggestions for buy than sell and neutral.
            return 1  # buy
        elif (
            sellScore > buyScore and sellScore > neutralScore
        ):  # if more suggestions for sell than buy and neutral.
            return -1
        else:  #
            return 0  # do not buy but don't sell either. This means that the ticker is neutral.
    def above_bought_signaller(self, current_price):
        # buy when price is above where we bought the coin
        if float(current_price) > float(self.above_bought):
            return 1  # signal a buy when price is above where we bought the coin
        else:  # signal a neutral when price is below where we bought the coin
            return 0

class record:
    crypto_ticker = ""  # the ticker for the coin on Robinhood.
    quantity = 0.0  # the quantity of the coin that was bought/sold.
    price = 0.0  # the price at which the coin was bought/sold.
    order_id = ""  # Robinhood order ID we create and save for this trade
    timestamp = ""  # the time the trade was made
    order_type = ""  # 'buy' or 'sell'

    def __init__(self, crypto_ticker, quantity, price, order_id, timestamp, order_type):
        """
        Initialize the record class with the crypto ticker, quantity, price, order_id, timestamp, and order_type.
        """
        self.crypto_ticker = crypto_ticker
        self.quantity = float(quantity)
        self.price = float(price)
        self.order_id = order_id
        self.timestamp = timestamp
        self.order_type = order_type


class trader:
    default_config = {
        "username": "",
        "password": "",
        "trades_enabled": False,
        "debug_enabled": False,
        "ticker_list": {"XETHZUSD": "ETH"},
        "trade_strategies": {"buy": "sma_rsi_threshold", "sell": "above_buy"},
        "buy_below_moving_average": 0.0075,
        "profit_percentage": 0.01,
        "buy_amount_per_trade": 0,
        "moving_average_periods": {
            "sma_fast": 48,  # 12 data points per hour, 4 hours worth of data
            "sma_slow": 192,
            "macd_fast": 48,
            "macd_slow": 104,  # MACD 12/26 -> 48/104
            "macd_signal": 28,
        },
        "rsi_period": 48,
        "rsi_threshold": 39.5,
        "reserve": 0.0,
        "stop_loss_threshold": 0.3,
        "minutes_between_updates": 5,
        "save_charts": True,
        "max_data_rows": 10000,
    }
    data = pd.DataFrame()
    orders = {}
    min_share_increments = {}  # the smallest increment of a coin you can buy/sell
    min_price_increments = (
        {}
    )  # the smallest fraction of a dollar you can buy/sell a coin with
    min_consecutive_samples = 0
    available_cash = 0
    is_trading_locked = False  # used to determine if we have had a break in our incoming price data and hold buys if so
    is_new_order_added = False  # the bot performs certain cleanup operations after new orders are sent out
    #!signal = signals()

    def __init__(self):
        # Set Pandas to output all columns in the dataframe
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 300)

        print("-- Configuration ------------------------")
        for c in self.default_config:
            isDefined = config.get(c)
            if not isDefined:
                config[c] = self.default_config[c]

        if not config["username"] or not config["password"]:
            print("RobinHood credentials not found in config file. Aborting.")
            exit()

        if config["rsi_period"] > config["moving_average_periods"]["sma_fast"]:
            self.min_consecutive_samples = config["rsi_period"]
        else:
            self.min_consecutive_samples = config["moving_average_periods"]["sma_fast"]

        for a_key, a_value in config.items():
            if a_key == "username" or a_key == "password":
                continue

            print(a_key.replace("_", " ").capitalize(), ": ", a_value, sep="")

        print("-- End Configuration --------------------")

        if path.exists("orders.pickle"):
            # Load state
            print("Loading previously saved state")
            with open("orders.pickle", "rb") as f:
                self.orders = pickle.load(f)
        else:
            # Start from scratch
            print("No state saved, starting from scratch")

        # Load data points
        if path.exists("dataframe.pickle"):
            self.data = pd.read_pickle("dataframe.pickle")

            # Only track up to a fixed amount of data points
            self.data = self.data.tail(config["max_data_rows"] - 1)

        # Connect to RobinHood
        if not config["debug_enabled"]:
            try:
                rh_response = r.login(config["username"], config["password"])
            except:
                print("Got exception while attempting to log into RobinHood.")
                exit()

        # Download RobinHood parameters
        for a_robinhood_ticker in config["ticker_list"].values():
            if not config["debug_enabled"]:
                try:
                    result = r.get_crypto_info(a_robinhood_ticker)
                    s_inc = result["min_order_quantity_increment"]
                    p_inc = result["min_order_price_increment"]
                except:
                    print("Failed to get increments from RobinHood.")
                    exit()
            else:
                s_inc = 0.0001
                p_inc = 0.0001

            self.min_share_increments.update({a_robinhood_ticker: float(s_inc)})
            self.min_price_increments.update({a_robinhood_ticker: float(p_inc)})

        # Initialize the available_cash amount
        self.available_cash = self.get_available_cash()

        print("Bot Ready")

        return

    def cancel_order(self, order_id):
        if not config["debug_enabled"]:
            try:
                cancelResult = r.cancel_crypto_order(order_id)
            except:
                print("Got exception canceling order, will try again.")
                return False

        return True

    def buy(self, ticker):
        if (
            self.available_cash < config["buy_amount_per_trade"]
            or self.is_trading_locked
        ):
            return False

        # Values need to be specified to no more precision than listed in min_price_increments.
        # Truncate to 7 decimal places to avoid floating point problems way out at the precision limit
        price = round(
            floor(self.data.iloc[-1][ticker] / self.min_price_increments[ticker])
            * self.min_price_increments[ticker],
            7,
        )

        # How much to buy depends on the configuration
        quantity = (
            self.available_cash
            if (config["buy_amount_per_trade"] == 0)
            else config["buy_amount_per_trade"]
        ) / price
        quantity = round(
            floor(quantity / self.min_share_increments[ticker])
            * self.min_share_increments[ticker],
            7,
        )

        print("Buying " + str(ticker) + " " + str(quantity) + " at $" + str(price))

        if config["trades_enabled"] and not config["debug_enabled"]:
            try:
                buy_info = r.order_buy_crypto_limit(str(ticker), quantity, price)

                # Add this new asset to our orders
                self.orders[buy_info["id"]] = asset(
                    ticker, quantity, price, buy_info["id"]
                )
            except:
                print("Got exception trying to buy, aborting.")
                return False

        return True

    def sell(self, asset):
        # Do we have enough of this asset to sell?
        if asset.quantity <= 0.0 or self.is_trading_locked:
            return False

        # Values needs to be specified to no more precision than listed in min_price_increments.
        # Truncate to 7 decimal places to avoid floating point problems way out at the precision limit
        price = round(
            floor(
                self.data.iloc[-1][asset.ticker]
                / self.min_price_increments[asset.ticker]
            )
            * self.min_price_increments[asset.ticker],
            7,
        )
        profit = round((asset.quantity * price) - (asset.quantity * asset.price), 3)

        print(
            "Selling "
            + str(asset.ticker)
            + " "
            + str(asset.quantity)
            + " for $"
            + str(price)
            + " (profit: $"
            + str(profit)
            + ")"
        )

        if config["trades_enabled"] and not config["debug_enabled"]:
            try:
                sell_info = r.order_sell_crypto_limit(
                    str(asset.ticker), asset.quantity, price
                )

                # Mark this asset as sold, the garbage collector (see 'run' method) will remove it from our orders at the next iteration
                self.orders[asset.order_id].quantity = 0
            except:
                print("Got exception trying to sell, aborting.")
                return False

        return True

    def run(self):
        now = datetime.now()
        self.data = self.get_new_data(now)

        # Schedule the next iteration
        Timer(config["minutes_between_updates"] * 60, self.run).start()

        # Print state
        print(
            "-- "
            + str(datetime.now().strftime("%Y-%m-%d %H:%M"))
            + " ---------------------"
        )
        print(self.data.tail())

        # We don't have enough consecutive data points to decide what to do
        self.is_trading_locked = not self.is_data_consistent(now)

        # Let's make sure we have the correct cash amount available for trading
        if self.is_new_order_added or self.available_cash < 0:
            self.available_cash = self.get_available_cash()

        if len(self.orders) > 0:
            print("-- Orders -------------------------------")

            for a_asset in list(self.orders.values()):
                # Check if any of these open orders on Robinhood are ours
                is_asset_deleted = False

                # Do we have any orders not filled on the platform? (swing/miss)
                if self.is_new_order_added:
                    try:
                        open_orders = r.get_all_open_crypto_orders()
                    except:
                        print(
                            "An exception occurred while retrieving list of open orders."
                        )
                        open_orders = []

                    for a_order in open_orders:
                        if a_order["id"] == a_asset.order_id and self.cancel_order(
                            a_order["id"]
                        ):
                            print(
                                "Order #"
                                + str(a_order["id"])
                                + " ("
                                + a_order["side"]
                                + " "
                                + a_asset.ticker
                                + ") was not filled. Cancelled and removed from orders."
                            )

                            self.orders.pop(a_asset.order_id)
                            is_asset_deleted = True

                    # We're done processing new orders
                    self.is_new_order_added = False

                if not is_asset_deleted:
                    # Print a summary of all our assets
                    print(str(a_asset.ticker) + ": " + str(a_asset.quantity), end="")

                    if a_asset.quantity > 0.0:
                        cost = a_asset.quantity * a_asset.price
                        print(
                            " | Price: $"
                            + str(round(a_asset.price, 3))
                            + " | Cost: $"
                            + str(round(cost, 3))
                            + " | Current value: $"
                            + str(
                                round(
                                    self.data.iloc[-1][a_asset.ticker]
                                    * a_asset.quantity,
                                    3,
                                )
                            )
                        )
                    else:
                        # We sold this asset during the previous iteration, and it wasn't still pending here above
                        # We can remove it from our orders safely (garbage collector)
                        self.orders.pop(a_asset.order_id)
                        print("\n")

                    # Is it time to sell any of them?
                    if (
                        getattr(
                            self.signal,
                            "sell_" + str(config["trade_strategies"]["sell"]),
                        )(a_asset, self.data)
                        or
                        # Stop-loss: is the current price below the purchase price by the percentage defined in the config file?
                        (
                            self.data.iloc[-1][a_asset.ticker]
                            < a_asset.price
                            - (a_asset.price * config["stop_loss_threshold"])
                        )
                    ):
                        self.is_new_order_added = (
                            self.sell(a_asset) or self.is_new_order_added
                        )

        # Buy?
        for a_robinhood_ticker in config["ticker_list"].values():
            if getattr(self.signal, "buy_" + str(config["trade_strategies"]["buy"]))(
                a_robinhood_ticker, self.data
            ):
                self.is_new_order_added = (
                    self.buy(a_robinhood_ticker) or self.is_new_order_added
                )

        # Final status for this iteration
        print("-- Bot Status ---------------------------")
        print("Buying power: $" + str(self.available_cash))

        # Save state
        with open("orders.pickle", "wb") as f:
            pickle.dump(self.orders, f)

        self.data.to_pickle("dataframe.pickle")


class checker:
    def __init__(self):
        self.stats_dict = {}  # Dictionary to hold stats for each ticker

    def check_price(self, ticker):
        ticker_price = 0  # update with code for a query to robinhood
        return ticker_price

    def update_holdings(self, holdings_df):
        # update the holdings from robinhood.
        return

    def check_order_status(self, order_id):  #
        # update the order status from robinhood for the order that is referenced with "order_id".
        return

    def is_data_consistent(self, now):
        if self.data.shape[0] <= 1:
            return False

        # Check for break between now and last sample
        timediff = now - datetime.strptime(
            self.data.iloc[-1]["timestamp"], "%Y-%m-%d %H:%M"
        )

        # Not enough data points available or it's been too long since we recorded any data
        if timediff.seconds > config["minutes_between_updates"] * 120:
            return False

        # Check for break in sequence of samples to minimum consecutive sample number
        position = len(self.data) - 1
        if position >= self.min_consecutive_samples:
            for x in range(0, self.min_consecutive_samples):
                timediff = datetime.strptime(
                    self.data.iloc[position - x]["timestamp"], "%Y-%m-%d %H:%M"
                ) - datetime.strptime(
                    self.data.iloc[position - (x + 1)]["timestamp"], "%Y-%m-%d %H:%M"
                )

                if timediff.seconds > config["minutes_between_updates"] * 120:
                    print("Holding trades: interruption found in price data.")
                    return False

        return True

    def get_new_data(self, now):
        new_row = {}

        self.is_trading_locked = False
        new_row["timestamp"] = now.strftime("%Y-%m-%d %H:%M")

        # Calculate moving averages and RSI values
        for a_kraken_ticker, a_robinhood_ticker in config["ticker_list"].items():
            if not config["debug_enabled"]:
                try:
                    result = get_json(
                        "https://api.kraken.com/0/public/Ticker?pair="
                        + str(a_kraken_ticker)
                    ).json()

                    if len(result["error"]) == 0:
                        new_row[a_robinhood_ticker] = round(
                            float(result["result"][a_kraken_ticker]["a"][0]), 3
                        )
                except:
                    print("An exception occurred retrieving prices.")
                    self.is_trading_locked = True
                    return self.data
            else:
                new_row[a_robinhood_ticker] = round(float(randint(10, 100)), 3)

            self.data = self.data.append(new_row, ignore_index=True)

            # If the Kraken API is overloaded, they freeze the values it returns
            if (
                self.data.tail(4)[a_robinhood_ticker].to_numpy()[-1]
                == self.data.tail(4)[a_robinhood_ticker].to_numpy()
            ).all():
                print(
                    "Repeating values detected for "
                    + str(a_robinhood_ticker)
                    + ". Ignoring data point."
                )
                self.data = self.data[:-1]
            elif self.data.shape[0] > 0:
                self.data[a_robinhood_ticker + "_SMA_F"] = (
                    self.data[a_robinhood_ticker]
                    .shift(1)
                    .rolling(window=config["moving_average_periods"]["sma_fast"])
                    .mean()
                )
                self.data[a_robinhood_ticker + "_SMA_S"] = (
                    self.data[a_robinhood_ticker]
                    .shift(1)
                    .rolling(window=config["moving_average_periods"]["sma_slow"])
                    .mean()
                )
                self.data[a_robinhood_ticker + "_RSI"] = RSI(
                    self.data[a_robinhood_ticker].values,
                    timeperiod=config["rsi_period"],
                )
                (
                    self.data[a_robinhood_ticker + "_MACD"],
                    self.data[a_robinhood_ticker + "_MACD_S"],
                    macd_hist,
                ) = MACD(
                    self.data[a_robinhood_ticker].values,
                    fastperiod=config["moving_average_periods"]["macd_fast"],
                    slowperiod=config["moving_average_periods"]["macd_slow"],
                    signalperiod=config["moving_average_periods"]["macd_signal"],
                )

            if config["save_charts"] == True:
                slice = self.data[
                    [
                        a_robinhood_ticker,
                        str(a_robinhood_ticker) + "_SMA_F",
                        str(a_robinhood_ticker) + "_SMA_S",
                    ]
                ]
                fig = slice.plot.line().get_figure()
                fig.savefig(
                    "chart-" + str(a_robinhood_ticker).lower() + "-sma.png", dpi=300
                )
                plt.close(fig)

        return self.data

    def get_available_cash(self):
        available_cash = -1.0

        if not config["debug_enabled"]:
            try:
                me = r.account.load_phoenix_account(info=None)
                available_cash = round(
                    float(me["crypto_buying_power"]["amount"]) - config["reserve"], 3
                )
            except:
                print("An exception occurred while reading available cash amount.")
        else:
            self.available_cash = randint(1000, 5000) + config["reserve"]

        return available_cash

    def retrieve_indicators(
        symbol,
        screener="crypto",
        interval=Interval.INTERVAL_15_MINUTES,
        exchange="BITFINEX",
    ):
        """
        Gets indicators given a symbol and interval

        Args:
            symbol (_type_): _description_
            screener (str, optional): _description_. Defaults to 'crypto'.
            interval (_type_, optional): _description_. Defaults to Interval.INTERVAL_15_MINUTES.
            exchange (str, optional): _description_. Defaults to 'BITFINEX'.

        Returns:
            _type_: _description_
        """
        coin_data = TA_Handler(
            symbol=symbol,
            exchange=exchange,
            screener=screener,
            interval=interval,
            timeout=None,
        )
        result = (
            coin_data.get_analysis().indicators
        )  # this result can be parsed for the indicators desired.
        return result

    def get_tradingview_statsdict(self, tickers):  #
        stats_dict = (
            {}
        )  # will hold technical analysis results for each currency pair. updated every iteration.
        tickers = [
            "BTC",
            "ETH",
            "DOGE",
            "ETC",
            "SHIB",
            "MATIC",
            "UNI",
            "XLM",
            "LTC",
            "LINK",
        ]
        coins_with_base = [str(str(coin) + "USD") for coin in tickers]
        for ticker in coins_with_base:  # loop through each currency pair.
            res = checker.retrieve_indicators(
                ticker
            )  # *get the technical analysis results for the coin designated by the variable: "ticker"
            # res contains the indicators for the ticker
            stats_dict[ticker] = res  # add results to our stats dictionary
            if simulate_pausing:
                time.sleep(
                    random.randint(1, 3)
                )  # sleep for a random amount of time between 1 and 3 seconds.
        self.stats_dict = (
            stats_dict  # update the dictionary of technical analysis results.
        )
    def trading_view_suggestion(self, ticker='BTC'):
        # Trading View suggestions for buying/selling/holding crypto
        """
        Takes in a ticker and returns a 1,-1, or 0 indicating whether or not to buy or sell the ticker. This is based on tradingview_ta data. The exchange this function utilizes is not Kraken. It is Coinbase.

        Args:
            ticker (str): the ticker of the crypto to check.
        """
        assert type(ticker) == str
        pos_df = pd.DataFrame()  # hold the ta data for all of the tickers
        output = TA_Handler(
            symbol=f"{ticker.upper()}USD",
            screener="Crypto",
            exchange="COINBASE",
            interval=Interval.INTERVAL_1_MINUTE,
        )
        output_analysis = output.get_analysis()
        dict2 = (
            output_analysis.summary
        )  # get the summary dictionary. NOTE: Also available is the output_analysis.technical_indicators, for further analysis.

        buyScore = float(dict2["BUY"])
        sellScore = float(dict2["SELL"])
        neutralScore = float(dict2["NEUTRAL"])

        if (
            buyScore > sellScore and buyScore > neutralScore
        ):  # if more suggestions for buy than sell and neutral.
            return 1  # buy
        elif (
            sellScore > buyScore and sellScore > neutralScore
        ):  # if more suggestions for sell than buy and neutral.
            return -1
        else:  #
            return 0  # do not buy but don't sell either. This means that the ticker is neutral.

class thief:
    # There are several options available
    # 1. robin_stocks.robinhood.orders.order_buy_crypto_limit(symbol, quantity, limitPrice, timeInForce='gtc', jsonify=True)
    #* Submits a limit order for a crypto by specifying the decimal amount of shares to buy. Good for share fractions up to 8 decimal places.
    # 2. robin_stocks.robinhood.orders.order_buy_crypto_by_quantity(symbol, quantity, timeInForce='gtc', jsonify=True)
    #* Submits a market order for a crypto by specifying the decimal amount of shares to buy. Good for share fractions up to 8 decimal places.
    # 3. robin_stocks.robinhood.orders.order_buy_crypto_limit_by_price(symbol, amountInDollars, limitPrice, timeInForce='gtc', jsonify=True)[source]
    #* Submits a limit order for a crypto by specifying the decimal price to buy. Good for share fractions up to 8 decimal places.
    # 4. robin_stocks.robinhood.orders.order_buy_crypto_limit_by_price(symbol, amountInDollars, limitPrice, timeInForce='gtc', jsonify=True)[source]
    #* Submits a limit order for a crypto by specifying the decimal price to buy. Good for share fractions up to 8 decimal places.
    # 5.  robin_stocks.robinhood.orders.order_crypto(symbol, side, quantityOrPrice, amountIn='quantity', limitPrice=None, timeInForce='gtc', jsonify=True)[source]
    '''
    Submits an order for a crypto.
        Parameters:

            symbol (str) – The crypto ticker of the crypto to trade.
            side (str) – Either ‘buy’ or ‘sell’
            quantityOrPrice (float) – Either the decimal price of shares to trade or the decimal quantity of shares.
            amountIn (Optional[str]) – If left default value of ‘quantity’, order will attempt to trade cryptos by the amount of crypto you want to trade. If changed to ‘price’, order will attempt to trade cryptos by the price you want to buy or sell.
            limitPrice (Optional[float]) – The price to trigger the market order.
            timeInForce (Optional[str]) – Changes how long the order will be in effect for. ‘gtc’ = good until cancelled.
            jsonify (Optional[str]) – If set to False, function will return the request object which contains status code and headers.

        Returns:

        Dictionary that contains information regarding the selling of crypto, such as the order id, the state of order (queued, confired, filled, failed, canceled, etc.), the price, and the quantity.'''

    def __init__(self):
        #self.record_book = {} # The record book
        self.bought_crypto = False # initialize
        self.sold_crypto = False # initialize
        self.orders = {}
        self.currentPrice = 0.00 # current price of whatever coin is being used
        self.currentDataFrame = pd.DataFrame() # initialize
        if path.exists("orders.pickle"):
                # Load state
            print("Loading previously saved state")
            with open("orders.pickle", "rb") as f:
                self.orders = pickle.load(f)
        else:
            # Start from scratch
            print("No state saved, starting from scratch")
            pd.DataFrame(self.orders).to_pickle("dataframe.pickle")
        # Connect to RobinHood
        if not config["debug_enabled"]:
            try:
                rh_response = r.login(config["username"], config["password"])
            except:
                print("Got exception while attempting to log into RobinHood.")
                exit()



        #? self.orders.to_pickle("dataframe.pickle")
    # actions
    def scout(self):
        df_master = pd.DataFrame.from_dict(r.get_crypto_positions()).drop(
            columns=["account_id", "cost_bases", "id", "updated_at"]
            )
        df_master.to_csv('df_master.csv')
        self.currentDataFrame = df_master
    def buy_robinhood_crypto_limit(self,ticker,limit_price):
        try:
            quantityOrPrice = config['buy_amount_per_trade'] # the buy amount per trade
            r.orders.order_crypto(ticker,'buy',
                                  quantityOrPrice,
                                  amountIn='price',
                                  limitPrice=limit_price,
                                  timeInForce='gtc',
                                  jsonify=True)
        except Exception:
            pass
        # Save state
        with open("orders.pickle", "wb") as f:
            pickle.dump(self.orders, f)

    def buy_robinhood_crypto_dollars(self,ticker,dollars):
        try:
            quantityOrPrice = dollars # the buy amount per trade
            r.orders.order_crypto(ticker,'buy',
                                  quantityOrPrice,
                                  amountIn='price',
                                  limitPrice=None,
                                  timeInForce='gtc',
                                  jsonify=True)
        except Exception:
            pass
        # Save state
        with open("orders.pickle", "wb") as f:
            pickle.dump(self.orders, f)

    def sell_robinhood_crypto_coins(self,ticker):
        try:
            # hashing out the coin name from the embedded dictionary in the df_master
            row_id = -1 # initializer for row
            self.scout()
            df_master = self.currentDataFrame
            for i in range(0,len(df_master)):
                coin_name = df_master['currency'][i]['code']
                if coin_name == ticker:
                    row_id = i # this is the row where our data lives.
                    break
            if row_id > -1:
                #todo can limit decimal places with the string here
                current_holdings = float(df_master['quantity'][row_id]) # ...or quantity available
                digits = len(str(current_holdings)) # digits for this coin (maximum granularity)
                quantityOrPrice = current_holdings/4 # one fourth of the quantity held.
                quantityOrPrice = str(quantityOrPrice)[0:int(digits)]
                quantityOrPrice = float(quantityOrPrice)
                r.orders.order_crypto(ticker,'sell',
                                    quantityOrPrice,
                                    amountIn='quantity',
                                    limitPrice=None,
                                    timeInForce='gtc',
                                    jsonify=True)
                print("order submitted for a sell of ",quantityOrPrice," ",ticker)
            else:
                print("row id issue")
        except Exception as e:
            pass
        # Save state
        current_holdings = current_holdings - quantityOrPrice
        self.orders['BTC'] = current_holdings
        with open("orders.pickle", "wb") as f:
            pickle.dump(self.orders, f)

bought_prices = {}
bought_signals = {}

if __name__ == "__main__":

    login = r.login(config['username'], config['password'])

    MaidMarian = checker()  # initialize the checker object
    #LittleJohn = trader()  # initialize the trader class
    Sherrif = thief() # initialize the thief class

    bought = False
    coin_names = ['BTC','ETH','DOGE','ETC','SHIB','MATIC','UNI',"XLM",'LTC','LINK']
    while True:
        print("Running Over The Coins...")
        for ticker in coin_names:
            try:
                bought = bought_signals[ticker]
            except Exception:
                bought = False
            print("Running on Coin: ",ticker," bought is currently ", bought)
            #ticker = 'BTC'
            #!Sherrif.buy_robinhood_crypto_dollars(ticker,1.00) # market order order
            Sherrif.scout()
            df_master = Sherrif.currentDataFrame
            for i in range(0,len(df_master)):
                coin_name = df_master['currency'][i]['code']
                if coin_name == ticker:
                    row_id = i # this is the row where our data lives.
                    current_holdings = float(df_master['quantity'][row_id])
                    break

            tick = r.orders.get_crypto_quote(ticker)
            currentPrice = float(tick['mark_price'])# current price
            currentSpread = abs(float(tick['bid_price']) - float(tick['ask_price']))
            try:
                boughtPrice = bought_prices[ticker] # initialize
            except Exception: #
                boughtPrice = currentPrice
            #?current_holdings
            Sell_Conditions_Met = False
            val = boughtPrice - currentPrice
            formatted_string = "{:.9f}".format(val)


            tv = checker.trading_view_suggestion(ticker)

            if boughtPrice + currentSpread < currentPrice or tv == -1:
                Sell_Conditions_Met = True #
            else: #
                pass

            #//guess_price = currentPrice - currentPrice*0.0001 # 1% less than current price
            #//print("guessing price:  ", guess_price)

            if not bought and tv == 1: # trading view suggests buy
                try:
                    Sherrif.buy_robinhood_crypto_dollars(ticker,2.00)
                    #//Sherrif.buy_robinhood_crypto_limit(ticker,guess_price)
                    bought = True
                    boughtPrice = currentPrice
                    bought_prices[ticker] = boughtPrice
                    time.sleep(random.randint(5,10))
                except Exception:
                    pass
            elif bought and Sell_Conditions_Met:
                Sherrif.sell_robinhood_crypto_coins(ticker)
                bought_prices[ticker] = -1 # remove the price from the prices
                time.sleep(random.randint(5,10))
            elif not bought and Sell_Conditions_Met: #* sell balances not reflected by 'bought' variable
                try: #
                    Sherrif.sell_robinhood_crypto_coins(ticker)
                except Exception:
                    pass
            else: #
                print("Neither event received")
            print(f'tv:{tv}, bought:{bought}')
            bought_signals[ticker] = bought # save the signal
            time.sleep(random.randint(0,2))

        seconds = random.randint(60,120)
        print("napping...",seconds,' seconds')
        time.sleep(seconds)