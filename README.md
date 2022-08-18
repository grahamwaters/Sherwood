# Sherwood:
---
Before you start using Sherwood, you need to understand the following:
Cryptocurrency investing is inherently risky. Doing it with code you didn’t write, understand, or know how to modify is a **really bad** idea.

What you do with this code is entirely up to you, and any risks you take are your own. It’s intended to be educational and comes with absolutely no guarantee of anything at all. If you use this code, you assume all responsibility for your own actions.

But have fun.

---

Jason Bowling makes several salient points about using a bot for this purpose in his article on Medium.com.
>Every time you issue a call that talks to the server — getting prices, issuing an order, checking status — check for exceptions. Every. Single. Time (Bowling, 2020).

We will be using the try/except pattern often in this code to prevent any code blockages due to uncaught exceptions.

### simple trading with simple logic
The goal for Sherwood is to create as simple a trading bot as possible. This being said, there are certain aspects of trading that make the usage of a bot complex. The following is a list of some of the more complex aspects of trading with a bot.
* signals
* credentials
* browser automation
* dev accounts and trading fees

So, in our functions.py file, we will define functions that meet the following criteria:
* are simple (have no more than two arguments)
* perform a single action

### The Record Class
The Record class is a simple class that we will use to store the data we collect from each trade. It defines the following attributes:
* crypto_ticker: the cryptocurrency ticker symbol
* quantity: the quantity of the cryptocurrency that was traded
* price: the price of the cryptocurrency at which it was traded
* order_id: the order id of the trade
* timestamp: the timestamp of the trade
* order_type: the type of order (buy or sell)

**(flex goal) status: the status of the trade (open, closed, or canceled)**

### The Trader Class
The Trader class is the main class for Sherwood. Any actions that involve a volume (either in USD or in a coin) will be performed using methods defined in this class. It is responsible for the following:
* buying a cryptocurrency by amount in USD
* buying a cryptocurrency by volume in COIN
* selling a cryptocurrency by amount in USD **(unusual behavior)**
* selling a cryptocurrency by volume in COIN
* canceling an open order by its order id

### The Checker Class
The checker class is an important part of Sherwood. Any actions that involve asking Robinhood for information will be performed using methods defined in this class. It is responsible for the following:
* checking the price of a cryptocurrency
* updating current crypto holdings
* checking the status of an order

## Installation
This code uses Python3. First, install the following dependencies:
* [Robin-Stocks](http://www.robin-stocks.com/en/latest/quickstart.html): `pip3 install robin_stocks`
* [Pandas](https://pandas.pydata.org/pandas-docs/stable/index.html): `pip3 install pandas`
* [TA-Lib](https://www.ta-lib.org/): download their tarball and compile it

Now make a file called config.py and put the following in it:
```python
config = {
    'username': 'your email here', # Robinhood credentials
    'password': 'your password here', # Robinhood credentials
    'trades_enabled': True, # if False, just collect data
    'debug_enabled': True, # if enabled, just pretend to connect to Robinhood
    'ticker_list': { # list of coin ticker pairs Kraken/Robinhood (XETHZUSD/ETH, etc) - https://api.kraken.com/0/public/AssetPairs
        'XETHZUSD': 'ETH',
        'XXBTZUSD': 'BTC'
    },
    'trade_strategies': { # select which strategies would you like the bot to use (buy, sell); see documentation for more info
        'buy': 'sma_rsi_threshold',
        'sell': 'above_buy'
    },
    'buy_below_moving_average': 0.0075, # buy if price drops below Fast_MA by this percentage (0.75%)
    'profit_percentage': 0.01, # sell if price raises above purchase price by this percentage (1%)
    'buy_amount_per_trade': 0, # if greater than zero, buy this amount of coin, otherwise use all the cash in the account
    'moving_average_periods': { # data points needed to calculate SMA fast, SMA slow, MACD fast, MACD slow, MACD signal
        'sma_fast': 24, # 12 data points per hour, 2 hours worth of data
        'sma_slow': 96,
        'macd_fast': 24,
        'macd_slow': 52, # MACD 12/26 -> 24/52
        'macd_signal': 14
    },
    'rsi_period': 48, # data points for RSI
    'rsi_threshold': { # RSI thresholds to trigger a buy or a sell order
        'buy': 39.5,
        'sell': 60
    },
    'reserve': 5.00, # tell the bot if you don't want it to use all of the available cash in your account
    'stop_loss_threshold': 0.05,   # sell if the price drops at least 5% below the purchase price
    'minutes_between_updates': 1, # 1 (default), 5, 15, 30, 60, 240, 1440, 10080, 21600
    'save_charts': False,
    'max_data_rows': 10000
}

```
Once dependencies have been installed and the config.py file contains (at least) your login credentials, you can run the bot. But how do you run it?
Great question, let's go through some of the elements of the config.py file before we dive into the weeds of running the Sherwood bot (See the forest for the trees if you will).
```python
* (string) `username` and `password`: Robinhood credentials
* (bool) `trades_enabled`:  If False, run in test mode and just collect data, otherwise submit orders
* (bool) `debug_enabled`: Simulate interactions with Robinhood (via random values)
* (list) `ticker_list`: List of coin ticker pairs Kraken/Robinhood (XETHZUSD/ETH, etc); see [here](https://api.kraken.com/0/public/AssetPairs) for a complete list of available tickers on Kraken
* (dict) `trade_strategies`: Select which strategies would you like the bot to use (buy, sell)
* (float) `buy_below_moving_average`: If the price dips below the MA by this percentage, and if the RSI is below the oversold threshold (see below), it will try to buy
* (float) `sell_above_buy_price`: Once the price rises above the Buy price by this percentage, it will try to sell
* (float) `buy_amount_per_trade`: If greater than zero, buy this amount of coin, otherwise use all the cash in the account
* (dict) `moving_average_periods`: Number of MA observations to wait before sprinting into action, for each measure (SMA fast, SMA slow, MACD fast, MACD slow, MACD signal)
* (int) `rsi_period`: Length of the observation window for calculating the RSI
* (float) `rsi_buy_threshold`: Threshold below which the bot will try to buy
* (float) `reserve`: By default, the bot will try to use all the funds available in your account to buy crypto; use this value if you want to set aside a given amount that the bot should not spend
* (float) `stop_loss_threshold`: Threshold below which the bot will sell its holdings, regardless of any gains
* (int) `minutes_between_updates`: How often should the bot spring into action (1 (default), 5, 15, 30, 60, 240, 1440, 10080, 21600)
* (bool) `save_charts`: Enable this feature to have the bot save SMA charts for each coin it's handling
* (int) `max_data_rows`: Max number of data points to store in the Pickle file (if you have issues with memory limits on your machine). 1k rows = 70kB
```
[thanks to Jason for this list of variables](https://github.com/cryptoTradingBot.git)

## Running Sherwood
To run your Sherwood bot you will simply create the appropriate objects and use the **run()** method of the class 'trader'.
```python
  LittleJohn = trader() # create a trader named 'LittleJohn'
  LittleJohn.run() # LittleJohn is now running through the forest.
  # Can't resist: (oodillally oodillally golly what a day)
```

Information about the bot's state is also saved in three pickle files, so that if you stop and restart it, it will continue from where it left off:

> `nohup ./bot.py &`

### The general flow of the Sherwood Bot looks like this:
1. Load the configuration and initialize or load a previously saved state
2. Load saved data points or download new ones from Kraken
3. Every 5 minutes (you can customize this in the settings), download the latest price info from Kraken for each coin
4. Compute [moving averages](https://www.investopedia.com/terms/m/movingaverage.asp) and [RSI](https://www.investopedia.com/terms/r/rsi.asp), making sure that there haven't been any interruptions in the data sequence
5. If the conditions to buy or sell are met, submit the corresponding order
6. Rinse and repeat

> The bot maintains a list of purchased assets (saved as `orders.pickle`) and at each iteration, it determines if the conditions to sell any of them are met. It also handles swing and miss orders, by checking if any of the orders placed during the previous iteration are still pending (not filled), and cancels them (Bowling, 2020).


---

Jason Crouse does a great job outlining the technical indicators in his readme file. I have included his descriptions below for supplemental review.
> ## Indicators
> ### Relative Strength Index
> The RSI trading indicator is a measure of the relative strength of the market (compared to its history), a momentum oscillator and is often used as an overbought and oversold technical indicator. The RSI is displayed as a line graph that moves between two extremes from 0 to 100. Traditional interpretation and usage of the RSI are that values of 70 or above indicate that a security is becoming overvalued and the price of the security is likely to go down in the future (bearish), while the RSI reading of 30 or below indicates an oversold or undervalued condition and the price of the security is likely to go up in the future (bullish).

> ### Moving Average Convergence/Divergence
> Moving average convergence divergence (MACD) is a trend-following momentum indicator that shows the relationship between two moving averages of a security’s price. The MACD is calculated by subtracting the 26-period [exponential moving average](https://www.investopedia.com/terms/e/ema.asp) (EMA) from the 12-period EMA. The result of that calculation is the MACD line. A nine-day EMA of the MACD called the "signal line," is then plotted on top of the MACD line, which can function as a trigger for buy and sell signals. Traders may buy the security when the MACD crosses above its signal line and sell—or short—the security when the MACD crosses below the signal line. Moving average convergence divergence (MACD) indicators can be interpreted in several ways, but the more common methods are crossovers, divergences, and rapid rises/falls.

> ## Technical Analysis
> This bot can implement any technical analysis as a series of conditions on the indicators it collects. Some of them are built into the algorithm, to give you a starting point to create your own. For example, Jason's approach is to buy when the price drops below the Fast-SMA by the percentage configured in the settings, and the RSI is below the threshold specified in the config file. By looking at multiple data points, you can also determine if a crossover happened, and act accordingly. The simple strategy outlined here above can be expanded [in many ways](https://medium.com/mudrex/rsi-trading-strategy-with-20-sma-on-mudrex-a26bd2ac039b). To that end, this bot keeps track of a few indicators that can be used to [determine if it's time to buy or sell](https://towardsdatascience.com/algorithmic-trading-with-macd-and-python-fef3d013e9f3): SMA fast, SMA slow, RSI, MACD, MACD Signal. Future versions will include ways to select which approach you would like to use.

> ## Backtesting
> Backtesting is the process of testing a trading or investment strategy using data from the past to see how it would have performed. For example, let's say your trading strategy is to buy Bitcoin when it falls 3% in a day, your backtest software will check Bitcoin's prices in the past and fire a trade when it fell 3% in a day. The backtest results will show if the trades were profitable. At this time, this bot doesn't offer an easy way to ingest past data and run simulations, but it's something I have on my wishlist for sure.

[His Repository is included here](https://github.com/JasonRBowling/cryptoTradingBot.git)

Works Cited
* https://medium.com/swlh/design-lessons-from-my-first-crypto-trading-bot-fcf654b99546