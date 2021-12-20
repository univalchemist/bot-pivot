from binance import ThreadedWebsocketManager as t_ws
from binance.exceptions import BinanceAPIException
from binance.enums import *
from collections import deque
import json, csv
import os.path
import argparse, sys
from types import SimpleNamespace
from datetime import timedelta, datetime
from multiprocessing import cpu_count
from joblib import Parallel
from joblib import delayed

from utils.arguments import Argument
from utils.draw_pivot import PlotPivot
from utils.log import logbook
from parameters import *
from strategy.pivot import PivotStrategy
from trade.order import *
from utils.position import Position

logger = logbook()

class BackTest():
    def __init__(self, args, position=Position()):
      self.args = args
      self.Symbol = args.symbol
      self.PivotStep = args.pivotstep # Default is 5
      self.MaxlenKlines = self.PivotStep*2 + 1
      self.Klines50 = deque(maxlen=50)
      self.Klines100 = deque(maxlen=100)
      self.Klines = deque(maxlen=self.MaxlenKlines)
      self.HighPivot = deque(maxlen=2)
      self.LowPivot = deque(maxlen=2)
      self.NextPivot = "None"
      self.Trend = "None"
      self.Delta = args.delta # Default is 10
      self.DeltaSL = args.deltasl # Default is 0.05
      self.PricePrecision = 1
      self.QtyPrecision = 1
      self.DeltaTrigger = args.deltatrigger # Default is 0.15
      self.AmountPerTrade = args.amount # Default is 50
      self.StopLoss = args.stoploss # Default is 0.4
      self.TakeProfit = args.takeprofit # Default is 0.8
      self.LongAvgPrice = 0
      self.ShortAvgPrice = 0
      self.LongOrderID = None
      self.ShortOrderID = None
      self.LongPosition = False
      self.ShortPosition = False
      self.LastHighForLong = 0
      self.LastLowForShort = 0
      self.client = self.create_client()
      self.get_precision()

      self.PositionAmount = 0
      self.PositionEntry = 0
      self.position = position
      self.LongOrderPrice = None
      self.ShortOrderPrice = None

      self.LongStopLoss = None
      self.LongTakeProfit = None
      self.ShortStopLoss = None
      self.ShortTakeProfit = None
      logger.info_magenta("BackTest Class initialized...")
    def create_client(self):
      return Client(API_KEY, API_SECRET)

    def get_precision(self):
        info = self.client.futures_exchange_info()
        for x in info["symbols"]:
            if x["symbol"] == self.Symbol:
                self.PricePrecision = int(x["pricePrecision"])
                self.QtyPrecision = int(x["quantityPrecision"])
    def handle_kline_msg(self, msg):
        self.Klines.append({
                "Open": msg[1],
                "Close": msg[4],
                "High": msg[3],
                "Low": msg[2]
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
                    self.Trend = "Up"
                elif LowP1 >= LowP0 and HighP0 > HighP1 and self.NextPivot == "High": # In downtrend, appear new HL
                    self.Trend = "Up"
                elif LowP0 > LowP1 and HighP1 >= HighP0 and self.NextPivot == "Low": # In downtrend, appear new HH
                    self.Trend = "Up"
                elif HighP0 > HighP1 and LowP0 > LowP1: # Strong Downtrend
                    self.Trend = "Down"
                elif HighP1 > HighP0 and LowP0 >= LowP1 and self.NextPivot == "High": # In uptrend, appear new LL
                    self.Trend = "Down"
                elif HighP0 >= HighP1 and LowP1 > LowP0 and self.NextPivot == "Low": # In uptrend, appear new LH
                    self.Trend = "Down"
            else:
                self.Trend = "None"
            self.mock_order_tp_sl()
    def mock_order_trailing_sl(self):
        logger.info("The Trend is " + self.Trend)
        LastPivotLow = self.LowPivot[1]
        LastPivotHigh = self.HighPivot[1]
        LastCandle = self.Klines[-1]
        LastHigh = float(LastCandle["High"])
        LastLow = float(LastCandle["Low"])
        if self.Trend == "Up":
            if self.LongOrderPrice == None:
                if self.LongPosition == True: # If there is the long position opened and no stop order
                    LastPivotLow = float(round(LastPivotLow - LastPivotLow * self.DeltaSL / 100, self.PricePrecision))
                    StopPrice = float(round(LastLow - LastLow * self.StopLoss / 100, self.PricePrecision))
                    StopPrice = StopPrice if StopPrice > LastPivotLow else LastPivotLow
                    self.LongOrderPrice = StopPrice
                else: # There is no any long position and stop order.
                    # If the last candle low price is greater than last pivot low, continue.(confirming it is still uptrend)
                    if LastLow >= LastPivotLow:
                        TriggerPrice = float(round(LastHigh + LastHigh * self.DeltaTrigger / 100, self.PricePrecision))
                        Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                        self.PositionAmount = Amount
                        self.LongOrderPrice = TriggerPrice
                        self.LastHighForLong = LastHigh # Need for next moving SL
                        
            elif self.LongOrderPrice:
                if self.LongPosition == False:
                    # If order is filled, create new open long stop order
                    if LastHigh > self.LongOrderPrice:
                        self.LongPosition = True
                        self.LongAvgPrice = self.LongOrderPrice
                        LastPivotLow = float(round(self.LowPivot[1] - self.LowPivot[1] * self.DeltaSL / 100, self.PricePrecision))
                        StopPrice = float(round(self.LongAvgPrice - self.LongAvgPrice * self.StopLoss / 100, self.PricePrecision))
                        StopPrice = StopPrice if StopPrice > LastPivotLow else LastPivotLow
                        self.PositionEntry = self.LongOrderPrice
                        self.LongOrderPrice = StopPrice
                    else: # Still no filled, Move Stop Trigger
                        # If the last candle low price is greater than last pivot low, continue.
                        if LastLow >= LastPivotLow:
                            if self.LastHighForLong > LastHigh:
                                # Cancel Original Open Long Order
                                self.LongOrderPrice = None
                                TriggerPrice = float(round(LastHigh + LastHigh * self.DeltaTrigger / 100, self.PricePrecision))
                                self.LongOrderPrice = TriggerPrice
                        else:
                            # Cancel Original Open Long Order
                            self.LongOrderPrice = None
                            self.LastHighForLong = 0
                            self.Position = {}
                    # TODO
                    # If order status is PARTIALLY_FILLED
                elif self.LongPosition == True: # This case is for that the current oder is close order. Thus, move stop-loss
                    # If order is filled, should no create new order for long because in uptrend, stop-loss hitted last pivot low. It means, uptrend is broken.
                    if self.LongOrderPrice > LastLow:
                        self.position.add_position({
                            "Amount": self.PositionAmount,
                            "Entry": self.PositionEntry,
                            "Exit": self.LongOrderPrice,
                            "Side": "Long"
                        })
                        self.LongOrderPrice = None
                        self.LongPosition = False
                        self.LastHighForLong = 0
                    else: # Move Stop Loss
                        # Cancel Original Close Stop Order
                        self.LongOrderPrice = None
                        LastPivotLow = float(round(self.LowPivot[1] - self.LowPivot[1] * self.DeltaSL / 100, self.PricePrecision))
                        StopPrice = float(round(self.LongAvgPrice - self.LongAvgPrice * self.StopLoss / 100, self.PricePrecision))
                        StopPrice = StopPrice if StopPrice > LastPivotLow else LastPivotLow
                        self.LongOrderPrice = StopPrice
            if self.ShortOrderPrice != None and self.ShortPosition == False: # In the previous downtrend, if there is open short order.
                self.ShortOrderPrice = None
                self.LastLowForShort = 0
        if self.Trend == "Down":
            # If there is the opened position and no stop order.
            if self.ShortOrderPrice == None:
                if self.ShortPosition == True: # There is short position without Stop Order
                    LastPivotHigh = float(round(LastPivotHigh + LastPivotHigh * self.DeltaSL / 100, self.PricePrecision))
                    StopPrice = float(round(LastHigh + LastHigh * self.StopLoss / 100, self.PricePrecision))
                    StopPrice = LastPivotHigh if StopPrice > LastPivotHigh else StopPrice
                    self.ShortOrderPrice = StopPrice
                else: # There is no any position, order
                    # If the last candle high price is less than last pivot high, continue.(confirming it is still downtrend)
                    if LastPivotHigh >= LastHigh:
                        TriggerPrice = float(round(LastLow - LastLow * self.DeltaTrigger / 100, self.PricePrecision))
                        Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                        self.PositionAmount = Amount
                        self.ShortOrderPrice = TriggerPrice
                        self.LastLowForShort = LastLow
            elif self.ShortOrderPrice:
                if self.ShortPosition == False:
                    # If order is filled, create new close short stop order
                    if self.ShortOrderPrice >= LastLow:
                        self.ShortPosition = True
                        LastPivotHigh = float(round(self.HighPivot[1] + self.HighPivot[1] * self.DeltaSL / 100, self.PricePrecision))
                        self.ShortAvgPrice = self.ShortOrderPrice
                        StopPrice = float(round(self.ShortAvgPrice + self.ShortAvgPrice * self.StopLoss / 100, self.PricePrecision))
                        StopPrice = LastPivotHigh if StopPrice > LastPivotHigh else StopPrice
                        self.PositionEntry = self.ShortOrderPrice
                        self.ShortOrderPrice = StopPrice
                    else: # Still no filled, Move Stop Trigger
                        # If the last candle high price is less than last pivot high, continue.(confirming it is still downtrend)
                        if LastPivotHigh >= LastHigh:
                            if LastLow > self.LastLowForShort:
                                # Cancel Original Stop Order
                                self.ShortOrderPrice = None
                                self.LastLowForShort = 0
                                TriggerPrice = float(round(LastLow - LastLow * self.DeltaTrigger / 100, self.PricePrecision))
                                Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                                self.ShortOrderPrice = TriggerPrice
                                self.LastLowForShort = LastLow
                                self.PositionAmount = Amount
                        else:
                            # Cancel Original Open Short Order
                            self.ShortOrderPrice = None
                            self.LastLowForShort = 0

                elif self.ShortPosition == True: # This case is for that the current oder is close short order. Thus, move stop-loss
                    # If order is filled, should no create new order for short because in downtrend, stop-loss hitted last pivot high. It means, downtrend is broken.
                    if LastHigh >= self.ShortOrderPrice:
                        self.position.add_position({
                            "Amount": self.PositionAmount,
                            "Entry": self.PositionEntry,
                            "Exit": self.ShortOrderPrice,
                            "Side": "Short"
                        })
                        self.ShortOrderPrice = None
                        self.ShortPosition = False
                        self.LastLowForShort = 0
                    else: # Move SL
                        # Cancel Original Close Short Order
                        self.ShortOrderPrice = None
                        LastPivotHigh = float(round(self.HighPivot[1] + self.HighPivot[1] * self.DeltaSL / 100, self.PricePrecision))
                        StopPrice = float(round(self.ShortAvgPrice + self.ShortAvgPrice * self.StopLoss / 100, self.PricePrecision))
                        StopPrice = LastPivotHigh if StopPrice > LastPivotHigh else StopPrice
                        self.ShortOrderPrice = StopPrice
            if self.LongOrderPrice != None and self.LongPosition == False: # In the previous upgrend, if there is open long order.
                self.LongOrderPrice = None
                self.LastHighForLong = 0
    def mock_order_tp_sl(self):
        logger.info("The Trend is " + self.Trend)
        LastPivotLow = self.LowPivot[1]
        LastPivotHigh = self.HighPivot[1]
        LastCandle = self.Klines[-1]
        LastHigh = float(LastCandle["High"])
        LastLow = float(LastCandle["Low"])
        if self.Trend == "Up":
            if self.LongPosition == False:
                if self.LongOrderPrice == None: # There is no any open long order
                    if LastLow >= LastPivotLow:
                        TriggerPrice = float(round(LastHigh + LastHigh * self.DeltaTrigger / 100, self.PricePrecision))
                        Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                        self.PositionAmount = Amount
                        self.LongOrderPrice = TriggerPrice
                        self.LastHighForLong = LastHigh # Need for next moving SL
                else: # There is open long order
                    # Check the order is triggered
                    if LastHigh > self.LongOrderPrice:
                        self.LongPosition = True
                        self.LongAvgPrice = self.LongOrderPrice
                        LastPivotStopLoss = float(round(self.LowPivot[1] - self.LowPivot[1] * self.DeltaSL / 100, self.PricePrecision))
                        StopPrice = float(round(self.LongAvgPrice - self.LongAvgPrice * self.StopLoss / 100, self.PricePrecision))
                        StopPrice = StopPrice if StopPrice > LastPivotStopLoss else LastPivotStopLoss
                        ProfitPrice = float(round(self.LongAvgPrice + self.LongAvgPrice * self.TakeProfit / 100, self.PricePrecision))
                        
                        self.PositionEntry = self.LongAvgPrice
                        self.LongStopLoss = StopPrice
                        self.LongTakeProfit = ProfitPrice
                    else: # Still no filled, Move Stop Trigger
                        # If the last candle low price is greater than last pivot low, continue.
                        if LastLow >= LastPivotLow:
                            if self.LastHighForLong > LastHigh:
                                # Cancel Original Open Long Order
                                self.LongOrderPrice = None
                                TriggerPrice = float(round(LastHigh + LastHigh * self.DeltaTrigger / 100, self.PricePrecision))
                                self.LongOrderPrice = TriggerPrice
                                self.LastHighForLong = LastHigh
                        else:
                            # Cancel Original Open Long Order
                            self.LongOrderPrice = None
                            self.LastHighForLong = 0

            else:
                if LastHigh > self.LongTakeProfit: # In case of takeprofit
                    self.position.add_position({
                        "Amount": self.PositionAmount,
                        "Entry": self.PositionEntry,
                        "Exit": self.LongTakeProfit,
                        "Side": "Long"
                    })
                    self.LongOrderPrice = None
                    self.LongStopLoss = None
                    self.LongTakeProfit = None
                    self.LongPosition = False
                    self.LastHighForLong = 0
                elif LastLow < self.LongStopLoss: # In case of stoploss
                    self.position.add_position({
                        "Amount": self.PositionAmount,
                        "Entry": self.PositionEntry,
                        "Exit": self.LongStopLoss,
                        "Side": "Long"
                    })
                    self.LongOrderPrice = None
                    self.LongStopLoss = None
                    self.LongTakeProfit = None
                    self.LongPosition = False
                    self.LastHighForLong = 0
            if self.ShortOrderPrice != None and self.ShortPosition == False: # In the previous downtrend, if there is open short order.
                self.ShortOrderPrice = None
                self.LastLowForShort = 0
        if self.Trend == "Down":
            if self.ShortPosition == False:
                if self.ShortOrderPrice == None: # There is no any open short order
                    if LastPivotHigh >= LastHigh:
                        TriggerPrice = float(round(LastLow - LastLow * self.DeltaTrigger / 100, self.PricePrecision))
                        Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                        self.PositionAmount = Amount
                        self.ShortOrderPrice = TriggerPrice
                        self.LastLowForShort = LastLow # Need for next moving SL
                else: # There is open short order
                    # Check if the open short order is filled or not
                    if self.ShortOrderPrice > LastLow:
                        self.ShortPosition = True
                        self.ShortAvgPrice = self.ShortOrderPrice
                        LastPivotStopLoss = float(round(LastPivotHigh + LastPivotHigh * self.DeltaSL / 100, self.PricePrecision))
                        StopPrice = float(round(self.ShortAvgPrice + self.ShortAvgPrice * self.StopLoss / 100, self.PricePrecision))
                        StopPrice = LastPivotStopLoss if StopPrice > LastPivotStopLoss else StopPrice
                        ProfitPrice = float(round(self.ShortAvgPrice - self.ShortAvgPrice * self.TakeProfit / 100, self.PricePrecision))

                        self.PositionEntry = self.ShortAvgPrice
                        self.ShortStopLoss = StopPrice
                        self.ShortTakeProfit = ProfitPrice
                    else: # Still no filled, Move Stop Trigger
                        # If the last candle high price is greater than last pivot high, continue.
                        if LastHigh < LastPivotHigh:
                            if self.LastLowForShort < LastLow:
                                # Cancel Original Open Long Order
                                self.ShortOrderPrice = None
                                TriggerPrice = float(round(LastLow - LastLow * self.DeltaTrigger / 100, self.PricePrecision))
                                self.ShortOrderPrice = TriggerPrice
                                self.LastLowForShort = LastLow
                        else:
                            # Cancel Original Open Long Order
                            self.ShortOrderPrice = None
                            self.LastLowForShort = 0

            else:
                if self.ShortTakeProfit > LastLow: # In case of takeprofit
                    self.position.add_position({
                        "Amount": self.PositionAmount,
                        "Entry": self.PositionEntry,
                        "Exit": self.ShortTakeProfit,
                        "Side": "Short"
                    })
                    self.ShortOrderPrice = None
                    self.ShortStopLoss = None
                    self.ShortTakeProfit = None
                    self.ShortPosition = False
                    self.LastLowForShort = 0
                elif self.ShortStopLoss < LastHigh: # In case of stoploss
                    self.position.add_position({
                        "Amount": self.PositionAmount,
                        "Entry": self.PositionEntry,
                        "Exit": self.ShortStopLoss,
                        "Side": "Short"
                    })
                    self.ShortOrderPrice = None
                    self.ShortStopLoss = None
                    self.ShortTakeProfit = None
                    self.ShortPosition = False
                    self.LastLowForShort = 0
            if self.LongOrderPrice != None and self.LongPosition == False: # In the previous downtrend, if there is open short order.
                self.LongOrderPrice = None
                self.LastHighForLong = 0
class HandleResult():
    def __init__(self):
        self.client = Client(API_KEY, API_SECRET)
        self.args = SimpleNamespace()
        self.args.symbol = "BTCUSDT"
        self.args.amount = 5000.0
        self.args.pivotstep = 5
        self.args.delta = 0
        self.args.deltasl = 0.15
        self.args.deltatrigger = 0.05
        self.args.stoploss = 0.4
        self.args.takeprofit = 0.8
        self.args.startTime = 1635768000000
        self.args.duration = 30
        self.args.interval = 5
        self.args.testnet = False
        date = datetime.utcfromtimestamp(self.args.startTime / 1000)
        year = date.year
        month = date.month
        self.filename = f"backtest/{self.args.symbol}_{year}_{month}_{self.args.interval}m_{self.args.pivotstep}step_{self.args.stoploss}sl_{self.args.takeprofit}tp.csv"

    def main(self):
        if not os.path.exists(self.filename):
            logger.warning("initializing csv...")
            headers = ["Symbol", "Timeline", "Amount", "PivotStep", "Delta", "DeltaSL", "DeltaTrigger", "StopLoss", "StartTime", "StartTime(Human)", "TotalTrades", "Success", "Failure", "Total Fees", "Total PnL" ]
            with open (self.filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
        startTime = self.args.startTime
        startTimes = []
        for _ in range(30):
            startTimes.append(startTime)
            startTime = int(startTime + timedelta(hours=24).total_seconds() * 1000)
        # multiprocessing
        # executor = Parallel(n_jobs=cpu_count(), backend='multiprocessing')
        # tasks = (delayed(self.process_trade)(s) for s in startTimes)
        # results = executor(tasks)
        # self.result_to_csv(results)
        for s in startTimes:
            result = self.process_trade(s)
            self.result_to_csv(result)
        # PlotPivot(res, self.args.pivotstep).draw_plot()
    def process_trade(self, startTime):
        maxLimit = int(1440 / self.args.interval)
        res = self.client.futures_klines(symbol=self.args.symbol, interval=str(self.args.interval) + "m", startTime=startTime, limit=maxLimit)
        if res and len(res) > 0:
            position = Position(self.args.amount)
            bt = BackTest(self.args, position=position)
            for row in res:
                bt.handle_kline_msg(row)
            totalTradeCount, pnl, totalFee, successCount, failureCount = position.calculate_pnl()
            logger.info("Total Trades: " + str(totalTradeCount))
            logger.info_magenta("Total PnL: " + str(pnl))
            logger.info_blue("Total Fees: " + str(totalFee))
            logger.success("Total Success: " + str(successCount))
            logger.error("Total Failure: " + str(failureCount))
            humanTime = datetime.utcfromtimestamp(startTime / 1000)
            return (
                self.args.symbol,
                self.args.interval,
                self.args.amount,
                self.args.pivotstep,
                self.args.delta,
                self.args.deltasl,
                self.args.deltatrigger,
                self.args.stoploss,
                startTime,
                humanTime,
                totalTradeCount,
                successCount,
                failureCount,
                totalFee,
                pnl
            )
    def result_to_csv(self, results):
        logger.warning("Writting csv...")
        with open (self.filename, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(results)

if __name__ == "__main__":
  HandleResult().main()