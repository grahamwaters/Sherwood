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