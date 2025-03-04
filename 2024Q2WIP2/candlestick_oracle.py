#region imports
from AlgorithmImports import *
#endregion
import talib
import numpy as np

weights = {}
weights["TASUKIGAP"] = 1.5
weights["SEPARATINGLINES"] = 1
weights["GAPSIDESIDEWHITE"] = .5
weights["HARAMI"] = 1.5
weights["HIKKAKE"] = 1.5
weights["HOMINGPIGEON"] = 1
weights["HAMMER"] = .5
weights["MARUBOZU"] = .5
weights["DARKCLOUDCOVER"] = -1.5
weights["3LINESTRIKE"] = -1.5
weights["ENGULFING"] = -1
weights["SHOOTINGSTAR"] = -.5

def get_candlestick_score(rolling_window, trend):
            rolling_window = [x for x in rolling_window if x is not None]
            rolling_window.reverse()
            size = len(rolling_window)
            
            O = np.array([rolling_window[i].Open for i in range(size)])
            H = np.array([rolling_window[i].High for i in range(size)])
            L = np.array([rolling_window[i].Low for i in range(size)])
            C = np.array([rolling_window[i].Close for i in range(size)])

            continuation_patterns = []
            continuation_patterns.append(talib.CDLTASUKIGAP(O, H, L, C))
            continuation_patterns.append(talib.CDLSEPARATINGLINES(O, H, L, C))
            continuation_patterns.append(talib.CDLGAPSIDESIDEWHITE(O,H,L,C))

            reversal_to_bull_patterns = []
            reversal_to_bull_patterns.append(talib.CDLHARAMI(O,H,L,C))
            reversal_to_bull_patterns.append(talib.CDLHIKKAKE(O,H,L,C))
            reversal_to_bull_patterns.append(talib.CDLHOMINGPIGEON(O,H,L,C))
            reversal_to_bull_patterns.append(talib.CDLHAMMER(O,H,L,C))
            reversal_to_bull_patterns.append(talib.CDLMARUBOZU(O,H,L,C))

            reversal_to_bear_patterns = []
            reversal_to_bear_patterns.append(talib.CDLDARKCLOUDCOVER(O,H,L,C))
            reversal_to_bear_patterns.append(talib.CDL3LINESTRIKE(O,H,L,C))
            reversal_to_bear_patterns.append(talib.CDLENGULFING(O,H,L,C))
            reversal_to_bear_patterns.append(talib.CDLSHOOTINGSTAR(O,H,L,C))
            

            final_weight = 0

            #if trend >.6 or trend < .4:
            for i in range(len(continuation_patterns)-1):
                if continuation_patterns[i].any() > 0:
                    if i == 0:
                        # TASUKI GAP
                        final_weight += weights["TASUKIGAP"] * trend
                    elif i == 1:
                        # SEPARATING LINES
                        final_weight += weights["SEPARATINGLINES"] * trend
                    elif i == 2:
                        # GAP SIDE SIDE WHITE
                        final_weight += weights["GAPSIDESIDEWHITE"] * trend
            #elif trend >=.4 and trend <.5:       
            for i in range(len(reversal_to_bull_patterns)-1):
                if reversal_to_bull_patterns[i].any() > 0:
                    if i == 0:
                        # HARAMI
                        final_weight += weights["HARAMI"]
                    elif i == 1:
                        # HIKKAKE
                        final_weight += weights["HIKKAKE"]
                    elif i == 2:
                        # HOMING PIGEON
                        final_weight += weights["HOMINGPIGEON"]
                    elif i == 3:
                        # HAMMER
                        final_weight += weights["HAMMER"]
                    elif i == 4:
                        # MARUBOZU
                        final_weight += weights["MARUBOZU"]
            #elif trend <=.6 and trend >=.5:
            for i in range(len(reversal_to_bear_patterns)-1):
                if reversal_to_bear_patterns[i].any() > 0:
                    if i == 0:
                        # DARK CLOUD COVER
                        final_weight += weights["DARKCLOUDCOVER"] 
                    elif i == 1:
                        # 3 LINE STRIKE
                        final_weight += weights["3LINESTRIKE"]
                    elif i == 2:
                        # ENGULFING
                        final_weight += weights["ENGULFING"]
                    elif i == 3:
                        # SHOOTING STAR
                        final_weight += weights["SHOOTINGSTAR"]
            return final_weight