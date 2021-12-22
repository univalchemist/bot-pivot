from binance.enums import *
from collections import deque
from back.mock_order import MockOrder
from client.client import create_client
from back.position import Position
from client.trade import Trade
from utils.enums import *

from utils.log import logbook
from parameters import *

logger = logbook()

class PivotStrategy():
    def __init__(self, args, position):
      logger.info_magenta("PivotStrategy Class initializing...")
      self.args = args
      self.Symbol = args.symbol
      self.PivotStep = args.pivotstep # Default is 5
      self.Delta = args.delta # Default is 10
      self.MaxlenKlines = self.PivotStep*2 + 1
      self.Klines = deque(maxlen=self.MaxlenKlines)
      self.HighPivot = deque(maxlen=2)
      self.LowPivot = deque(maxlen=2)
      self.NextPivot = None
      self.Trend = TREND_NONE
      self.client = create_client(self.args)
      self.trade = MockOrder(self.args, position) if args.backtest else Trade(self.args)
      self.prepare_before_processing()

    def prepare_before_processing(self):
        if self.args.backtest: return
        res = self.client.futures_klines(symbol=self.Symbol, interval=str(self.args.interval) + "m")
        length = len(res)
        i = 0
        Klines = deque(maxlen=self.MaxlenKlines)
        HighPivot = deque(maxlen=2)
        LowPivot = deque(maxlen=2)
        NextPivot = None
        for row in res:
            Open = float(row[1])
            High = float(row[2])
            Low = float(row[3])
            Close = float(row[4])
            Klines.append({
                "Open": Open,
                "High": High,
                "Low": Low,
                "Close": Close
                })
            if i >= self.PivotStep and i < length - self.PivotStep:
                _klins_left = res[i - self.PivotStep:i]
                _klins_right = res[i + 1:i + self.PivotStep + 1]
                # Highs of left/right 5 candles
                HighsLeft = [float(x[2]) for x in _klins_left]
                LowsLeft = [float(x[3]) for x in _klins_left]
                # Lows of left/right 5 candles
                HighsRight = [float(x[2]) for x in _klins_right]
                LowsRight = [float(x[3]) for x in _klins_right]
                #
                HighCheck = True if all(x <= High for x in HighsLeft) and all(x < High for x in HighsRight) else False
                LowCheck = True if all(x >= Low for x in LowsLeft) and all(x > Low for x in LowsRight) else False
                if NextPivot == None:
                    if HighCheck == True:
                        HighPivot.append(High)
                        NextPivot = PIVOT_LOW
                    elif LowCheck == True:
                        LowPivot.append(Low)
                        NextPivot = PIVOT_HIGH
                else:
                    if HighCheck == True:
                        # Check the current high pivot is greater than the previous one. If true, replace the previous one to current
                        LastHigh = HighPivot[len(HighPivot) - 1] if len(HighPivot) > 0 else 0
                        # Check the current high pivot is greater than the previous one. If true, replace the previous one to current
                        if NextPivot == PIVOT_LOW and High > LastHigh and LastHigh > 0:
                            HighPivot.remove(LastHigh)
                            HighPivot.append(High)
                        if NextPivot == PIVOT_HIGH:
                            HighPivot.append(High)
                            NextPivot = PIVOT_LOW
                    if LowCheck == True:
                        # Check there is continuous LL without LH
                        LastLow = LowPivot[len(LowPivot) - 1] if len(LowPivot) > 0 else 0
                        # Check the current low pivot is less than the previous one. If true, replace the previous one to current
                        if NextPivot == PIVOT_HIGH and LastLow > Low and LastLow > 0:
                            LowPivot.remove(LastLow)
                            LowPivot.append(Low)
                        if NextPivot == PIVOT_LOW:
                            LowPivot.append(Low)
                            NextPivot = PIVOT_HIGH
            i = i + 1
        self.Klines = Klines
        self.HighPivot = HighPivot
        self.LowPivot = LowPivot
    
    def handle_kline_msg(self, msg):
        Info = msg["k"]
        Closed = Info["x"]
        logger.info("The current candle's closed is " + str(Closed))
        if Closed == True:
            self.Klines.append({
                "Open": Info["o"],
                "Close": Info["c"],
                "High": Info["h"],
                "Low": Info["l"]
                })
            self.calculate_pivot_high_low()
    def calculate_pivot_high_low(self):
        if len(self.Klines) == self.MaxlenKlines:
            Kline = self.Klines[self.PivotStep]
            Open = float(Kline["Open"])
            Close = float(Kline["Close"])
            High = float(Kline["High"]) # Get high value of 5th candle to compare left/right 5 candles
            Low = float(Kline["Low"]) # Get low value of 5th candle to compare left/right 5 candles
            _klins_left = list(self.Klines)[0:self.PivotStep]
            _klins_right = list(self.Klines)[self.PivotStep + 1:self.MaxlenKlines]
            # Highs of left/right 5 candles
            HighsLeft = [float(x["High"]) for x in _klins_left]
            LowsLeft = [float(x["Low"]) for x in _klins_left]
            # Lows of left/right 5 candles
            HighsRight = [float(x["High"]) for x in _klins_right]
            LowsRight = [float(x["Low"]) for x in _klins_right]
            #
            HighCheck = True if all(x <= High for x in HighsLeft) and all(x < High for x in HighsRight) else False
            LowCheck = True if all(x >= Low for x in LowsLeft) and all(x > Low for x in LowsRight) else False
            # Check the candle is green or red
            IsUpCandle = True if Close > Open else False
            # It is just for the process to find the first high/low point
            if self.NextPivot == None:
                if HighCheck == True:
                    self.HighPivot.append(High)
                    self.NextPivot = PIVOT_LOW
                elif LowCheck == True:
                    self.LowPivot.append(Low)
                    self.NextPivot = PIVOT_HIGH
            else:
                if HighCheck == True:
                    # Check the current high pivot is greater than the previous one. If true, replace the previous one to current
                    LastHigh = self.HighPivot[len(self.HighPivot) - 1] if len(self.HighPivot) > 0 else 0
                    # Check the current high pivot is greater than the previous one. If true, replace the previous one to current
                    if self.NextPivot == PIVOT_LOW and High > LastHigh and LastHigh > 0:
                        self.HighPivot.remove(LastHigh)
                        self.HighPivot.append(High)
                    if self.NextPivot == PIVOT_HIGH:
                        self.HighPivot.append(High)
                        self.NextPivot = PIVOT_LOW
                if LowCheck == True:
                    # Check there is continuous LL without LH
                    LastLow = self.LowPivot[len(self.LowPivot) - 1] if len(self.LowPivot) > 0 else 0
                    # Check the current low pivot is less than the previous one. If true, replace the previous one to current
                    if self.NextPivot == PIVOT_HIGH and LastLow > Low and LastLow > 0:
                        self.LowPivot.remove(LastLow)
                        self.LowPivot.append(Low)
                    if self.NextPivot == PIVOT_LOW:
                        self.LowPivot.append(Low)
                        self.NextPivot = PIVOT_HIGH
        self.check_up_down_trend()
    def check_up_down_trend(self):
        # Check high/low pivots length is max length
        if len(self.LowPivot) == 2 and len(self.HighPivot) == 2:
            # Get last two low/high pivots
            LowP0 = self.LowPivot[0]
            LowP1 = self.LowPivot[1]
            HighP0 = self.HighPivot[0]
            HighP1 = self.HighPivot[1]
            DeltaHigh = abs(HighP1 - HighP0)
            DeltaLow = abs(LowP1 - LowP0)
            if DeltaHigh > self.Delta or DeltaLow > self.Delta:
                if LowP1 > LowP0 and HighP1 > HighP0: # Strong Uptrend
                    self.Trend = TREND_UP
                elif LowP1 >= LowP0 and HighP0 > HighP1 and self.NextPivot == PIVOT_HIGH: # In downtrend, appear new HL
                    self.Trend = TREND_UP
                elif LowP0 > LowP1 and HighP1 >= HighP0 and self.NextPivot == PIVOT_LOW: # In downtrend, appear new HH
                    self.Trend = TREND_UP
                elif HighP0 > HighP1 and LowP0 > LowP1: # Strong Downtrend
                    self.Trend = TREND_DOWN
                elif HighP1 > HighP0 and LowP0 >= LowP1 and self.NextPivot == PIVOT_HIGH: # In uptrend, appear new LL
                    self.Trend = TREND_DOWN
                elif HighP0 >= HighP1 and LowP1 > LowP0 and self.NextPivot == PIVOT_LOW: # In uptrend, appear new LH
                    self.Trend = TREND_DOWN
            else:
                self.Trend = TREND_NONE
            
            LastPivotLow = self.LowPivot[1]
            LastPivotHigh = self.HighPivot[1]
            LastCandle = self.Klines[-1]
            if self.args.backtest: self.trade.mock_order_tp_sl(self.Trend, LastPivotLow, LastPivotHigh, LastCandle)
            else: self.trade.handle_order_tp_sl(self.Trend, LastPivotLow, LastPivotHigh, LastCandle)
