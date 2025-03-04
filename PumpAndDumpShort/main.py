# region imports
from AlgorithmImports import *
from alpha import custom_alpha

# endregion


class Fallingknives(QCAlgorithm):
        
    def Initialize(self):
        self.SetStartDate(2020, 1, 1)  # Set start date
        self.SetEndDate(2024, 4, 1)  # Set end date (replace with desired end date)
        self.SetCash(1000000)  # Set initial capital
        self.final_universe_size = 700  # Number of stocks in final universe
        self.AddUniverse(self.CoarseFilter, self.FineFilter)
        self.UniverseSettings.Resolution = Resolution.Hour
        self.rebalanceTime = self.Time

        self.set_portfolio_construction(EqualWeightingPortfolioConstructionModel())
        self.set_alpha(custom_alpha(self))
        self.set_execution(ImmediateExecutionModel())
        self.add_risk_management(NullRiskManagementModel())
 
        # set account type
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage, AccountType.Margin)

        

    def CoarseFilter(self, coarse):
        # Rebalancing weekly
        
        if self.Time <= self.rebalanceTime:
            return self.Universe.Unchanged
        self.rebalanceTime = self.Time + timedelta(days=15)
        sortedByVolume = sorted(coarse, key=lambda x: x.DollarVolume, reverse=True)
        final = [x.Symbol for x in sortedByVolume if x.MarketCap > 0][300:1000]

        return final
    
    def FineFilter(self, fine):

        sorted_list = sorted(fine, key=lambda x: x.ValuationRatios.EVToEBITDA, reverse=False)
        final = [x.Symbol for x in sorted_list if x.HasFundamentalData and x.Price > 5][:self.final_universe_size]

        return final
    



