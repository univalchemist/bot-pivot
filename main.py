from binance import Client
from binance import ThreadedWebsocketManager as t_ws
from binance import BinanceSocketManager as bs
from binance.exceptions import BinanceAPIException
from binance.enums import *
from collections import deque
from threading import Thread as T

from parameters import *
from trade import *

client = Client(API_KEY, API_SECRET, testnet=True)
# symbol = "btcusdt@bookTicker"
symbol = "BTCUSDT"

class HandleCandle():
    def __init__(self):
        self.PivotStep = 5
        self.MaxlenKlines = self.PivotStep*2 + 1
        self.Klines = deque(maxlen=self.MaxlenKlines)
        self.HighPivot = deque(maxlen=2)
        self.LowPivot = deque(maxlen=2)
        self.NextPivot = "None"
        self.Trend = "None"
        self.Delta = 10
        self.DeltaSL = 0.0005
        self.PricePrecision = 1
        self.QtyPrecision = 1
        self.DeltaPercent = 0.08
        self.AmountPerTrade = 50
        self.LongAvgPrice = 0
        self.ShortAvgPrice = 0
        self.LongOrderID = None
        self.ShortOrderID = None
        self.LongPosition = False
        self.ShortPosition = False
        self.LastHighForLong = 0
        self.LastLowForShort = 0
        print("==============Class init===================")
        self.prepare_before_processing()
        self.get_precision()
        
    def prepare_before_processing(self):
        res = client.futures_klines(symbol=symbol, interval=KLINE_INTERVAL_1MINUTE)
        length = len(res)
        i = 0
        Klines = deque(maxlen=self.MaxlenKlines)
        HighPivot = deque(maxlen=2)
        LowPivot = deque(maxlen=2)
        NextPivot = "None"
        for row in res:
            Open = float(row[1])
            High = float(row[2])
            Low = float(row[3])
            Close = float(row[4])
            Klines.append({
                "Open": Open,
                "Close": Close,
                "High": High,
                "Low": Low
                })
            if i > self.PivotStep - 1 and i < length - self.PivotStep:
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
                if NextPivot == "None":
                    if HighCheck == True:
                        HighPivot.append(High)
                        NextPivot = "Low"
                    elif LowCheck == True:
                        LowPivot.append(Low)
                        NextPivot = "High"
                else:
                    if HighCheck == True:
                        # Check the current high pivot is greater than the previous one. If true, replace the previous one to current
                        LastHigh = HighPivot[len(HighPivot) - 1] if len(HighPivot) > 0 else 0
                        # Check the current high pivot is greater than the previous one. If true, replace the previous one to current
                        if NextPivot == "Low" and High > LastHigh and LastHigh > 0:
                            HighPivot.remove(LastHigh)
                            HighPivot.append(High)
                        if NextPivot == "High":
                            HighPivot.append(High)
                            NextPivot = "Low"
                    if LowCheck == True:
                        # Check there is continuous LL without LH
                        LastLow = LowPivot[len(LowPivot) - 1] if len(LowPivot) > 0 else 0
                        # Check the current low pivot is less than the previous one. If true, replace the previous one to current
                        if NextPivot == "High" and LastLow > Low and LastLow > 0:
                            LowPivot.remove(LastLow)
                            LowPivot.append(Low)
                        if NextPivot == "Low":
                            LowPivot.append(Low)
                            NextPivot = "High"
            i = i + 1
        self.Klines = Klines
        self.HighPivot = HighPivot
        self.LowPivot = LowPivot
    def get_precision(self):
        info = client.futures_exchange_info()
        for x in info["symbols"]:
            if x["symbol"] == symbol:
                self.PricePrecision = int(x["pricePrecision"])
                self.QtyPrecision = int(x["quantityPrecision"])
    def handle_kline_msg(self, msg):
        Info = msg["k"]
        Closed = Info["x"]
        print("==============Closed===================", Closed)
        if Closed == True:
            self.Klines.append({
                "Open": Info["o"],
                "Close": Info["c"],
                "High": Info["h"],
                "Low": Info["l"]
                })
            self.calculate_pivot_high_low()
    def calculate_pivot_high_low(self):
        print(len(self.Klines))
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
            if self.NextPivot == "None":
                if HighCheck == True:
                    self.HighPivot.append(High)
                    self.NextPivot = "Low"
                elif LowCheck == True:
                    self.LowPivot.append(Low)
                    self.NextPivot = "High"
            else:
                if HighCheck == True:
                    # Check the current high pivot is greater than the previous one. If true, replace the previous one to current
                    LastHigh = self.HighPivot[len(self.HighPivot) - 1] if len(self.HighPivot) > 0 else 0
                    # Check the current high pivot is greater than the previous one. If true, replace the previous one to current
                    if self.NextPivot == "Low" and High > LastHigh and LastHigh > 0:
                        self.HighPivot.remove(LastHigh)
                        self.HighPivot.append(High)
                    if self.NextPivot == "High":
                        self.HighPivot.append(High)
                        self.NextPivot = "Low"
                if LowCheck == True:
                    # Check there is continuous LL without LH
                    LastLow = self.LowPivot[len(self.LowPivot) - 1] if len(self.LowPivot) > 0 else 0
                    # Check the current low pivot is less than the previous one. If true, replace the previous one to current
                    if self.NextPivot == "High" and LastLow > Low and LastLow > 0:
                        self.LowPivot.remove(LastLow)
                        self.LowPivot.append(Low)
                    if self.NextPivot == "Low":
                        self.LowPivot.append(Low)
                        self.NextPivot = "High"
        self.check_up_down_trend()
    def check_up_down_trend(self):
        print("========check_up_down_trend======>>>", self.Trend)
        print("========len(self.LowPivot)======>>>", len(self.LowPivot))
        print("========len(self.HighPivot)======>>>", len(self.HighPivot))
        # Check high/low pivots length is max length
        if len(self.LowPivot) == 2 and len(self.HighPivot) == 2:
            # Get last two low/high pivots
            LowP0 = self.LowPivot[0]
            LowP1 = self.LowPivot[1]
            HighP0 = self.HighPivot[0]
            HighP1 = self.HighPivot[1]
            print("========LowP0======>>>", LowP0)
            print("========LowP1======>>>", LowP1)
            print("========HighP0======>>>", HighP0)
            print("========HighP1======>>>", HighP1)
            DeltaHigh = abs(HighP1 - HighP0)
            DeltaLow = abs(LowP1 - LowP0)
            if DeltaHigh > self.Delta or DeltaLow > self.Delta:
                if LowP1 > LowP0 and HighP1 > HighP0: # Strong Uptrend
                    print("Condition 1: Up")
                    self.Trend = "Up"
                elif LowP1 >= LowP0 and HighP0 > HighP1 and self.NextPivot == "High": # In downtrend, appear new HL
                    print("Condition 2: Up")
                    self.Trend = "Up"
                elif LowP0 > LowP1 and HighP1 >= HighP0 and self.NextPivot == "Low": # In downtrend, appear new HH
                    print("Condition 3: Up")
                    self.Trend = "Up"
                elif HighP0 > HighP1 and LowP0 > LowP1: # Strong Downtrend
                    print("Condition 4: Down")
                    self.Trend = "Down"
                elif HighP1 > HighP0 and LowP0 >= LowP1 and self.NextPivot == "High": # In uptrend, appear new LL
                    print("Condition 5: Down")
                    self.Trend = "Down"
                elif HighP0 >= HighP1 and LowP1 > LowP0 and self.NextPivot == "Low": # In uptrend, appear new LH
                    print("Condition 6: Down")
                    self.Trend = "Down"
            else:
                self.Trend = "None"
                print("Condition 7: None")
            self.handle_order()
    def handle_order(self):
        print("handle_order: ", self.Trend)
        if self.Trend == "Up":
            # There should be no any long position
            if self.LongOrderID == None and self.LongPosition == False:
                LastPivotLow = self.LowPivot[1]
                LastCandle = self.Klines[-1]
                LastHigh = float(LastCandle["High"])
                LastLow = float(LastCandle["Low"])

                # If the last candle low price is greater than last pivot low, continue.(confirming it is still uptrend)
                if LastLow >= LastPivotLow:
                    TriggerPrice = float(round(LastHigh + LastHigh * self.DeltaPercent / 100, self.PricePrecision))
                    Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                    NewOrder = open_long_stop_market(symbol, Amount, TriggerPrice)
                    if NewOrder != None and NewOrder["orderId"] and NewOrder["status"] == "NEW":
                        self.LongOrderID = NewOrder["orderId"]
                        self.LastHighForLong = LastHigh # Need for next moving SL
            elif self.LongOrderID:
                res = client.futures_get_order(symbol=symbol, orderId=self.LongOrderID)
                if self.LongPosition == False:
                    # If order is filled, create new open long order
                    if res["status"] == "FILLED":
                        self.LongPosition = True
                        LastPivotLow = float(round(self.LowPivot[1] - self.LowPivot[1] * self.DeltaSL, self.PricePrecision))
                        avgPrice = float(res["avgPrice"])
                        self.LongAvgPrice = avgPrice
                        StopPrice = float(round(self.LongAvgPrice - self.LongAvgPrice * 0.45 / 100, self.PricePrecision))
                        StopPrice = StopPrice if StopPrice > LastPivotLow else LastPivotLow
                        StopOrder = close_long_stop_market(symbol, StopPrice)
                        if StopOrder != None and StopOrder["orderId"] and StopOrder["status"] == "NEW":
                            self.LongOrderID = StopOrder["orderId"]
                    elif res["status"] == "NEW": # Still no filled, Move Stop Trigger
                        LastPivotLow = self.LowPivot[1]
                        LastCandle = self.Klines[-1]
                        LastHigh = float(LastCandle["High"])
                        LastLow = float(LastCandle["Low"])

                        # If the last candle low price is greater than last pivot low, continue.
                        if LastLow >= LastPivotLow:
                            if self.LastHighForLong > LastHigh:
                                # Cancel Original Open Long Order
                                OriginalOrder = cancel_order(symbol, self.LongOrderID)
                                if OriginalOrder != None and OriginalOrder["orderId"] and OriginalOrder["status"] == "CANCELED":
                                    self.LongOrderID = None
                                    self.LastHighForLong = 0
                                    TriggerPrice = float(round(LastHigh + LastHigh * self.DeltaPercent / 100, self.PricePrecision))
                                    Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                                    NewOrder = open_long_stop_market(symbol, Amount, TriggerPrice)
                                    if NewOrder != None and NewOrder["orderId"] and NewOrder["status"] == "NEW":
                                        self.LongOrderID = NewOrder["orderId"]
                                        self.LastHighForLong = LastHigh
                        else:
                            # Cancel Original Open Long Order
                            OriginalOrder = cancel_order(symbol, self.LongOrderID)
                            if OriginalOrder != None and OriginalOrder["orderId"] and OriginalOrder["status"] == "CANCELED":
                                self.LongOrderID = None
                                self.LastHighForLong = 0

                    elif res["status"] != "CANCELED": # PARTIALLY_FILLED, PENDING_CANCEL, REJECTED, EXPIRED
                        self.LongOrderID = None
                        self.LastHighForLong = 0
                elif self.LongPosition == True: # This case is for that the current oder is close order. Thus, move stop-loss
                    # If order is filled, should no create new order for long because in uptrend, stop-loss hitted last pivot low. It means, uptrend is broken.
                    if res["status"] == "FILLED":
                        self.LongOrderID = None
                        self.LongPosition = False
                        self.LastHighForLong = 0
                    elif res["status"] == "NEW": # Move Stop Loss
                        # Cancel Original Close Stop Order
                        OriginalOrder = cancel_order(symbol, self.LongOrderID)
                        if OriginalOrder != None and OriginalOrder["orderId"] and OriginalOrder["status"] == "CANCELED":
                            self.LongOrderID = None
                            LastPivotLow = float(round(self.LowPivot[1] - self.LowPivot[1] * self.DeltaSL, self.PricePrecision))
                            StopPrice = float(round(self.LongAvgPrice - self.LongAvgPrice * 0.45 / 100, self.PricePrecision))
                            StopPrice = StopPrice if StopPrice > LastPivotLow else LastPivotLow
                            NewStopOrder = close_long_stop_market(symbol, StopPrice)
                            if NewStopOrder != None and NewStopOrder["orderId"] and NewStopOrder["status"] == "NEW":
                                self.LongOrderID = NewStopOrder["orderId"]
            if self.ShortOrderID != None and self.ShortPosition == False: # In the previous downtrend, if there is open short order.
                CloseOpenShort = cancel_order(symbol, self.ShortOrderID)
                if CloseOpenShort != None and CloseOpenShort["orderId"] and CloseOpenShort["status"] == "CANCELED":
                    self.ShortOrderID = None
                    self.LastLowForShort = 0
        if self.Trend == "Down":
            # If no any shot position
            if self.ShortOrderID == None and self.ShortPosition == False:
                LastPivotHigh = self.HighPivot[1]
                LastCandle = self.Klines[-1]
                LastHigh = float(LastCandle["High"])
                LastLow = float(LastCandle["Low"])

                # If the last candle high price is less than last pivot high, continue.(confirming it is still downtrend)
                if LastPivotHigh >= LastHigh:
                    TriggerPrice = float(round(LastLow - LastLow * self.DeltaPercent / 100, self.PricePrecision))
                    Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                    NewOrder = open_short_stop_market(symbol, Amount, TriggerPrice)
                    if NewOrder != None and NewOrder["orderId"] and NewOrder["status"] == "NEW":
                        self.ShortOrderID = NewOrder["orderId"]
                        self.LastLowForShort = LastLow
            elif self.ShortOrderID:
                res = client.futures_get_order(symbol=symbol, orderId=self.ShortOrderID)
                if self.ShortPosition == False:
                    # If order is filled, create new close short order
                    if res["status"] == "FILLED":
                        self.ShortPosition = True
                        LastPivotHigh = float(round(self.HighPivot[1] + self.HighPivot[1] * self.DeltaSL, self.PricePrecision))
                        avgPrice = float(res["avgPrice"])
                        self.ShortAvgPrice = avgPrice
                        StopPrice = float(round(self.ShortAvgPrice + self.ShortAvgPrice * 0.45 / 100, self.PricePrecision))
                        StopPrice = LastPivotHigh if StopPrice > LastPivotHigh else StopPrice
                        StopOrder = close_short_stop_market(symbol, StopPrice)
                        if StopOrder != None and StopOrder["orderId"] and StopOrder["status"] == "NEW":
                            self.ShortOrderID = StopOrder["orderId"]
                    elif res["status"] == "NEW": # Still no filled, Move Stop Trigger
                        LastPivotHigh = self.HighPivot[1]
                        LastCandle = self.Klines[-1]
                        LastHigh = float(LastCandle["High"])
                        LastLow = float(LastCandle["Low"])

                        # If the last candle high price is less than last pivot high, continue.(confirming it is still downtrend)
                        if LastPivotHigh >= LastHigh:
                            if LastLow > self.LastLowForShort:
                                # Cancel Original Stop Order
                                OriginalOrder = cancel_order(symbol, self.ShortOrderID)
                                if OriginalOrder != None and OriginalOrder["orderId"] and OriginalOrder["status"] == "CANCELED":
                                    self.ShortOrderID = None
                                    self.LastLowForShort = 0
                                    TriggerPrice = float(round(LastLow - LastLow * self.DeltaPercent / 100, self.PricePrecision))
                                    Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                                    NewOrder = open_short_stop_market(symbol, Amount, TriggerPrice)
                                    if NewOrder != None and NewOrder["orderId"] and NewOrder["status"] == "NEW":
                                        self.ShortOrderID = NewOrder["orderId"]
                                        self.LastLowForShort = LastLow
                        else:
                            # Cancel Original Open Short Order
                            OriginalOrder = cancel_order(symbol, self.ShortOrderID)
                            if OriginalOrder != None and OriginalOrder["orderId"] and OriginalOrder["status"] == "CANCELED":
                                self.ShortOrderID = None
                                self.LastLowForShort = 0

                    elif res["status"] != "CANCELED": # PARTIALLY_FILLED, PENDING_CANCEL, REJECTED, EXPIRED
                        self.ShortOrderID = None
                elif self.ShortPosition == True: # This case is for that the current oder is close short order. Thus, move stop-loss
                    # If order is filled, should no create new order for short because in downtrend, stop-loss hitted last pivot high. It means, downtrend is broken.
                    if res["status"] == "FILLED":
                        self.ShortOrderID = None
                        self.ShortPosition = False
                        self.LastLowForShort = 0
                    elif res["status"] == "NEW": # Move SL
                        # Cancel Original Close Short Order
                        OriginalOrder = cancel_order(symbol, self.ShortOrderID)
                        if OriginalOrder != None and OriginalOrder["orderId"] and OriginalOrder["status"] == "CANCELED":
                            self.ShortOrderID = None
                            LastPivotHigh = float(round(self.HighPivot[1] + self.HighPivot[1] * self.DeltaSL, self.PricePrecision))
                            StopPrice = float(round(self.ShortAvgPrice + self.ShortAvgPrice * 0.45 / 100, self.PricePrecision))
                            StopPrice = LastPivotHigh if StopPrice > LastPivotHigh else StopPrice
                            NewStopOrder = close_short_stop_market(symbol, StopPrice)
                            if NewStopOrder != None and NewStopOrder["orderId"] and NewStopOrder["status"] == "NEW":
                                self.ShortOrderID = NewStopOrder["orderId"]
            if self.LongOrderID != None and self.LongPosition == False: # In the previous upgrend, if there is open long order.
                CloseOpenLong = cancel_order(symbol, self.LongOrderID)
                if CloseOpenLong != None and CloseOpenLong["orderId"] and CloseOpenLong["status"] == "CANCELED":
                    self.LongOrderID = None
                    self.LastHighForLong = 0

def main():
    print("main")
    # create socket manager
    try:
        twm = t_ws(api_key=API_KEY, api_secret=API_SECRET, testnet=True)
        bm = bs(client)
        twm.start()

        twm.start_kline_futures_socket(callback=HandleCandle().handle_kline_msg, symbol=symbol)
    except BinanceAPIException as e:
        print("something wrong!!!!!!!!!!")
        print(e)

if __name__ == "__main__":
    main()