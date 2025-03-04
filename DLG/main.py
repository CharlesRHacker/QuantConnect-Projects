# region imports
from AlgorithmImports import *
# endregion

class NQStrategy(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2024, 1, 1)
        self.SetEndDate(2024, 2, 1)
        self.SetCash(100000)
        
        # Add continuous futures contract for NQ with proper symbol
        self.nq = self.AddFuture(Futures.Indices.NASDAQ100EMini, 
                                Resolution.Tick, 
                                extendedMarketHours=True)
        self.nq.SetFilter(lambda u: u.FrontMonth())
        
        self._symbol = None  # Will be set when securities change
        
        self.five_min_data = []
        self.last_bar_time = None
        
        self.time1 = []
        self.high = []
        self.low = []
        self.close = []
        
        self.win = 0
        self.loss = 0
        self.bypass = True
        self.bypass1 = True
        self.tpb = False
        self.slb = False
        self.tps = False
        self.sls = False
        self.cum_profit = []
        self.tops = 999999
        self.up = False
        self.down = False
        self.slbe = 999999
        self.topsl = 999999
        self.slbu = 0
        self.bottoms = 0
        self.bottomsh = 0
        self.entryb = 0
        self.entrys = 0
        self.z = 0

        self.start = 90500
        self.end = 93000
        self.rr = .5
        self.endof = 170000

        self.no_entry_reasons = {}
        
        # Set realistic trading costs
        self.Settings.FreePortfolioValuePercentage = 0.1  # 10% margin requirement
        self.dollars_per_trade = 100000 * .9

    def OnSecuritiesChanged(self, changes):
        for security in changes.AddedSecurities:
            self._symbol = security.Symbol
            self.Debug(f"Added security: {self._symbol}")

    def OnData(self, data):
        # Get the current mapped futures contract data
        if self._symbol is None or not data.ContainsKey(self._symbol):
            return
            
        current_bar = data[self._symbol]
        if current_bar is None:
            return
            
        # Update our price arrays with the latest data
        # Format time as HHMMSS integer to match data source
        current_time_int = int(self.Time.strftime('%H%M%S'))
        self.time1.append(current_time_int)
        self.high.append(current_bar.High)
        self.low.append(current_bar.Low)
        self.close.append(current_bar.Close)
        
        # Reset at start of day
        if current_time_int == 0:
            self.bypass = True
            self.bypass1 = True
            self.tpb = self.slb = False
            self.tps = self.sls = False
            self.up = self.down = False
            self.slbe = self.tops = self.topsl = 999999
            self.slbu = self.bottoms = self.bottomsh = 0
            self.entryb = self.entrys = 0
        
        # Trading logic
        if len(self.time1) > 2:
            if current_time_int > self.start and current_time_int < self.end and self.bypass:
                if self.low[-1] > self.high[-3]:
                    self.bypass = False
                    self.bottomsh = self.low[-1]
                    self.bottoms = self.high[-3]
                    self.slbu = min(self.low[-2], self.low[-3])
                elif self.high[-1] < self.low[-3]:
                    self.bypass = False
                    self.topsl = self.high[-1]
                    self.btopsttoms = self.low[-3]
                    self.slbe = max(self.high[-2], self.high[-3])
            
            if current_time_int > self.start and current_time_int < self.end and self.bypass1:
                if self.close[-1] < self.bottomsh:
                    self.bypass1 = False
                    self.up = True
                    self.entryb = self.bottomsh
                    self.z += 1
                    self.Debug("BUYING")
                    qty = int(self.dollars_per_trade / self.close[-1])
                    self.MarketOrder(self._symbol, qty)
                elif self.close[-1] > self.topsl:
                    self.bypass1 = False
                    self.down = True
                    self.entrys = self.topsl
                    self.z += 1
                    qty = int(self.dollars_per_trade / self.close[-1])
                    self.MarketOrder(self._symbol, -qty)
                    self.Debug("SHORTING")
        
        if self.up and not self.down and not self.tpb and not self.slb and self.entryb > 0:
            if self.low[-1] < self.slbu and self.high[-1] < self.entryb + self.rr * (self.entryb - self.slbu):
                self.slb = True
                self.loss += 1
                self.cum_profit.append(self.rr * (self.slbu - self.entryb))
                self.MarketOrder(self._symbol, -self.Portfolio[self._symbol].Quantity)
                self.Debug(f"SELLING AT TIME: {self.Time}")
                self.entryb = 0
            elif self.low[-1] > self.slbu and self.high[-1] > self.entryb + self.rr * (self.entryb - self.slbu):
                self.tpb = True
                self.win += 1
                self.cum_profit.append(self.rr * (self.entryb - self.slbu))
                self.MarketOrder(self._symbol, -self.Portfolio[self._symbol].Quantity)
                self.Debug(f"SELLING AT TIME: {self.Time}")
                self.entryb = 0
        
        if self.down and not self.up and not self.tps and not self.sls and self.entrys > 0:
            if self.low[-1] < self.entrys - self.rr * (self.slbe - self.entrys) and self.high[-1] < self.slbe:
                self.tps = True
                self.win += 1
                self.cum_profit.append(self.rr * (self.slbe - self.entrys))
                self.MarketOrder(self._symbol, -self.Portfolio[self._symbol].Quantity)
                self.Debug(f"SELLING AT TIME: {self.Time}")
                self.entrys = 0
            elif self.high[-1] > self.slbe and self.low[-1] > self.entrys - self.rr * (self.slbe - self.entrys):
                self.sls = True
                self.loss += 1
                self.cum_profit.append(-self.rr * (self.slbe - self.entrys))
                self.MarketOrder(self._symbol, -self.Portfolio[self._symbol].Quantity)
                self.Debug(f"SELLING AT TIME: {self.Time}")
                self.entrys = 0
        
        if current_time_int == self.endof:
            self.EndDay()

    def OnEndOfAlgorithm(self):
        if self.win + self.loss == 0:
            return
        self.Debug(f"Win Rate: {self.win / (self.win + self.loss) * 100}%")
        self.Debug(f"Total Profit: {sum(self.cum_profit)}")
        self.Debug(f"Total Trades: {self.win + self.loss}")
        self.Debug(f"Total Wins: {self.win}")
        self.Debug(f"Total Losses: {self.loss}")

    def EndDay(self):
        self.Debug(f"Exit positions called at time: {self.Time}")
        if self.entryb > 0 and not self.tpb and not self.slb:
            if self.close[-1] > self.entryb:
                self.win += 1
            else:
                self.loss += 1
            self.cum_profit.append(self.close[-1] - self.entryb)
            self.MarketOrder(self._symbol, -1)
            self.entryb = 0
        elif self.entrys > 0 and not self.tps and not self.sls:
            if self.close[-1] > self.entrys:
                self.loss += 1
            else:
                self.win += 1
            self.cum_profit.append(self.entrys - self.close[-1])
            self.MarketOrder(self._symbol, 1)
            self.entrys = 0
