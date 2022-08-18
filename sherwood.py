#!/usr/bin/python3 -u

# Sherwood Crypto Bot
# Version 1.1.0
# Graham Waters

import time, random
from config import config
from signals import signals
from tradingview_config import exchanges_dict # this contains the exchange names for each currency pair.
import pandas as pd
from tradingview_ta import TA_Handler, Interval, Exchange
import tradingview_ta
simulate_pausing = False # set to True to simulate pausing the bot for debugging purposes.
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

class trader:
    default_config = {
        'username': '',
        'password': '',
        'trades_enabled': False,
        'debug_enabled': False,
        'ticker_list': {
            'XETHZUSD': 'ETH'
        },
        'trade_strategies': {
            'buy': 'sma_rsi_threshold',
            'sell': 'above_buy'
        },
        'buy_below_moving_average': 0.0075,
        'profit_percentage': 0.01,
        'buy_amount_per_trade': 0,
        'moving_average_periods': {
            'sma_fast': 48, # 12 data points per hour, 4 hours worth of data
            'sma_slow': 192,
            'macd_fast': 48,
            'macd_slow': 104, # MACD 12/26 -> 48/104
            'macd_signal': 28
        },
        'rsi_period': 48,
        'rsi_threshold': 39.5,
        'reserve': 0.0,
        'stop_loss_threshold': 0.3,
        'minutes_between_updates': 5,
        'save_charts': True,
        'max_data_rows': 10000
    }
    data = pd.DataFrame()
    orders = {}
    min_share_increments = {}  #the smallest increment of a coin you can buy/sell
    min_price_increments = {}   #the smallest fraction of a dollar you can buy/sell a coin with
    min_consecutive_samples = 0
    available_cash = 0
    is_trading_locked = False # used to determine if we have had a break in our incoming price data and hold buys if so
    is_new_order_added = False # the bot performs certain cleanup operations after new orders are sent out
    signal = signals()

    def __init__( self ):
        # Set Pandas to output all columns in the dataframe
        pd.set_option( 'display.max_columns', None )
        pd.set_option( 'display.width', 300 )

        print( '-- Configuration ------------------------' )
        for c in self.default_config:
            isDefined = config.get( c )
            if ( not isDefined ):
                config[ c ] = self.default_config[ c ]

        if ( not config[ 'username' ] or not config[ 'password' ] ):
            print( 'RobinHood credentials not found in config file. Aborting.' )
            exit()

        if ( config[ 'rsi_period' ] > config[ 'moving_average_periods' ][ 'sma_fast' ] ):
            self.min_consecutive_samples = config[ 'rsi_period' ]
        else:
            self.min_consecutive_samples = config[ 'moving_average_periods' ][ 'sma_fast' ]

        for a_key, a_value in config.items():
            if ( a_key == 'username' or a_key == 'password' ):
                continue

            print( a_key.replace( '_', ' ' ).capitalize(), ': ', a_value, sep='' )

        print( '-- End Configuration --------------------' )

        if path.exists( 'orders.pickle' ):
            # Load state
            print( 'Loading previously saved state' )
            with open( 'orders.pickle', 'rb' ) as f:
                self.orders = pickle.load( f )
        else:
            # Start from scratch
            print( 'No state saved, starting from scratch' )

        # Load data points
        if ( path.exists( 'dataframe.pickle' ) ):
            self.data = pd.read_pickle( 'dataframe.pickle' )

            # Only track up to a fixed amount of data points
            self.data = self.data.tail( config[ 'max_data_rows' ] - 1 )
        else:
            # Download historical data from Kraken
            column_names = [ 'timestamp' ]

            for a_robinhood_ticker in config[ 'ticker_list' ].values():
                column_names.append( a_robinhood_ticker )

            self.data = pd.DataFrame( columns = column_names )

            for a_kraken_ticker, a_robinhood_ticker in config[ 'ticker_list' ].items():
                try:
                    result = get_json( 'https://api.kraken.com/0/public/OHLC?interval=' + str( config[ 'minutes_between_updates' ] ) + '&pair=' + a_kraken_ticker ).json()
                    historical_data = pd.DataFrame( result[ 'result' ][ a_kraken_ticker ] )
                    historical_data = historical_data[ [ 0, 1 ] ]

                    # Be nice to the Kraken API
                    sleep( 3 )
                except:
                    print( 'An exception occurred retrieving historical data from Kraken.' )

                # Convert timestamps
                self.data[ 'timestamp' ] = [ datetime.fromtimestamp( x ).strftime( "%Y-%m-%d %H:%M" ) for x in historical_data[ 0 ] ]

                # Copy the data
                self.data[ a_robinhood_ticker ] = [ round( float( x ), 3 ) for x in historical_data[ 1 ] ]

                # Calculate the indicators
                self.data[ a_robinhood_ticker + '_SMA_F' ] = self.data[ a_robinhood_ticker ].shift( 1 ).rolling( window = config[ 'moving_average_periods' ][ 'sma_fast' ] ).mean()
                self.data[ a_robinhood_ticker + '_SMA_S' ] = self.data[ a_robinhood_ticker ].shift( 1 ).rolling( window = config[ 'moving_average_periods' ][ 'sma_slow' ] ).mean()
                self.data[ a_robinhood_ticker + '_RSI' ] = RSI( self.data[ a_robinhood_ticker ].values, timeperiod = config[ 'rsi_period' ] )
                self.data[ a_robinhood_ticker + '_MACD' ], self.data[ a_robinhood_ticker + '_MACD_S' ], macd_hist = MACD( self.data[ a_robinhood_ticker ].values, fastperiod = config[ 'moving_average_periods' ][ 'macd_fast' ], slowperiod = config[ 'moving_average_periods' ][ 'macd_slow' ], signalperiod = config[ 'moving_average_periods' ][ 'macd_signal' ] )

        # Connect to RobinHood
        if ( not config[ 'debug_enabled' ] ):
            try:
                rh_response = rh.login( config[ 'username' ], config[ 'password' ] )
            except:
                print( 'Got exception while attempting to log into RobinHood.' )
                exit()

        # Download RobinHood parameters
        for a_robinhood_ticker in config[ 'ticker_list' ].values():
            if ( not config[ 'debug_enabled' ] ):
                try:
                    result = rh.get_crypto_info( a_robinhood_ticker )
                    s_inc = result[ 'min_order_quantity_increment' ]
                    p_inc = result[ 'min_order_price_increment' ]
                except:
                    print( 'Failed to get increments from RobinHood.' )
                    exit()
            else:
                s_inc = 0.0001
                p_inc = 0.0001

            self.min_share_increments.update( { a_robinhood_ticker: float( s_inc ) } )
            self.min_price_increments.update( { a_robinhood_ticker: float( p_inc ) } )

        # Initialize the available_cash amount
        self.available_cash = self.get_available_cash()

        print( 'Bot Ready' )

        return

    def cancel_order( self, order_id ):
        if ( not config[ 'debug_enabled' ] ):
            try:
                cancelResult = rh.cancel_crypto_order( order_id )
            except:
                print( 'Got exception canceling order, will try again.' )
                return False

        return True

    def buy( self, ticker ):
        if ( self.available_cash < config[ 'buy_amount_per_trade' ] or self.is_trading_locked ):
            return False

        # Values need to be specified to no more precision than listed in min_price_increments.
        # Truncate to 7 decimal places to avoid floating point problems way out at the precision limit
        price = round( floor( self.data.iloc[ -1 ][ ticker ] / self.min_price_increments[ ticker ] ) * self.min_price_increments[ ticker ], 7 )

        # How much to buy depends on the configuration
        quantity = ( self.available_cash if ( config[ 'buy_amount_per_trade' ] == 0 ) else config[ 'buy_amount_per_trade' ] ) / price
        quantity = round( floor( quantity / self.min_share_increments[ ticker ] ) * self.min_share_increments[ ticker ], 7 )

        print( 'Buying ' + str( ticker ) + ' ' + str( quantity ) + ' at $' + str( price ) )

        if ( config[ 'trades_enabled' ] and not config[ 'debug_enabled' ] ):
            try:
                buy_info = rh.order_buy_crypto_limit( str( ticker ), quantity, price )

                # Add this new asset to our orders
                self.orders[ buy_info[ 'id' ] ] = asset( ticker, quantity, price, buy_info[ 'id' ] )
            except:
                print( 'Got exception trying to buy, aborting.' )
                return False

        return True

    def sell( self, asset ):
        # Do we have enough of this asset to sell?
        if ( asset.quantity <= 0.0 or self.is_trading_locked ):
            return False

        # Values needs to be specified to no more precision than listed in min_price_increments.
        # Truncate to 7 decimal places to avoid floating point problems way out at the precision limit
        price = round( floor( self.data.iloc[ -1 ][ asset.ticker ] / self.min_price_increments[ asset.ticker ] ) * self.min_price_increments[ asset.ticker ], 7 )
        profit = round( ( asset.quantity * price ) - ( asset.quantity * asset.price ), 3 )

        print( 'Selling ' + str( asset.ticker ) + ' ' + str( asset.quantity ) + ' for $' + str( price ) + ' (profit: $' + str( profit ) + ')' )

        if ( config[ 'trades_enabled' ] and not config[ 'debug_enabled' ] ):
            try:
                sell_info = rh.order_sell_crypto_limit( str( asset.ticker ), asset.quantity, price )

                # Mark this asset as sold, the garbage collector (see 'run' method) will remove it from our orders at the next iteration
                self.orders[ asset.order_id ].quantity = 0
            except:
                print( 'Got exception trying to sell, aborting.' )
                return False

        return True

    def run( self ):
        now = datetime.now()
        self.data = self.get_new_data( now )

        # Schedule the next iteration
        Timer( config[ 'minutes_between_updates' ] * 60, self.run ).start()

        # Print state
        print( '-- ' + str( datetime.now().strftime( '%Y-%m-%d %H:%M' ) ) + ' ---------------------' )
        print( self.data.tail() )

        # We don't have enough consecutive data points to decide what to do
        self.is_trading_locked = not self.is_data_consistent( now )

        # Let's make sure we have the correct cash amount available for trading
        if ( self.is_new_order_added or self.available_cash < 0 ):
            self.available_cash = self.get_available_cash()

        if ( len( self.orders ) > 0 ):
            print( '-- Orders -------------------------------' )

            for a_asset in list( self.orders.values() ):
                # Check if any of these open orders on Robinhood are ours
                is_asset_deleted = False

                # Do we have any orders not filled on the platform? (swing/miss)
                if ( self.is_new_order_added ):
                    try:
                        open_orders = rh.get_all_open_crypto_orders()
                    except:
                        print( 'An exception occurred while retrieving list of open orders.' )
                        open_orders = []

                    for a_order in open_orders:
                        if ( a_order[ 'id' ] == a_asset.order_id and self.cancel_order( a_order[ 'id' ] ) ):
                            print( 'Order #' + str( a_order[ 'id' ] ) + ' (' + a_order[ 'side' ] + ' ' + a_asset.ticker + ') was not filled. Cancelled and removed from orders.' )

                            self.orders.pop( a_asset.order_id )
                            is_asset_deleted = True

                    # We're done processing new orders
                    self.is_new_order_added = False

                if ( not is_asset_deleted ):
                    # Print a summary of all our assets
                    print( str( a_asset.ticker ) + ': ' + str( a_asset.quantity ), end = '' )

                    if ( a_asset.quantity > 0.0 ):
                        cost = a_asset.quantity * a_asset.price
                        print( ' | Price: $' + str( round( a_asset.price, 3 ) ) + ' | Cost: $' + str( round( cost, 3 ) ) + ' | Current value: $' + str( round( self.data.iloc[ -1 ][ a_asset.ticker ] * a_asset.quantity, 3 ) ) )
                    else:
                        # We sold this asset during the previous iteration, and it wasn't still pending here above
                        # We can remove it from our orders safely (garbage collector)
                        self.orders.pop( a_asset.order_id )
                        print( "\n" )

                    # Is it time to sell any of them?
                    if (
                        getattr( self.signal, 'sell_' + str(  config[ 'trade_strategies' ][ 'sell' ] ) )( a_asset, self.data ) or

                        # Stop-loss: is the current price below the purchase price by the percentage defined in the config file?
                        ( self.data.iloc[ -1 ][ a_asset.ticker ] < a_asset.price - ( a_asset.price * config[ 'stop_loss_threshold' ] ) )
                    ):
                        self.is_new_order_added = self.sell( a_asset ) or self.is_new_order_added

        # Buy?
        for a_robinhood_ticker in config[ 'ticker_list' ].values():
            if ( getattr( self.signal, 'buy_' + str(  config[ 'trade_strategies' ][ 'buy' ] ) )( a_robinhood_ticker, self.data ) ):
                self.is_new_order_added = self.buy( a_robinhood_ticker ) or self.is_new_order_added

        # Final status for this iteration
        print( '-- Bot Status ---------------------------' )
        print( 'Buying power: $' + str( self.available_cash ) )

        # Save state
        with open( 'orders.pickle', 'wb' ) as f:
            pickle.dump( self.orders, f )

        self.data.to_pickle( 'dataframe.pickle' )

class checker:
    def __init__(self):
        self.stats_dict = {} # Dictionary to hold stats for each ticker
    def check_price(self,ticker):
        ticker_price = 0 # update with code for a query to robinhood
        return ticker_price
    def update_holdings(self,holdings_df):
        # update the holdings from robinhood.
        return
    def check_order_status(self,order_id): #
        # update the order status from robinhood for the order that is referenced with "order_id".
        return
    def is_data_consistent( self, now ):
        if ( self.data.shape[ 0 ] <= 1 ):
            return False

        # Check for break between now and last sample
        timediff = now - datetime.strptime( self.data.iloc[ -1 ][ 'timestamp' ], '%Y-%m-%d %H:%M' )

        # Not enough data points available or it's been too long since we recorded any data
        if ( timediff.seconds > config[ 'minutes_between_updates' ] * 120 ):
            return False

        # Check for break in sequence of samples to minimum consecutive sample number
        position = len( self.data ) - 1
        if ( position >= self.min_consecutive_samples ):
            for x in range( 0, self.min_consecutive_samples ):
                timediff = datetime.strptime( self.data.iloc[ position - x ][ 'timestamp' ], '%Y-%m-%d %H:%M' ) - datetime.strptime( self.data.iloc[ position - ( x + 1 ) ][ 'timestamp' ], '%Y-%m-%d %H:%M' )

                if ( timediff.seconds > config[ 'minutes_between_updates' ] * 120 ):
                    print( 'Holding trades: interruption found in price data.' )
                    return False

        return True
    def get_new_data( self, now ):
        new_row = {}

        self.is_trading_locked = False
        new_row[ 'timestamp' ] = now.strftime( "%Y-%m-%d %H:%M" )

        # Calculate moving averages and RSI values
        for a_kraken_ticker, a_robinhood_ticker in config[ 'ticker_list' ].items():
            if ( not config[ 'debug_enabled' ] ):
                try:
                    result = get_json( 'https://api.kraken.com/0/public/Ticker?pair=' + str( a_kraken_ticker ) ).json()

                    if ( len( result[ 'error' ] ) == 0 ):
                        new_row[ a_robinhood_ticker ] = round( float( result[ 'result' ][ a_kraken_ticker ][ 'a' ][ 0 ] ), 3 )
                except:
                    print( 'An exception occurred retrieving prices.' )
                    self.is_trading_locked = True
                    return self.data
            else:
                new_row[ a_robinhood_ticker ] = round( float( randint( 10, 100 ) ), 3 )

            self.data = self.data.append( new_row, ignore_index = True )

            # If the Kraken API is overloaded, they freeze the values it returns
            if ( ( self.data.tail( 4 )[ a_robinhood_ticker ].to_numpy()[ -1 ] == self.data.tail( 4 )[ a_robinhood_ticker ].to_numpy() ).all() ):
                print( 'Repeating values detected for ' + str( a_robinhood_ticker ) + '. Ignoring data point.' )
                self.data = self.data[:-1]
            elif ( self.data.shape[ 0 ] > 0 ):
                self.data[ a_robinhood_ticker + '_SMA_F' ] = self.data[ a_robinhood_ticker ].shift( 1 ).rolling( window = config[ 'moving_average_periods' ][ 'sma_fast' ] ).mean()
                self.data[ a_robinhood_ticker + '_SMA_S' ] = self.data[ a_robinhood_ticker ].shift( 1 ).rolling( window = config[ 'moving_average_periods' ][ 'sma_slow' ] ).mean()
                self.data[ a_robinhood_ticker + '_RSI' ] = RSI( self.data[ a_robinhood_ticker ].values, timeperiod = config[ 'rsi_period' ] )
                self.data[ a_robinhood_ticker + '_MACD' ], self.data[ a_robinhood_ticker + '_MACD_S' ], macd_hist = MACD( self.data[ a_robinhood_ticker ].values, fastperiod = config[ 'moving_average_periods' ][ 'macd_fast' ], slowperiod = config[ 'moving_average_periods' ][ 'macd_slow' ], signalperiod = config[ 'moving_average_periods' ][ 'macd_signal' ] )

            if ( config[ 'save_charts' ] == True ):
                slice = self.data[ [ a_robinhood_ticker, str( a_robinhood_ticker ) + '_SMA_F', str( a_robinhood_ticker ) + '_SMA_S' ] ]
                fig = slice.plot.line().get_figure()
                fig.savefig( 'chart-' + str( a_robinhood_ticker ).lower() + '-sma.png', dpi = 300 )
                plt.close( fig )

        return self.data
    def get_available_cash( self ):
        available_cash = -1.0

        if ( not config[ 'debug_enabled' ] ):
            try:
                me = rh.account.load_phoenix_account( info=None )
                available_cash = round( float( me[ 'crypto_buying_power' ][ 'amount' ] ) - config[ 'reserve' ], 3 )
            except:
                print( 'An exception occurred while reading available cash amount.' )
        else:
            self.available_cash = randint( 1000, 5000 ) + config[ 'reserve' ]

        return available_cash
    def retrieve_indicators(symbol,
                            screener='crypto',
                            interval=Interval.INTERVAL_15_MINUTES,
                            exchange='BITFINEX'):
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
        coin_data = TA_Handler(symbol=symbol,
                                exchange=exchange,
                                screener=screener,
                                interval=interval,
                                timeout=None
                                )
        result = coin_data.get_analysis().indicators # this result can be parsed for the indicators desired.
        return result
    def get_tradingview_statsdict(self,tickers): #
            stats_dict = {} # will hold technical analysis results for each currency pair. updated every iteration.
            tickers = ['BTC','ETH','DOGE','ETC','SHIB','MATIC','UNI',"XLM",'LTC','LINK']
            coins_with_base = [str(str(coin)+'USD') for coin in tickers]
            for ticker in coins_with_base: # loop through each currency pair.
                res = checker.retrieve_indicators(ticker) #*get the technical analysis results for the coin designated by the variable: "ticker"
                # res contains the indicators for the ticker
                stats_dict[ticker] = res # add results to our stats dictionary
                if simulate_pausing:
                    time.sleep(random.randint(1,3)) # sleep for a random amount of time between 1 and 3 seconds.
            self.stats_dict = stats_dict # update the dictionary of technical analysis results.







if __name__ == '__main__':
    LittleJohn = trader() # initialize the trader class
    LittleJohn.run() # run the trader class