
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
    #!print(self.data.tail()) # results in large output to the terminal.

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
