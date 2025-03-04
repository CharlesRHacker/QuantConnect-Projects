# region imports
from AlgorithmImports import *
from trendCalculator import get_trend
# endregion

class This2024q2wip2(QCAlgorithm):

    def Initialize(self):
        
        self.SetStartDate(2024, 1, 1)
        self.SetEndDate(2024, 4, 1)
        self.SetCash(1000000)
        
        # Universe selection
        self.rebalanceTime = self.Time
        self.AddUniverse(self.CoarseFilter, self.FineFilter)
        #self.AddEquity("WDC", Resolution.Hour)
        self.UniverseSettings.Resolution = Resolution.Hour
        
        # Debugging and logging
        #self.plotting = False
        #self.logging = False
        self.plotting = True
        self.logging = True
        
        # indicator parameters
        self.sma_slow_length = 29 #self.get_parameter("slow_length") # the length in days of the slow moving average
        self.sma_fast_length = 12 #self.get_parameter("fast_length") # the length in days of the fast moving average
        self.trend_sma_length = 100 # the length in days of the trend moving average
        self.ATR_multiplier = 1 # the multiplier for the ATR for the slow SMA bands
        self.price_rolling_length = 35 * 7 #int(self.get_parameter("price_rolling")) * 7 # the length in hours of price data to hold
        self.aroon_threshold = 70 #int(self.get_parameter("aroon_threshold"))
        
        # Trend parameters
        self.trend_threshold = .3 #float(self.get_parameter("trend_threshold")) # minimum trend either direction to enter trade
        self.trend_length = self.price_rolling_length # length of rolling price data to check for trend in hours
        self.order = 5 # for trend calculation purposes
        self.k = 2 # for trend calculation purposes
        self.leading_direction_band_multiply = 1.25 #float(self.get_parameter("leading_band"))  # multiplier for leading direction band
        
        # Risk management parameters
        self.price_smoothing = 2
        self.rebuy_period = [7*7, 10*7] # minimum and maximum period in which to re-enter after trailing stop in hours
        self.trailing_stop = .08 #float(self.get_parameter("trailing_stop")) # percent value of trailing stop
        self.trailing_atr_multiplier = 2.5
        self.stop_loss = 1
        self.take_profit = 1
        self.short_trailing_stop = .08
        self.days_breaking_multiplier = 6 #int(self.get_parameter("days_breaking"))
        self.days_breaking_before_enter = self.days_breaking_multiplier * 7 # used to determine how many days to wait before entering trade after sma break
        self.days_breaking_trend = 40 * 7#int(self.get_parameter("days_breaking_trend")) * 7
        self.rsi_high_threshold = 45 # rsi value to stop out long
        self.rsi_low_threshold = 55 # rsi value to stop out short
        self.rsi_rolling_length = 10 * 7#int(self.get_parameter("rsi_rolling"))# length of rsi rolling window
        self.rsi_order = 10 # for rsi trend calculation
        self.trend_distance = 0 #float(self.get_parameter("trend_distance")) # distance from trend sma to be considered far enough to enter trade
        self.adx_threshold = 30 #int(self.get_parameter("adx_threshold")) # minimum adx value to enter trade
        self.sell_rsi_margin = 15 #int(self.get_parameter("sell_rsi_margin")) # margin for rsi to sell out
        self.rsi_trend_threshold = 1 #float(self.get_parameter("rsi_threshold")) # rsi trend threshold to sell out\
        self.rsi_selling_toggle = True
        self.adx_rolling_length = 35
        self.obv_rolling_length = 45
        self.obv_threshold = 5000000

        # dictionaries to hold indicator data etc for each symbol
        self.activeStocks = set()
        self.sma_slow = {}
        self.sma_slow_consolidators = {}
        self.sma_fast = {}
        self.sma_fast_consolidators = {}
        self.sma_trend = {}
        self.sma_trend_consolidators = {}
        self.price_rolling = {}
        self.sell_prices = {}
        self.cover_prices = {}
        self.ATRS = {}
        self.atr_consolidators = {}
        self.days_breakings = {}
        self.days_breakings_trend = {}
        self.above_below_sma = {}
        self.peak_while_long = {}
        self.peak_while_short = {}
        self.aroons = {}
        self.aroon_consolidators = {}
        self.RSIS = {}
        self.rsi_consolidators = {}
        self.RSI_last_location = {}
        self.rsi_rolling = {}
        self.ADX = {}
        self.adx_consolidators = {}
        self.adx_rolling = {}
        self.obvs = {}
        self.obvs_rolling = {}

        # portfolio management
        self.trade_list = []
        self.max_position_size = .15 #float(self.get_parameter("max_position_size"))   # max position size as a proportion of total portfolio value
        self.bought_dates = {}
        self.days_doing_nothing = 35#35#int(self.get_parameter("days_doing_nothing"))
        self.final_universe_size = 300 #int(self.get_parameter("final_universe_size")) # the number of stocks to hold in the universe
        self.portfolio_weight_bias = 50 #int(self.get_parameter("portfolio_weight_bias")) # the bias for the portfolio weight



    def CoarseFilter(self, coarse):
        # Rebalancing monthly
        if self.Time <= self.rebalanceTime:
            return self.Universe.Unchanged
        
        # rebalance universe every month
        self.rebalanceTime = self.Time + timedelta(days=120)

        # filter top 50 by volume
        sortedByDollarVolume = sorted(coarse, key=lambda x: x.DollarVolume, reverse=True)
        return [x.Symbol for x in sortedByDollarVolume if x.HasFundamentalData][:1000]
    
    def FineFilter(self, fine):
        # filter by top volume (again (redundant for now))
        sortedByDollarVolume= sorted(fine, key=lambda x: x.DollarVolume, reverse=True)
        return [x.Symbol for x in sortedByDollarVolume if x.price > 10 and x.MarketCap > 2000000000 and str(x.Symbol).split()[0] != "SMCI"][:self.final_universe_size]


    def OnSecuritiesChanged(self, changes):
        # region removed securities
        for x in changes.RemovedSecurities:
            self.Liquidate(x.Symbol)
            if x.Symbol in self.activeStocks:
                self.activeStocks.remove(x.Symbol)

        # initialize indicators and data structures for new securities
        for x in changes.AddedSecurities:
            self.activeStocks.add(x.Symbol)

            self.initialize_indicators(x)

    def OnData(self, data: Slice):
        smoothed_price = None

        for symbol in self.activeStocks:
            if not data.ContainsKey(symbol) or data[symbol] is None:
                continue

            

            self.price_rolling[symbol].Add(data[symbol].close)
            self.rsi_rolling[symbol].Add(self.RSIS[symbol].Current.Value)
            self.adx_rolling[symbol].Add(self.ADX[symbol].Current.Value)
            self.obvs_rolling[symbol].Add(self.obvs[symbol].Current.Value)


            obv_trend = get_trend(self, [x for x in self.obvs_rolling[symbol]], self.order, self.k)[2]
            price_trend = get_trend(self, [x for x in self.price_rolling[symbol]], self.order, self.k)[2]
            rsi_trend = get_trend(self, [x for x in self.rsi_rolling[symbol]], self.rsi_order, self.k)[2]

            if self.plotting:
                self.Plot("trend", "obv_trend", obv_trend)
                self.Plot("trend", "price_trend", price_trend)
                self.Plot("trend", "rsi_trend", rsi_trend)

            # Adjust sma slow bands based on trend
            if data[symbol].close > self.sma_trend[symbol].Current.Value:
                self.ATR_multiplier_bottom = self.leading_direction_band_multiply * self.ATR_multiplier
                self.ATR_multiplier_top = self.ATR_multiplier
                if self.days_breakings_trend[symbol] <= 0:
                    self.days_breakings_trend[symbol] = 1
                else:
                    self.days_breakings_trend[symbol] += 1
            else:
                self.ATR_multiplier_top = self.leading_direction_band_multiply * self.ATR_multiplier
                self.ATR_multiplier_bottom = self.ATR_multiplier
                if self.days_breakings_trend[symbol] >= 0:
                    self.days_breakings_trend[symbol] = -1
                else:
                    self.days_breakings_trend[symbol] -= 1

            # check if fast sma is above or below slow sma
            if self.sma_fast[symbol].Current.Value > self.sma_slow[symbol].Current.Value + self.ATR_multiplier_top * self.ATRS[symbol].Current.Value:
                relation = 1
            elif self.sma_fast[symbol].Current.Value < self.sma_slow[symbol].Current.Value - self.ATR_multiplier_bottom * self.ATRS[symbol].Current.Value:
                relation = -1
            else:
                relation = 0
            # If recently crossed above slow sma band, initiate count for how many days it has been above
            if relation == 1 and self.above_below_sma[symbol] == 0 and self.days_breakings[symbol] <=0 and not self.Portfolio[symbol].IsLong:
                self.Liquidate(symbol)
                self.trade_list = [x for x in self.trade_list if x[0] != symbol]
                if self.logging:
                    self.Log("Liquidating as relation is 1 and crossed above initiating count for symbol: " + str(symbol))
                    self.Log("sma_fast: " + str(self.sma_fast[symbol].Current.Value) + " sma_slow top band: " + str(self.sma_slow[symbol].Current.Value + self.ATR_multiplier_top * self.ATRS[symbol].Current.Value))
                    self.Log("days above trend: " + str(self.days_breakings_trend[symbol]))
                self.days_breakings[symbol] = 1
                self.sell_prices[symbol] = None
                self.cover_prices[symbol] = None
                self.peak_while_long[symbol] = None
                self.peak_while_short[symbol] = None
            # If recently crossed below slow sma band, initiate count for how many days it has been below
            elif relation == -1 and self.above_below_sma[symbol] == 0 and self.days_breakings[symbol] >=0 and not self.Portfolio[symbol].IsShort:
                self.Liquidate(symbol)
                self.trade_list = [x for x in self.trade_list if x[0] != symbol]
                if self.logging:
                    self.Log("Liquidating as relation is -1 and crossed below initiating count for symbol: " + str(symbol))
                    #self.Log("* setting days_breakings to -1")
                    self.Log("sma_fast: " + str(self.sma_fast[symbol].Current.Value) + " sma_slow bottom band: " + str(self.sma_slow[symbol].Current.Value - self.ATR_multiplier_bottom * self.ATRS[symbol].Current.Value))
                    self.Log("days below trend: " + str(self.days_breakings_trend[symbol]))
                self.days_breakings[symbol] = -1
                self.cover_prices[symbol] = None
                self.sell_prices[symbol] = None
                self.peak_while_long[symbol] = None
                self.peak_while_short[symbol] = None
            # if no band crosses...
            else:
                # if long, check for trailing stop
                if self.Portfolio[symbol].IsLong:
                    self.long_sell_signal(symbol, data, obv_trend, rsi_trend)
                    
                # if short...
                elif self.Portfolio[symbol].IsShort:
                    self.short_cover_signal(symbol, data, obv_trend, rsi_trend)

            # if band crosses, check if enough days have passed to enter trade
            if self.days_breakings[symbol] != 0:
                if self.days_breakings[symbol] > 0:
                    self.long_days_breaking_update(symbol, data, obv_trend, rsi_trend, price_trend)
                elif self.days_breakings[symbol] < 0:
                    self.short_days_breaking_update(symbol, data, obv_trend, rsi_trend, price_trend)
            # if stopped out, check if price is above slow sma and fast sma and reenter trade
            self.reenter_long(symbol, data, obv_trend, price_trend)
            
            # if stopped out, check if price is below slow sma and fast sma and reenter trade
            self.reenter_short(symbol, data, obv_trend, price_trend)

            # update above/below sma relation and sell/cover tiemouts
            self.above_below_sma[symbol] = relation
            if self.sell_prices[symbol] != None:
                self.sell_prices[symbol][0] += 1
            if self.cover_prices[symbol] != None:
                self.cover_prices[symbol][0] += 1
                

                 
            if self.plotting :
                # plot if long, short, or neutral:
                self.Plot("quantity", "quantity", self.Portfolio[symbol].Quantity)
                self.Plot("above/below sma", "above/below sma", self.above_below_sma[symbol])
                self.Plot("sma", "Short", self.sma_fast[symbol].Current.Value)
                self.Plot("sma", "Long", self.sma_slow[symbol].Current.Value)
                #self.Plot("sma", "day_long sma", self.day_sma_slow.Current.Value)
                self.Plot("sma", "slow_lower_band", self.sma_slow[symbol].Current.Value - self.ATR_multiplier_bottom * self.ATRS[symbol].Current.Value)
                self.Plot("sma", "slow_upper_band", self.sma_slow[symbol].Current.Value + self.ATR_multiplier_top * self.ATRS[symbol].Current.Value)
                self.Plot("price", "trend", self.sma_trend[symbol].Current.Value)
                self.Plot("price", "price", data[symbol].Close)
                self.Plot("atr", "atr", self.ATRS[symbol].Current.Value)
                self.Plot("days_breaking", "days_breaking",self.days_breakings[symbol])
                if self.peak_while_short[symbol] != None:
                    self.Plot("price", "peak_while_short", self.peak_while_short[symbol])
                self.Plot("days_breakings_trend", "days_breakings_trend", self.days_breakings_trend[symbol])
                self.Plot("aroon", "aroon_up", self.aroons[symbol].AroonUp.Current.Value)
                self.Plot("aroon", "aroon_down", self.aroons[symbol].AroonDown.Current.Value)
                self.Plot("rsi", "rsi", self.RSIS[symbol].Current.Value)
                self.Plot("adx", "adx", self.ADX[symbol].Current.Value)
                if self.RSI_last_location[symbol] != None:
                    self.Plot("rsi_locale", "rsi_last_location", self.RSI_last_location[symbol])
        
        self.trade_logic()

    def initialize_indicators(self, x):
        self.sma_slow[x.Symbol] = DoubleExponentialMovingAverage(self.sma_slow_length)
        self.sma_slow_consolidators[x.Symbol] = TradeBarConsolidator(timedelta(days=1))
        self.register_indicator(x.Symbol, self.sma_slow[x.Symbol], self.sma_slow_consolidators[x.Symbol])

        self.sma_fast[x.Symbol] = DoubleExponentialMovingAverage(self.sma_fast_length)
        self.sma_fast_consolidators[x.Symbol] = TradeBarConsolidator(timedelta(days=1))
        self.register_indicator(x.Symbol, self.sma_fast[x.Symbol], self.sma_fast_consolidators[x.Symbol])

        self.aroons[x.Symbol] = AroonOscillator(14, 14)
        self.aroon_consolidators[x.Symbol] = TradeBarConsolidator(timedelta(days=1))
        self.register_indicator(x.Symbol, self.aroons[x.Symbol], self.aroon_consolidators[x.Symbol])

        self.ATRS[x.Symbol] = AverageTrueRange(14)
        self.atr_consolidators[x.Symbol] = TradeBarConsolidator(timedelta(days=1))
        self.register_indicator(x.Symbol, self.ATRS[x.Symbol], self.atr_consolidators[x.Symbol])

        self.RSIS[x.Symbol] = RelativeStrengthIndex(14)
        self.rsi_consolidators[x.Symbol] = TradeBarConsolidator(timedelta(days=1))
        self.register_indicator(x.Symbol, self.RSIS[x.Symbol], self.rsi_consolidators[x.Symbol])

        self.ADX[x.Symbol] = AverageDirectionalIndex(14)
        self.adx_consolidators[x.Symbol] = TradeBarConsolidator(timedelta(days=1))
        self.register_indicator(x.Symbol, self.ADX[x.Symbol], self.adx_consolidators[x.Symbol])

        self.sma_trend[x.Symbol] = ExponentialMovingAverage(self.trend_sma_length)
        self.sma_trend_consolidators[x.Symbol] = TradeBarConsolidator(timedelta(days=1))
        self.register_indicator(x.Symbol, self.sma_trend[x.Symbol], self.sma_trend_consolidators[x.Symbol])

        self.obvs[x.Symbol] = self.obv(x.Symbol)
        self.warm_up_indicator(x.Symbol, self.obvs[x.Symbol])

        self.price_rolling[x.Symbol] = RollingWindow[float](self.price_rolling_length)
        self.adx_rolling[x.Symbol] = RollingWindow[float](self.adx_rolling_length)
        self.obvs_rolling[x.Symbol] = RollingWindow[float](self.obv_rolling_length)
        self.above_below_sma[x.Symbol] = 0
        self.peak_while_long[x.Symbol] = None
        self.peak_while_short[x.Symbol] = None
        self.sell_prices[x.Symbol] = None
        self.cover_prices[x.Symbol] = None
        self.days_breakings[x.Symbol] = 0
        self.days_breakings_trend[x.Symbol] = 0
        self.RSI_last_location[x.Symbol] = None
        self.rsi_rolling[x.Symbol] = RollingWindow[float](self.rsi_rolling_length)
            

        history = self.History[TradeBar](x.Symbol, int(1.5 * self.trend_sma_length) + int(1.5 * self.days_breaking_trend), Resolution.Daily)
        
        # populate indicators and rolling windows with historical data and check for days above trend and for 
        # crossovers that happened before the algorithm started
        count = 0

        for bar in history:

            if count <= int(1.5*self.trend_sma_length):
                self.sma_trend[x.Symbol].Update(bar.EndTime, bar.Close)
                self.sma_fast[x.Symbol].Update(bar.EndTime, bar.Close)
                self.sma_slow[x.Symbol].Update(bar.EndTime, bar.Close)
                self.aroons[x.Symbol].Update(bar)
                self.RSIS[x.Symbol].Update(bar.EndTime, bar.Close)
                self.ADX[x.Symbol].Update(bar)
                self.ATRS[x.Symbol].Update(bar)
                self.obvs_rolling[x.Symbol].Add(self.obvs[x.Symbol].Current.Value)

            else:
                self.price_rolling[x.Symbol].Add(bar.Close)
                self.rsi_rolling[x.Symbol].Add(self.RSIS[x.Symbol].Current.Value)
                self.adx_rolling[x.Symbol].Add(self.ADX[x.Symbol].Current.Value)
                self.obvs_rolling[x.Symbol].Add(self.obvs[x.Symbol].Current.Value)

                self.sma_trend[x.Symbol].Update(bar.EndTime, bar.Close)
                self.sma_fast[x.Symbol].Update(bar.EndTime, bar.Close)
                self.sma_slow[x.Symbol].Update(bar.EndTime, bar.Close)
                self.aroons[x.Symbol].Update(bar)
                self.RSIS[x.Symbol].Update(bar.EndTime, bar.Close)
                self.ADX[x.Symbol].Update(bar)
                self.ATRS[x.Symbol].Update(bar)

                if bar.Close > self.sma_trend[x.Symbol].Current.Value:
                    ATR_multiplier_bottom = self.leading_direction_band_multiply * self.ATR_multiplier
                    ATR_multiplier_top = self.ATR_multiplier
                    if self.days_breakings_trend[x.Symbol] <= 0:
                        self.days_breakings_trend[x.Symbol] = 1
                    else:
                        self.days_breakings_trend[x.Symbol] += 7
                else:
                    ATR_multiplier_top = self.leading_direction_band_multiply * self.ATR_multiplier
                    ATR_multiplier_bottom = self.ATR_multiplier
                    if self.days_breakings_trend[x.Symbol] >= 0:
                        self.days_breakings_trend[x.Symbol] = -1
                    else:
                        self.days_breakings_trend[x.Symbol] -= 7
                
                sma_slow_low = self.sma_slow[x.Symbol].Current.Value - ATR_multiplier_bottom * self.ATRS[x.Symbol].Current.Value
                sma_slow_high = self.sma_slow[x.Symbol].Current.Value + ATR_multiplier_top * self.ATRS[x.Symbol].Current.Value

                if self.sma_fast[x.Symbol].Current.Value > sma_slow_high:
                    relation = 1
                elif self.sma_fast[x.Symbol].Current.Value < sma_slow_low:
                    relation = -1
                else:
                    relation = 0

                if relation == 1 and self.above_below_sma[x.Symbol] == 0 and self.days_breakings[x.Symbol] <=0 and bar.close > self.sma_trend[x.Symbol].Current.Value:
                    self.days_breakings[x.Symbol] = 1
                    #self.Log("in history, setting days breaking to 1")

                elif relation == -1 and self.above_below_sma[x.Symbol] == 0 and self.days_breakings[x.Symbol] >=0 and bar.close < self.sma_trend[x.Symbol].Current.Value:
                    self.days_breakings[x.Symbol] = -1
                    #self.Log("in history, setting days breaking to -1")
                
                if self.days_breakings[x.Symbol] != 0:
                    if self.days_breakings[x.Symbol] > 0:
                        if self.sma_fast[x.Symbol].Current.Value > self.sma_slow[x.Symbol].Current.Value:
                            #if self.RSIS[x.Symbol].Current.Value > 50:
                            
                            self.days_breakings[x.Symbol] += 1
                        else:
                            self.days_breakings[x.Symbol] = 0
                    elif self.days_breakings[x.Symbol] < 0:
                        if self.sma_fast[x.Symbol].Current.Value < self.sma_slow[x.Symbol].Current.Value:
                            #if self.RSIS[x.Symbol].Current.Value < 50:
                            
                            self.days_breakings[x.Symbol] -= 1
                        else:
                            self.days_breakings[x.Symbol] = 0
                
                self.above_below_sma[x.Symbol] = relation
            count += 1

    def long_sell_signal(self, symbol, data, obv_trend, rsi_trend):

        # smooth price data to avoid short whipsaws
        smoothed_price = []
        for j in range(self.price_smoothing):
            smoothed_price.append(self.price_rolling[symbol][j])
        smoothed_price = sum(smoothed_price)/self.price_smoothing

        # update the peak while long for trailing stop logic and check if trailing stop is hit
        self.peak_while_long[symbol] = max(self.peak_while_long[symbol], data[symbol].close) if self.peak_while_long[symbol] != None else data[symbol].close
        #if smoothed_price/self.peak_while_long[symbol] < (1-self.trailing_stop):
        if smoothed_price < self.peak_while_long[symbol] - (self.trailing_atr_multiplier*self.ATRS[symbol].Current.Value):
            self.Liquidate(symbol)
            self.trade_list = [x for x in self.trade_list if x[0] != symbol]
            if self.logging:
                self.Log("liquidating long trailing stop, smoothed_price: " + str(smoothed_price) + " peak_while_long: " + str(self.peak_while_long[symbol]) + " for symbol: " + str(symbol))
                
            self.sell_prices[symbol] = [0, data[symbol].close]
            position = 0
            self.peak_while_long[symbol] = None
        
        # check for overbought
        if self.RSIS[symbol].Current.Value < self.rsi_high_threshold and self.RSI_last_location[symbol] == "1":
            if self.logging:
                self.Log("liquidating long overbought, rsi: " + str(self.RSIS[symbol].Current.Value) + " for symbol: " + str(symbol))
            self.Liquidate(symbol)
            self.trade_list = [x for x in self.trade_list if x[0] != symbol]
            self.peak_while_long[symbol] = None
            self.sell_prices[symbol] = [0, data[symbol].close]
        
        if self.RSIS[symbol].Current.Value < self.rsi_high_threshold and self.RSIS[symbol].Current.Value > self.rsi_low_threshold:
            self.RSI_last_location[symbol] = "0"
        elif self.RSIS[symbol].Current.Value >= self.rsi_high_threshold:
            self.RSI_last_location[symbol] = "1"
        elif self.RSIS[symbol].Current.Value <= self.rsi_low_threshold:
            self.RSI_last_location[symbol] = "-1"

        # check if rsi trend hints at reversal sell out
        # consolidate rsi_rolling to groups of 60

        if self.plotting:
            self.Plot("trend", "rsi_trend", rsi_trend)
            self.Log("rsi_trend: " + str(rsi_trend) + " for symbol: " + str(symbol))
        if rsi_trend < -self.rsi_trend_threshold and self.RSIS[symbol].Current.Value < 55:
            if self.rsi_selling_toggle and self.RSIS[symbol].Current.Value < 50:
                self.Liquidate(symbol)
                if self.logging: 
                    self.Log("liquidating long rsi trend, rsi_trend: " + str(rsi_trend) + " for symbol: " + str(symbol))
                self.trade_list = [x for x in self.trade_list if x[0] != symbol]
                self.peak_while_long[symbol] = None
                self.sell_prices[symbol] = [0, data[symbol].close]

        # check for rsi dip below 55
        if self.RSIS[symbol].Current.Value < 50 - self.sell_rsi_margin:
            if self.rsi_selling_toggle:
                if self.logging:
                    self.Log("liquidating long rsi dip, rsi: " + str(self.RSIS[symbol].Current.Value) + " for symbol: " + str(symbol))
                    rsi_arr = [x for x in self.rsi_rolling[symbol]]
                    self.Log("rsi_arr: " + str(rsi_arr))    
                self.Liquidate(symbol)
                self.trade_list = [x for x in self.trade_list if x[0] != symbol]
                self.peak_while_long[symbol] = None
                self.sell_prices[symbol] = [0, data[symbol].close]

        # obv sell signal

        if obv_trend <= -self.obv_threshold:
            self.Plot("obv trend in sell criteria", "sell signal obv trend", obv_trend)
            if self.logging:
                self.Log("liquidating long obv trend, obv_trend: " + str(obv_trend) + " for symbol: " + str(symbol))
            self.Liquidate(symbol)
            self.trade_list = [x for x in self.trade_list if x[0] != symbol]
            self.peak_while_long[symbol] = None
            self.sell_prices[symbol] = [0, data[symbol].close]
        
        # stop loss
        if data[symbol].close < self.Portfolio[symbol].AveragePrice * (1 - self.stop_loss):
            self.Liquidate(symbol)
            self.trade_list = [x for x in self.trade_list if x[0] != symbol]
            self.peak_while_long[symbol] = None
            self.sell_prices[symbol] = [0, data[symbol].close]
            if self.logging:
                self.Log("liquidating long stop loss, stop_loss: " + str(self.stop_loss) + " for symbol: " + str(symbol))

        # take profit
        if data[symbol].close > self.Portfolio[symbol].AveragePrice * (1 + self.take_profit):
            self.Liquidate(symbol)
            self.trade_list = [x for x in self.trade_list if x[0] != symbol]
            self.peak_while_long[symbol] = None
            self.sell_prices[symbol] = [0, data[symbol].close]
            if self.logging:
                self.Log("liquidating long take profit, take_profit: " + str(self.take_profit) + " for symbol: " + str(symbol))

    def short_cover_signal(self, symbol, data, obv_trend, rsi_trend):
        # smooth price data to avoid short whipsaws
        smoothed_price = []
        for j in range(self.price_smoothing):
            smoothed_price.append(self.price_rolling[symbol][j])
        smoothed_price = sum(smoothed_price)/self.price_smoothing

        # update the peak while short for trailing stop logic and check if trailing stop is hit
        self.peak_while_short[symbol] = min(self.peak_while_short[symbol], data[symbol].close) if self.peak_while_short[symbol] != None else data[symbol].close
        
        #if smoothed_price/self.peak_while_short[symbol] > (1+ self.short_trailing_stop):
        if smoothed_price > self.peak_while_short[symbol] + (self.trailing_atr_multiplier*self.ATRS[symbol].Current.Value):
            self.Liquidate(symbol)
            self.trade_list = [x for x in self.trade_list if x[0] != symbol]
            if self.logging:
                self.Log("liquidating short trailing stop, smoothed_price: " + str(smoothed_price) + " peak_while_short: " + str(self.peak_while_short[symbol]) + " for symbol: " + str(symbol))
                
            self.cover_prices[symbol] = [0, data[symbol].close]
            position = 0
            self.peak_while_short[symbol] = None

        
        # check for oversold
        if self.RSIS[symbol].Current.Value > self.rsi_low_threshold and self.RSI_last_location[symbol] == "-1":
            if self.rsi_selling_toggle:
                self.Liquidate(symbol)
                if self.logging:
                    self.Log("liquidating short oversold, rsi: " + str(self.RSIS[symbol].Current.Value) + " for symbol: " + str(symbol))
                self.trade_list = [x for x in self.trade_list if x[0] != symbol]
                self.peak_while_long[symbol] = None
                self.cover_prices[symbol] = [0, data[symbol].close]
            
        if self.RSIS[symbol].Current.Value < self.rsi_high_threshold and self.RSIS[symbol].Current.Value > self.rsi_low_threshold:
            self.RSI_last_location[symbol] = "0"
        elif self.RSIS[symbol].Current.Value >= self.rsi_high_threshold:
            self.RSI_last_location[symbol] = "1"
        elif self.RSIS[symbol].Current.Value <= self.rsi_low_threshold:
            self.RSI_last_location[symbol] = "-1"
        
        # check if rsi trend hints at reversal sell out
        # consolidate rsi_rolling to groups of 60

        if rsi_trend > self.rsi_trend_threshold and self.RSIS[symbol].Current.Value > 45:
            if self.rsi_selling_toggle and self.RSIS[symbol].Current.Value > 50:
                if self.logging:
                    self.Log("liquidating short rsi trend, rsi_trend: " + str(rsi_trend) + " for symbol: " + str(symbol))
                self.Liquidate(symbol)
                self.trade_list = [x for x in self.trade_list if x[0] != symbol]
                self.peak_while_short[symbol] = None
                self.cover_prices[symbol] = [0, data[symbol].close]
        
        # check for rsi spike above 45
        if self.RSIS[symbol].Current.Value > 50 + self.sell_rsi_margin:
            if self.rsi_selling_toggle:
                if self.logging:
                    self.Log("liquidating short rsi spike, rsi: " + str(self.RSIS[symbol].Current.Value) + " for symbol: " + str(symbol))
                self.Liquidate(symbol)
                self.trade_list = [x for x in self.trade_list if x[0] != symbol]
                self.peak_while_short[symbol] = None
                self.cover_prices[symbol] = [0, data[symbol].close]

         # obv cover signal
        if obv_trend > self.obv_threshold:
            if self.logging:
                self.Log("liquidating long obv trend, obv_trend: " + str(obv_trend) + " for symbol: " + str(symbol))
            self.Liquidate(symbol)
            self.trade_list = [x for x in self.trade_list if x[0] != symbol]
            self.peak_while_long[symbol] = None
            self.sell_prices[symbol] = [0, data[symbol].close]

        # stop loss
        if data[symbol].close > self.Portfolio[symbol].AveragePrice * (1 + self.stop_loss):
            self.Liquidate(symbol)
            self.trade_list = [x for x in self.trade_list if x[0] != symbol]
            self.peak_while_short[symbol] = None
            self.cover_prices[symbol] = [0, data[symbol].close]

        # take profit
        if data[symbol].close < self.Portfolio[symbol].AveragePrice * (1 - self.take_profit):
            self.Liquidate(symbol)
            self.trade_list = [x for x in self.trade_list if x[0] != symbol]
            self.peak_while_short[symbol] = None
            self.cover_prices[symbol] = [0, data[symbol].close]
            if self.logging:
                self.Log("liquidating short take profit, take_profit: " + str(self.take_profit) + " for symbol: " + str(symbol))

    def long_days_breaking_update(self, symbol, data, obv_trend, rsi_trend, price_trend):

        if self.sma_fast[symbol].Current.Value > self.sma_slow[symbol].Current.Value:
            if self.RSIS[symbol].Current.Value > 50:
                self.days_breakings[symbol] += 1
            #self.Log("*incrementing days_breakings")
            if self.days_breakings[symbol] >= self.days_breaking_before_enter and self.days_breakings_trend[symbol] >= self.days_breaking_trend:
                if price_trend > self.trend_threshold and self.aroons[symbol].AroonUp.Current.Value > self.aroon_threshold and self.aroons[symbol].AroonUp.Current.Value > self.aroons[symbol].AroonDown.Current.Value: 
                    # check if adx has been increasing
                    max_adx = max([x for x in self.adx_rolling[symbol]])
                    current_adx = self.ADX[symbol].Current.Value

                    if current_adx >= max_adx * .95 and self.ADX[symbol].Current.Value >= self.adx_threshold and self.days_breakings_trend[symbol] >= self.days_breaking_trend:
                        if obv_trend > self.obv_threshold:
                            self.days_breakings[symbol] = 0
                            self.Log("*buy, aroonup: " + str(self.aroons[symbol].AroonUp.Current.Value) + " aroondown: " + str(self.aroons[symbol].AroonDown.Current.Value) + " adx: " + str(self.ADX[symbol].Current.Value) + "days breaking trend:  " + str(self.days_breakings_trend[symbol]) + "current adx: " + str(current_adx) + "max_adx: " + str(max_adx) + " for: " + str(symbol))
                            amount_above = data[symbol].close - self.sma_slow[symbol].Current.Value
                            self.trade_list.append([symbol, price_trend/data[symbol].price, amount_above/data[symbol].price, self.aroons[symbol].AroonUp.Current.Value, self.ADX[symbol].Current.Value, 1])
                            
                            self.peak_while_long[symbol] = data[symbol].close
                        
                    else:
                        self.Log("decided not to buy: " + " current adx: " + str(current_adx) + " max_adx: " + str(max_adx) + "days breaking trend:  " + str(self.days_breakings_trend[symbol]) + " for: " + str(symbol))
        else:
            self.days_breakings[symbol] = 0
            #self.Log("* reset to 0 as below slow sma")

    def short_days_breaking_update(self, symbol, data, obv_trend, rsi_trend, price_trend):

        if self.sma_fast[symbol].Current.Value < self.sma_slow[symbol].Current.Value:
            if self.RSIS[symbol].Current.Value < 50:
                self.days_breakings[symbol] -= 1
            #self.Log("not shorting yet, current days breaking: " + str(self.days_breakings[symbol]) + " needs to reach: " + str(-self.days_breaking_before_enter))
            if self.days_breakings[symbol] <= -self.days_breaking_before_enter and self.days_breakings_trend[symbol] <= -self.days_breaking_trend:
                
                if price_trend < -self.trend_threshold and self.aroons[symbol].AroonDown.Current.Value > self.aroon_threshold and self.aroons[symbol].AroonDown.Current.Value > self.aroons[symbol].AroonUp.Current.Value:
                    min_adx = min([x for x in self.adx_rolling[symbol]])
                    current_adx = self.ADX[symbol].Current.Value
                    
                    self.Plot("adx", "min_adx", min_adx)
                    
                    if current_adx <= min_adx * 1.05 and self.ADX[symbol].Current.Value >= self.adx_threshold and self.days_breakings_trend[symbol] <= -self.days_breaking_trend:
                        if obv_trend < 1000000:
                            self.days_breakings[symbol] = 0
                            self.Log("*short, aroondown: " + str(self.aroons[symbol].AroonDown.Current.Value) + " aroonup: " + str(self.aroons[symbol].AroonUp.Current.Value) + " adx: " + str(self.ADX[symbol].Current.Value) + "days breaking trend:  " + str(self.days_breakings_trend[symbol]) + " for: " + str(symbol))
                            
                            amount_below = self.sma_slow[symbol].Current.Value - data[symbol].close
                            self.trade_list.append([symbol, abs(price_trend)/data[symbol].price, amount_below/data[symbol].price, self.aroons[symbol].AroonDown.Current.Value, self.ADX[symbol].Current.Value, -1])
                            
                            self.peak_while_short[symbol] = data[symbol].close
                    else:
                        self.Log("decided not to short: " + " current adx: " + str(current_adx) + " min_adx: " + str(min_adx) + "days breaking trend:  " + str(self.days_breakings_trend[symbol]) + " for: " + str(symbol))
                else:
                    self.Log("not shorting yet, current days breaking: " + str(self.days_breakings[symbol]) + " needs to reach: " + str(-self.days_breaking_before_enter))
        else:
            self.days_breakings[symbol] = 0
            
    def reenter_long(self, symbol, data, obv_trend, price_trend):
        if self.sell_prices[symbol] is not None and self.sell_prices[symbol][0] > self.rebuy_period[0] and self.sell_prices[symbol][0] < self.rebuy_period[1] and not self.Portfolio[symbol].IsShort and not self.Portfolio[symbol].IsLong:
            if data[symbol].close > self.sell_prices[symbol][1] and data[symbol].close > self.sma_fast[symbol].Current.Value and data[symbol].close > self.sma_slow[symbol].Current.Value + self.ATR_multiplier_top * self.ATRS[symbol].Current.Value:
                if obv_trend > self.obv_threshold:
                    if price_trend > self.trend_threshold and self.aroons[symbol].AroonUp.Current.Value > self.aroon_threshold and self.aroons[symbol].AroonUp.Current.Value > self.aroons[symbol].AroonDown.Current.Value and self.ADX[symbol].Current.Value >= self.adx_threshold and self.RSIS[symbol].Current.Value >= 55:
                        if self.RSIS[symbol].Current.Value > 50 and self.ADX[symbol].Current.Value >= .95 * max([x for x in self.adx_rolling[symbol]]):
                            amount_above = data[symbol].close - self.sma_slow[symbol].Current.Value
                            self.trade_list.append([symbol, price_trend/data[symbol].price, amount_above/data[symbol].price, self.aroons[symbol].AroonUp.Current.Value, self.ADX[symbol].Current.Value, 1])
                            self.peak_while_long[symbol] = data[symbol].close
                            self.sell_prices[symbol] = None

    def reenter_short(self, symbol, data, obv_trend, price_trend):
        if self.cover_prices[symbol] is not None and self.cover_prices[symbol][0] > self.rebuy_period[0] and self.cover_prices[symbol][0] < self.rebuy_period[1] and not self.Portfolio[symbol].IsShort and not self.Portfolio[symbol].IsLong:
            if data[symbol].close < self.cover_prices[symbol][1] and data[symbol].close < self.sma_fast[symbol].Current.Value and data[symbol].close < self.sma_slow[symbol].Current.Value - self.ATR_multiplier_bottom * self.ATRS[symbol].Current.Value:
                if obv_trend < -1000000:
                    if price_trend < -self.trend_threshold and self.aroons[symbol].AroonDown.Current.Value > self.aroon_threshold and self.aroons[symbol].AroonDown.Current.Value > self.aroons[symbol].AroonUp.Current.Value and self.ADX[symbol].Current.Value >= self.adx_threshold and self.RSIS[symbol].Current.Value <= 45:
                        if self.RSIS[symbol].Current.Value < 50 and self.ADX[symbol].Current.Value <= 1.05 * min([x for x in self.adx_rolling[symbol]]):
                            amount_below = data[symbol].close - self.sma_slow[symbol].Current.Value
                            self.trade_list.append([symbol, price_trend/data[symbol].price, amount_below/data[symbol].price, self.aroons[symbol].AroonDown.Current.Value, self.ADX[symbol].current.Value, -1])
                            if self.logging:
                                self.Log("reentering after stopping out short " + str(symbol))
                            self.peak_while_short[symbol] = data[symbol].close
                            self.cover_prices[symbol] = None
                
    def trade_logic(self):
        
        # add up score for uninvested trades
        total_score = 0
        for trade in self.trade_list:
                total_score += self.portfolio_weight_bias + abs(trade[2] * trade[1] * trade[3] * trade[4])
                trade.append(abs(trade[2] * trade[1] * trade[3] * trade[4]))
        
        # sort trade list by score
        self.trade_list = sorted(self.trade_list, key=lambda x: x[-1], reverse=True)
        
        # invest in trades
        for i in range(len(self.trade_list)):
            trade = self.trade_list[i]
            proportion = (self.portfolio_weight_bias + (trade[2] * trade[1] * trade[3] * trade[4])) / total_score
            margin_left = self.Portfolio.MarginRemaining - 5000
            
            holdings = self.Portfolio.TotalAbsoluteHoldingsCost
            cash_left = self.Portfolio.Cash
            total_potential = holdings + margin_left + cash_left

            if self.logging:
                self.Log("proportion: " + str(proportion) + "holdings " + str(holdings) + " margin_left: " + str(margin_left) + " cash_left: " + str(cash_left) + " total_potential: " + str(total_potential) + " for symbol: " + str(trade[0]))

            if self.plotting and str(trade).split()[0] == "CHWY":
                self.Plot("buy/sell", "holdings", holdings)
                self.Plot("buy/sell", "cash", cash_left)
                self.Plot("buy/sell", "margin", margin_left)
                self.Plot("buy/sell", "potential", total_potential)

            

            quantity = proportion * (max(margin_left, 0) + max(cash_left, 0)) / self.price_rolling[trade[0]][0]
            if self.logging:
                self.Log("first quantity: " + str(quantity) + " for symbol: " + str(trade[0]))

            # if currently invested and amount we want to invest more makes total position size too large, adjust
            if self.Portfolio[trade[0]].Invested:
                if abs(((quantity * self.price_rolling[trade[0]][0]) + abs(self.Portfolio[symbol].quantity) * self.price_rolling[trade[0][0]])/total_potential) > self.max_position_size:
                    #self.Log("quantity value too high, adjusting")
                    quantity = (self.max_position_size * total_potential) / self.price_rolling[trade[0]][0] - abs(self.Portfolio[symbol].quantity)        

            if abs((quantity * self.price_rolling[trade[0]][0])/total_potential) > self.max_position_size:
                #self.Log("quantity value too high, adjusting")
                quantity = (self.max_position_size * total_potential) / self.price_rolling[trade[0]][0]
                quantity = quantity
            
            if self.logging:
                self.Log("final quantity: " + str(quantity) + " for symbol: " + str(trade[0]))

            if self.plotting and str(trade).split()[0] == "CHWY":
                self.Plot("buy/sell", "quantity_value", quantity * self.price_rolling[trade[0]][0])


            if trade[5] == -1:
                order_properties = OrderProperties()
                order_properties.time_in_force = TimeInForce.GOOD_TIL_DATE(self.Time + timedelta(days=2))
                self.limit_order(trade[0], -quantity/2, self.price_rolling[trade[0]][0] *.95, order_properties=order_properties)
                self.bought_dates[trade[0]] = self.Time
            elif trade[5] == 1:
                order_properties = OrderProperties()
                order_properties.time_in_force = TimeInForce.GOOD_TIL_DATE(self.Time + timedelta(days=2))
                self.limit_order(trade[0], quantity, self.price_rolling[trade[0]][0] * 1.05, order_properties=order_properties)
                self.bought_dates[trade[0]] = self.Time
        self.trade_list = []

        keys = list(self.Portfolio.keys())
        sortedByProfit = sorted(keys, key=lambda x: self.Portfolio[x].UnrealizedProfitPercent, reverse=True)

        for i in range(len(sortedByProfit)):
            symbol = sortedByProfit[i]
            if self.Portfolio[symbol].UnrealizedProfit != 0.0:
                
                #if not self.plotting:
                #self.Plot("profit", symbol, self.Portfolio[symbol].UnrealizedProfitPercent)

                margin_left = self.Portfolio.MarginRemaining - 5000
                holdings = self.Portfolio.TotalAbsoluteHoldingsCost
                cash_left = self.Portfolio.Cash
                if cash_left < 0: cash_left = 0
                total_potential = margin_left + cash_left + holdings

                # if less than 15% of total portfolio, and profit is more than 5%, increase position size
                open_orders = self.Transactions.GetOpenOrders(symbol)
                if self.Portfolio[symbol].UnrealizedProfitPercent > .05 and abs(self.Portfolio[symbol].holdings_cost)/total_potential < self.max_position_size * 1.5 and len(open_orders) == 0:
                    quantity =  (self.max_position_size * 1.5 * total_potential - self.Portfolio[symbol].holdings_cost) / self.price_rolling[symbol][0]
                    if quantity * self.price_rolling[symbol][0] > margin_left + cash_left: 
                        quantity = (margin_left + cash_left) / self.price_rolling[symbol][0]

                    if quantity < 0:
                        continue

                    if self.Portfolio[symbol].IsShort:
                        quantity = -quantity/2

                    order_properties = OrderProperties()
                    order_properties.time_in_force = TimeInForce.GOOD_TIL_DATE(self.Time + timedelta(days=2))
                    self.limit_order(symbol, quantity, self.price_rolling[symbol][0] * 1.05, order_properties=order_properties)

                    if self.logging:
                        self.Log("increasing position size for symbol: " + str(symbol) + "profit is: " + str(self.Portfolio[symbol].UnrealizedProfitPercent))

                # if 5 days have passed and profit is less than 1$, liquidate
                if self.bought_dates[symbol] != None:
                    if self.Time - self.bought_dates[symbol] > timedelta(days=self.days_doing_nothing) and self.Portfolio[symbol].UnrealizedProfitPercent < .01:
                        self.Liquidate(symbol)
                        self.bought_dates[symbol] = None
                        self.peak_while_long[symbol] = None
                        self.peak_while_short[symbol] = None
                        self.sell_prices[symbol] = None
                        self.cover_prices[symbol] = None
                        self.trade_list = [x for x in self.trade_list if x[0] != symbol]
                        if self.logging:
                            self.Log("liquidating due to low profit for symbol: " + str(symbol))             

