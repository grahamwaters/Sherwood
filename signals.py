from config import config
from math import isnan
import pandas as pd
import numpy as np
from tradingview_ta import TA_Handler, Interval

class signals:
    def buy_sma_crossover_rsi(self, ticker, data):
        # Moving Average Crossover with RSI Filter
        # Credits: https://trader.autochartist.com/moving-average-crossover-with-rsi-filter/
        # Buy when Fast-SMA crosses Slow-SMA from below, and stays above for 3 consecutive readings, and RSI > buy threshold (50 suggested)

        return (
            # Make sure the data is valid
            not isnan(data.iloc[-1][ticker + "_SMA_F"])
            and not isnan(data.iloc[-2][ticker + "_SMA_F"])
            and not isnan(data.iloc[-3][ticker + "_SMA_F"])
            and not isnan(data.iloc[-4][ticker + "_SMA_F"])
            and not isnan(data.iloc[-1][ticker + "_SMA_S"])
            and not isnan(data.iloc[-2][ticker + "_SMA_S"])
            and not isnan(data.iloc[-3][ticker + "_SMA_S"])
            and not isnan(data.iloc[-4][ticker + "_SMA_S"])
            and not isnan(data.iloc[-1][ticker + "_RSI"])
            and
            # Fast-SMA crossed Slow-SMA and stays above
            data.iloc[-1][ticker + "_SMA_F"] >= data.iloc[-1][ticker + "_SMA_S"]
            and data.iloc[-2][ticker + "_SMA_F"] >= data.iloc[-2][ticker + "_SMA_S"]
            and data.iloc[-3][ticker + "_SMA_F"] >= data.iloc[-3][ticker + "_SMA_S"]
            and data.iloc[-4][ticker + "_SMA_F"] < data.iloc[-4][ticker + "_SMA_S"]
            and
            # ... and they diverge
            data.iloc[-1][ticker + "_SMA_F"] - data.iloc[-1][ticker + "_SMA_S"]
            >= data.iloc[-2][ticker + "_SMA_F"] - data.iloc[-2][ticker + "_SMA_S"]
            and
            # RSI above threshold
            data.iloc[-1][ticker + "_RSI"] > config["rsi_threshold"]["buy"]
        )

    def buy_sma_rsi_threshold(self, ticker, data):
        # Simple Fast-SMA and RSI
        # Buy when price is below Fast-SMA and RSI is below threshold

        return (
            not isnan(data.iloc[-1][ticker + "_SMA_F"])
            and not isnan(data.iloc[-1][ticker + "_RSI"])
            and
            # Is the current price below the Fast-SMA by the percentage defined in the config file?
            data.iloc[-1][ticker]
            <= data.iloc[-1][ticker + "_SMA_F"]
            - (data.iloc[-1][ticker + "_SMA_F"] * config["buy_below_moving_average"])
            and
            # RSI below the threshold
            data.iloc[-1][ticker + "_RSI"] <= config["rsi_threshold"]["buy"]
        )

    def sell_above_buy(self, asset, data):
        # Simple percentage

        return data.iloc[-1][asset.ticker] > asset.price + (
            asset.price * config["profit_percentage"]
        )

    def sell_sma_crossover_rsi(self, asset, data):
        # Moving Average Crossover with RSI Filter
        # Credits: https://trader.autochartist.com/moving-average-crossover-with-rsi-filter/

        return (
            # Make sure the data is valid
            not isnan(data.iloc[-1][asset.ticker + "_SMA_F"])
            and not isnan(data.iloc[-2][asset.ticker + "_SMA_F"])
            and not isnan(data.iloc[-3][asset.ticker + "_SMA_F"])
            and not isnan(data.iloc[-4][asset.ticker + "_SMA_F"])
            and not isnan(data.iloc[-1][asset.ticker + "_SMA_S"])
            and not isnan(data.iloc[-2][asset.ticker + "_SMA_S"])
            and not isnan(data.iloc[-3][asset.ticker + "_SMA_S"])
            and not isnan(data.iloc[-4][asset.ticker + "_SMA_S"])
            and not isnan(data.iloc[-1][asset.ticker + "_RSI"])
            and
            # Fast-SMA crossed Slow-SMA and stays above
            data.iloc[-1][asset.ticker + "_SMA_F"]
            <= data.iloc[-1][asset.ticker + "_SMA_S"]
            and data.iloc[-2][asset.ticker + "_SMA_F"]
            <= data.iloc[-2][asset.ticker + "_SMA_S"]
            and data.iloc[-3][asset.ticker + "_SMA_F"]
            <= data.iloc[-3][asset.ticker + "_SMA_S"]
            and data.iloc[-4][asset.ticker + "_SMA_F"]
            > data.iloc[-4][asset.ticker + "_SMA_S"]
            and
            # ... and they diverge
            data.iloc[-1][ticker + "_SMA_S"] - data.iloc[-1][ticker + "_SMA_F"]
            >= data.iloc[-2][ticker + "_SMA_S"] - data.iloc[-2][ticker + "_SMA_F"]
            and
            # RSI below threshold
            data.iloc[-1][ticker + "_RSI"] <= config["rsi_threshold"]["sell"]
            and
            # Price is greater than purchase price by at least profit percentage
            data.iloc[-1][asset.ticker]
            >= asset.price + (asset.price * config["profit_percentage"])
        )

    def trading_view_suggestion(self,ticker):
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
        dict2 = output_analysis.summary # get the summary dictionary. NOTE: Also available is the output_analysis.technical_indicators, for further analysis.

        buyScore = float(dict2["BUY"])
        sellScore = float(dict2["SELL"])
        neutralScore = float(dict2["NEUTRAL"])

        if buyScore > sellScore and buyScore > neutralScore: # if more suggestions for buy than sell and neutral.
            return 1 # buy
        elif sellScore > buyScore and sellScore > neutralScore: # if more suggestions for sell than buy and neutral.
            return -1
        else: #
            return 0 # do not buy but don't sell either. This means that the ticker is neutral.
