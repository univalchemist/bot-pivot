from binance.enums import *
from collections import deque
import csv
import os.path
import argparse, sys
from datetime import timedelta, datetime

from utils.arguments import Argument
from utils.log import logbook
from parameters import *
from trade.order import *
from utils.position import Position

logger = logbook()

parser = argparse.ArgumentParser(description='Set your Symbol, TradeAmount, PivotStep, DeltaPivot, DeltaSL, DeltaTrigger, StopLoss, Testnet. Example: "main.py -s BTCUSDT"')
parser.add_argument('-s', '--symbol', default="BTCUSDT", help='str, Pair for trading e.g. "-s BTCUSDT"')
parser.add_argument('-a', '--amount', default=5000.0, type=float, help='float, Amount in USDT to trade e.g. "-a 50"')
parser.add_argument('-ps', '--pivotstep', default=5, type=int, help='int, Left/Right candle count to calculate Pivot e.g. "-ps 5"')
parser.add_argument('-d', '--delta', default=0, type=float, help='float, delta to determine trend e.g. "-d 10.0"')
parser.add_argument('-dsl', '--deltasl', default=0.05, type=float, help='float, delta SL to calculate with HH, LL. its value is percentage e.g. "-dsl 0.0005"')
parser.add_argument('-dt', '--deltatrigger', default=0.15, type=float, help='float, delta percent to calculate trigger open order. its value is percentage e.g. "-dt 0.15"')
parser.add_argument('-sl', '--stoploss', default=0.4, type=float, help='float, Percentage Stop Loss"-sl 0.4" ')
parser.add_argument('-tp', '--takeprofit', default=0.8, type=float, help='float, Percentage of Take Profit"-sl 0.8" ')
parser.add_argument('-st', '--starttime', required=True, type=int, help='long, timestamp milliseconds for start time"-sl 1635768000000" ')
parser.add_argument('-du', '--duration', required=True, type=int, help='int, duration as days to test"-sl 30" ')
parser.add_argument('-i', '--interval', default=1, type=int, help='int, time interval as minute"-i 1" ')
parser.add_argument('-test', '--testnet',  action="store_true", help='Run script in testnet or live mode.')
args = parser.parse_args()

class BackTest():
    def __init__(self, args, position=Position()):
      self.args = args
      self.Symbol = args.symbol
      self.PivotStep = args.pivotstep # Default is 5
      self.MaxlenKlines = self.PivotStep*2 + 1
      self.Klines = deque(maxlen=self.MaxlenKlines)
      self.HighPivot = deque(maxlen=2)
      self.LowPivot = deque(maxlen=2)
      self.NextPivot = None
      self.Trend = None
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
            self.mock_order_tp_sl()
    def mock_order_tp_sl(self):
        logger.info("The Trend is " + self.Trend)
        LastPivotLow = self.LowPivot[1]
        LastPivotHigh = self.HighPivot[1]
        LastCandle = self.Klines[-1]
        LastHigh = float(LastCandle["High"])
        LastLow = float(LastCandle["Low"])
        if self.Trend == TREND_UP:
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
        if self.Trend == TREND_DOWN:
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
        self.args = args
        date = datetime.utcfromtimestamp(self.args.starttime / 1000)
        year = date.year
        month = date.month
        self.filename = f"backtest/{self.args.symbol}_{year}_{month}_{self.args.interval}m_{self.args.pivotstep}step_{self.args.stoploss}sl_{self.args.takeprofit}tp.csv"

    def main(self):
        if not os.path.exists(self.filename):
            logger.warning("initializing csv...")
            headers = ["Symbol", "Timeline", "Amount", "PivotStep", "Delta", "DeltaSL", "DeltaTrigger", "TakeProfit", "StopLoss", "StartTime", "StartTime(Human)", "TotalTrades", "Success", "Failure", "Total Fees", "Total PnL" ]
            with open (self.filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
        startTime = self.args.starttime
        startTimes = []
        for _ in range(30):
            startTimes.append(startTime)
            startTime = int(startTime + timedelta(hours=24).total_seconds() * 1000)
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
                self.args.takeprofit,
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

    if args.starttime == None:
        logger.error("Please Check Start Time e.g. -st 1635768000000")
        logger.error("exit!")
        sys.exit()
    if args.duration == None:
        logger.error("Please duration e.g. -du 30")
        logger.error("exit!")
        sys.exit()
    else:
        Argument().set_args(args)
        HandleResult().main()