
from AlgorithmImports import *
import numpy as np

class custom_alpha(AlphaModel):
    def __init__(self, algo):
        algo.Logging = True

        self.min_recent_volume_increase = 3  # Minimum recent volume increase multilier
        self.min_price_spike = .8  # Minimum price spike percentage
        self.min_price_decline = 0.2  # Minimum price decline percentage after spike
        self.stop_loss_pct = 1  # Stop-loss percentage for short positions
        self.take_profit_pct = .75  # Take-profit percentage for short positions

        self.decline_window = 7 # hours to check for rapid decline
        self.incline_window = 18  # hours to check for rapid incline

        self.stay_in_candidate_list = 49  # days to stay in candidate list
        self.split_ratio = .5
        self.volumeBarsDaysSize = 5
        self.volumeBarsDaysSize = self.volumeBarsDaysSize * 7

        self.insight_length = 5

        self.activeStocks = set()

        self.volumes = {}
        self.rolling_prices_incline = {}
        self.rolling_prices_decline = {}
        self.shortCandidates = {}
        self.days_in_candidate_list = {}
        self.hold_times = {}
        self.Bollingers = {}
        self.bollinger_consolidators = {}

        self.ATRS = {}
        self.atr_consolidators = {}
        self.atr_stop_multiplier = 1  # ATR stop multiplier
        self.RSIS = {}
        self.rsi_consolidators = {}

        self.rsis_rolling_windows = {}
        self.rsis_rolling_windows_length = 14

        self.peak_prices = {}

    def Update(self, algo, data):
        insights = []
        
        # Check for shorting and exit opportunities
        for symbol in self.activeStocks:
            if not data.ContainsKey(symbol) or data[symbol] is None:
                continue

            self.rolling_prices_incline[symbol].Add(data[symbol].price)
            self.rolling_prices_decline[symbol].Add(data[symbol].price)
            self.rsis_rolling_windows[symbol].Add(self.RSIS[symbol].Current.Value)
            self.volumes[symbol].Add(data[symbol].Volume)

            if symbol not in self.shortCandidates:
                self.IsShortingCandidate(algo, data, symbol)  
            if algo.Portfolio[symbol].IsShort:  
                if self.IsShortExitCandidate(algo, data, symbol):
                    algo.Log("Covering stock: " + str(symbol) + " at price: " + str(data[symbol].price) + " at time/date: " + str(algo.Time))
                    insights.append(Insight.Price(symbol, timedelta(days=self.insight_length), InsightDirection.Flat, weight = 1))
                    

                
        toremove = []

        for symbol in self.shortCandidates:
            self.shortCandidates[symbol] += 1
            if self.shortCandidates[symbol] >= self.stay_in_candidate_list:
                toremove.append(symbol)
            if self.RapidDecline(algo, data, symbol):
                if self.RSIS[symbol].Current.Value <= min(self.rsis_rolling_windows[symbol])*1.05:
                    algo.Log("shorting stock: " + str(symbol) + " at price: " + str(data[symbol].price) + " at time/date: " + str(algo.Time))
                    insights.append(Insight.Price(symbol, timedelta(days=self.insight_length), InsightDirection.Down, weight = 1))
                    toremove.append(symbol)
                    self.peak_prices[symbol] = data[symbol].price
                else:
                    algo.Log("stock: " + str(symbol) + " failed rsi check: min RSI: " + str(min(self.rsis_rolling_windows[symbol])) + " current RSI: " + str(self.RSIS[symbol].Current.Value))
        for symbol in toremove:
            if symbol in self.shortCandidates:
                self.shortCandidates.pop(symbol)

        # plot profit for each investment
        for symbol in algo.Portfolio.Keys:
            if str(symbol).split()[0] == "EUDA":
                algo.Plot("ATRS", str(symbol), self.ATRS[symbol].Current.Value)
                algo.Plot("price", str(symbol) + "price", self.rolling_prices_incline[symbol][0])
                algo.Plot("price", str(symbol) + "bollingerupper", self.Bollingers[symbol].UpperBand.Current.Value)
                algo.plot("price", str(symbol) + "atrstop", self.peak_prices[symbol] + self.ATRS[symbol].Current.Value * self.atr_stop_multiplier)

        return insights



    def RapidDecline(self, algo, data, symbol):
        # check if stock is in a rapid decline over last x days
        if not data.ContainsKey(symbol) or data[symbol] is None:
            return False
        if not symbol in self.Bollingers:
            return False
        if not self.Bollingers[symbol].IsReady:
            return False

        old_price = max(self.rolling_prices_decline[symbol])
        current_price = data[symbol].price


        
        # current_price < old_price * (1 - self.min_price_decline) and 
        if current_price < old_price * (1-self.min_price_decline): #and current_price < self.Bollingers[symbol].UpperBand.Current.Value:
            algo.Log("HIT, IT'S LOWER, current price less than: " + str(old_price * (1 - self.min_price_decline)) + " for stock: " + str(symbol))
            return True
        algo.Log("max price over last 8 hours " + str(old_price) + " for stock: " + str(symbol))
        algo.Log("current price at time: " + str(current_price) + " for stock: " + str(symbol))
        algo.Log("Looking for a current price less than: " + str(old_price * (1 - self.min_price_decline)) + " for stock: " + str(symbol))

        return False

    def IsShortingCandidate(self, algo, data, symbol):
        # Check for recent volume increase, price spike, and confirmation decline

        # check if stock is ready to analyze
        if not data.ContainsKey(symbol) or data[symbol] is None:
            return 
        if not self.volumes[symbol].IsReady:
            return 
        
        # check for recent volume increase
        # find the median volume over the volumes window and compare to today
        volumesList = []
        for value in self.volumes[symbol]:
            volumesList.append(value)
        median_volume = np.median(volumesList)

        if data[symbol].Volume/median_volume < self.min_recent_volume_increase:
            return 
        algo.Log("volume jump: " + str(data[symbol].Volume / median_volume) + " for stock: " + str(symbol) + " passed")

        prices_list = [x for x in self.rolling_prices_incline[symbol]]

        price_spike_median = np.median(prices_list)

        if data[symbol].price / price_spike_median < 1 + self.min_price_spike:
            return 
        
        algo.Log(str(symbol) + " Passed price spike check, adding to candidate list, spike was: " + str(data[symbol].price / price_spike_median) + " current price is: " + str(data[symbol].price) + " spike median is: " + str(price_spike_median))

        # Add stock to candidates to watch to short
        self.shortCandidates[symbol] = 1
        


    def IsShortExitCandidate(self, algo, data, symbol):
        # Exit on stop-loss or take-profit
        algo.Log("checking shortexits for symbol: " + str(symbol))

        if not data.ContainsKey(symbol) or data[symbol] is None:
            return False
        
        algo.Log("got past data check for symbol: " + str(symbol))

        entry_price = algo.Portfolio[symbol].AveragePrice

        current_price = data[symbol].close
        if current_price <= entry_price * (1 - self.take_profit_pct):
            algo.Log("Take profit hit for stock: " + str(symbol) + " at price: " + str(data[symbol].price) + " at time/date: " + str(algo.Time))
            return True
        elif current_price >= entry_price * (1 + self.stop_loss_pct):
            algo.Log("Stop loss hit for stock: " + str(symbol) + " at price " + str(data[symbol].price) + " at time/date: " + str(algo.Time))
            return True
        else:
            algo.Log("current price: " + str(current_price) + " takeprofit: " + str(entry_price * (1 - self.take_profit_pct)) + " stoploss: " + str(entry_price * (1 + self.stop_loss_pct)) + " for symbol: " + str(symbol))
        if symbol in self.peak_prices: 
            if self.peak_prices[symbol] != None:
                algo.Log("checking atr stop loss for symbol: " + str(symbol))
                if algo.Portfolio[symbol].IsShort:
                    algo.Log("short position, checking atr stop loss for symbol: " + str(symbol))
                    price = self.rolling_prices_incline[symbol][0]
                    if price < self.peak_prices[symbol]:
                        self.peak_prices[symbol] = price
                    if price > self.peak_prices[symbol] + self.atr_stop_multiplier * self.ATRS[symbol].Current.Value:
                        algo.Log("atr stop loss triggereddd")
                        self.peak_prices.pop(symbol)
                        return True
                    else:
                        algo.Log("atr stop loss not triggered: price is: " + str(price) + " peak price is: " + str(self.peak_prices[symbol]) + " atr stop is: " + str(self.peak_prices[symbol] + self.ATRS[symbol].Current.Value * self.atr_stop_multiplier))
        # if rsi is increasing, return true
        if self.RSIS[symbol].Current.Value > min(self.rsis_rolling_windows[symbol])*1.05:
            return True
        return False


    def OnSecuritiesChanged(self, algo, changes):
        # close positions in removed securities
        for x in changes.RemovedSecurities:
            if x.Symbol in self.activeStocks:
                self.activeStocks.remove(x.Symbol)
        
        # can't open positions here since data might not be added correctly yet
        for x in changes.AddedSecurities:
            history_trade_bar = algo.history[TradeBar](x.Symbol, self.volumeBarsDaysSize, Resolution.Hour)
            self.volumes[x.Symbol] = RollingWindow[float](self.volumeBarsDaysSize)
            self.rolling_prices_incline[x.Symbol] = RollingWindow[float](self.incline_window)
            self.rolling_prices_decline[x.Symbol] = RollingWindow[float](self.decline_window)
            
            self.Bollingers[x.Symbol] = BollingerBands(20, 2, MovingAverageType.Simple)
            self.bollinger_consolidators[x.Symbol] = TradeBarConsolidator(timedelta(days=1))
            algo.register_indicator(x.Symbol, self.Bollingers[x.Symbol], self.bollinger_consolidators[x.Symbol])
            
            self.ATRS[x.Symbol] = AverageTrueRange(14)
            self.atr_consolidators[x.Symbol] = TradeBarConsolidator(timedelta(days=1))
            algo.register_indicator(x.Symbol, self.ATRS[x.Symbol], self.atr_consolidators[x.Symbol])

            self.RSIS[x.Symbol] = RelativeStrengthIndex(14)
            self.rsi_consolidators[x.Symbol] = TradeBarConsolidator(timedelta(days=1))
            algo.register_indicator(x.Symbol, self.RSIS[x.Symbol], self.rsi_consolidators[x.Symbol])

            self.rsis_rolling_windows[x.Symbol] = RollingWindow[float](self.rsis_rolling_windows_length)


            for trade_bar in history_trade_bar:
                self.volumes[x.Symbol].Add(trade_bar.Volume)
                self.rolling_prices_incline[x.Symbol].Add(trade_bar.Close)
                self.rolling_prices_decline[x.Symbol].Add(trade_bar.Close)
                self.Bollingers[x.Symbol].Update(trade_bar.EndTime, trade_bar.Close)
                self.ATRS[x.Symbol].Update(trade_bar)
                self.RSIS[x.Symbol].Update(trade_bar.EndTime, trade_bar.Close)
                self.rsis_rolling_windows[x.Symbol].Add(self.RSIS[x.Symbol].Current.Value)
            self.activeStocks.add(x.Symbol)   
