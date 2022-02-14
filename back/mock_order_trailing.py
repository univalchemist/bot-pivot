from binance.enums import *
from collections import deque
import csv
import os.path
import argparse, sys
from datetime import timedelta, datetime

from utils.arguments import Argument
from utils.log import Logger
from parameters import *
from client.order import *
from .position import Position

logger = Logger()

class MockOrder():
  def __init__(self, args, position):
    self.args = args
    self.Symbol = args.symbol
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
  
  def mock_order_trailing_sl(self, LastHigh, LastLow):
        if self.LongPosition:
            if LastLow < self.LongStopLoss: # In case of stoploss
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
            elif LastLow > self.LongAvgPrice:
                self.LongAvgPrice = LastLow
                StopPrice = float(round(LastLow - LastLow * self.StopLoss / 100, self.PricePrecision))
                self.LongStopLoss = StopPrice

        if self.ShortPosition:
            if self.ShortStopLoss < LastHigh: # In case of stoploss
                self.position.add_position({
                    "Amount": self.PositionAmount,
                    "Entry": self.PositionEntry,
                    "Exit": self.ShortStopLoss,
                    "Side": "Short"
                })
                self.ShortOrderPrice = None
                self.ShortStopLoss = None
                self.ShortPosition = False
                self.LastLowForShort = 0
            elif LastHigh < self.ShortAvgPrice:
                self.ShortAvgPrice = LastHigh
                StopPrice = float(round(LastHigh + LastHigh * self.StopLoss / 100, self.PricePrecision))
                self.ShortStopLoss = StopPrice
        if self.LongPosition == False and self.ShortPosition == False:
            # if NextPivot == PIVOT_HIGH:
                # if self.LongPosition == False:
                    if self.LongOrderPrice == None: # There is no any open long order
                        # if LastLow >= MA_100:
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
                            StopPrice = float(round(self.LongAvgPrice - self.LongAvgPrice * self.StopLoss / 100, self.PricePrecision))
                            
                            self.PositionEntry = self.LongAvgPrice
                            self.LongStopLoss = StopPrice
                        else: # Still no filled, Move Stop Trigger
                            # If the last candle low price is greater than MA_100, continue.
                            # if LastLow >= MA_100:
                                if self.LastHighForLong > LastHigh:
                                    # Cancel Original Open Long Order
                                    self.LongOrderPrice = None
                                    TriggerPrice = float(round(LastHigh + LastHigh * self.DeltaTrigger / 100, self.PricePrecision))
                                    self.LongOrderPrice = TriggerPrice
                                    self.LastHighForLong = LastHigh

                # if self.ShortOrderPrice != None and self.ShortPosition == False: # In the previous downtrend, if there is open short order.
                #     self.ShortOrderPrice = None
                #     self.LastLowForShort = 0
            # elif NextPivot == PIVOT_LOW:
                # if self.ShortPosition == False:
                    if self.ShortOrderPrice == None: # There is no any open short order
                        # if MA_100 >= LastHigh:
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
                            StopPrice = float(round(self.ShortAvgPrice + self.ShortAvgPrice * self.StopLoss / 100, self.PricePrecision))

                            self.PositionEntry = self.ShortAvgPrice
                            self.ShortStopLoss = StopPrice
                        else: # Still no filled, Move Stop Trigger
                            # If the last candle high price is greater than last pivot high, continue.
                            # if LastHigh <= MA_100:
                                if self.LastLowForShort < LastLow:
                                    # Cancel Original Open Long Order
                                    self.ShortOrderPrice = None
                                    TriggerPrice = float(round(LastLow - LastLow * self.DeltaTrigger / 100, self.PricePrecision))
                                    self.ShortOrderPrice = TriggerPrice
                                    self.LastLowForShort = LastLow
                # if self.LongOrderPrice != None and self.LongPosition == False: # In the previous downtrend, if there is open short order.
                #     self.LongOrderPrice = None
                #     self.LastHighForLong = 0
            # else: # TREND_NONE
            #     self.LongOrderPrice = None
            #     self.LastHighForLong = 0
            #     self.ShortOrderPrice = None
            #     self.LastLowForShort = 0