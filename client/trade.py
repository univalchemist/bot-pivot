from binance import Client
from binance.enums import *
from collections import deque
from .client import create_client
from .position import Position
from utils.enums import *

from utils.log import Logger
from parameters import *
from .order import Order

logger = Logger()

class Trade():
    def __init__(self, args):
        logger.info_magenta("Trade Class initializing...")
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

        self.LongPosition = False
        self.ShortPosition = False
        self.LongOrderID = None
        self.ShortOrderID = None
        self.LastHighForLong = 0
        self.LastLowForShort = 0
        self.LongAvgPrice = 0
        self.ShortAvgPrice = 0
        self.LongStopOrderId = None
        self.LongProfitOrderId = None
        self.ShortStopOrderId = None
        self.ShortProfitOrderId = None

        self.PositionAmount = 0
        self.PositionEntry = 0

        self.client = create_client(self.args)
        self.order = Order(self.args)
        self.position = Position(self.args)
        self.get_precision()
        self.check_long_position()
        self.check_short_position()
    def get_precision(self):
        info = self.client.futures_exchange_info()
        for x in info["symbols"]:
            if x["symbol"] == self.Symbol:
                self.PricePrecision = int(x["pricePrecision"])
                self.QtyPrecision = int(x["quantityPrecision"])
    def check_long_position(self):
        long, _ = self.position.check_is_position()
        if long[0]:
            self.LongPosition = True
            # Check if there is SL/TP order
            IS_SL, slOrderId = self.order.check_is_sl_tp_order(positionSide=POSITION_LONG, checkPoint=POSITION_CHECK_SL)
            if IS_SL: self.LongStopOrderId = slOrderId
            else:
                # Close the current position by market order
                self.order.close_long_market(long[1])
                self.LongPosition = False
                return

            IS_TP, tpOrderId = self.order.check_is_sl_tp_order(positionSide=POSITION_LONG, checkPoint=POSITION_CHECK_TP)
            if IS_TP: self.LongProfitOrderId = tpOrderId
            else:
                # Close the current position by market order
                self.order.close_long_market(long[1])
                self.LongPosition = False
                return
    def check_short_position(self):
        _, short = self.position.check_is_position()
        if short[0]:
            self.ShortPosition = True
            # Check if there is SL/TP order
            IS_SL, slOrderId = self.order.check_is_sl_tp_order(positionSide=POSITION_SHORT, checkPoint=POSITION_CHECK_SL)
            if IS_SL: self.ShortStopOrderId = slOrderId
            else:
                # Close the current position by market order
                self.order.close_long_market(short[1])
                self.ShortPosition = False
                return

            IS_TP, tpOrderId = self.order.check_is_sl_tp_order(positionSide=POSITION_SHORT, checkPoint=POSITION_CHECK_TP)
            if IS_TP: self.LongProfitOrderId = tpOrderId
            else:
                # Close the current position by market order
                self.order.close_long_market(short[1])
                self.ShortPosition = False
                return

    def check_position_order(self):
        # Check Long Position
        if self.LongProfitOrderId: # In case of takeprofit
            res = self.client.futures_get_order(symbol=self.Symbol, orderId=self.LongProfitOrderId)
            if res["status"] == ORDER_STATUS_FILLED:
                # TODO:
                # Store trade result(Entry, Exit, Amount, Fee, PnL)
                self.LongProfitOrderId = None
                self.LongPosition = False
                self.LastHighForLong = 0
                # Cancel SL order
                CancelOrder = self.order.cancel_order(self.LongStopOrderId)
                if CancelOrder != None and CancelOrder["orderId"] and CancelOrder["status"] == ORDER_STATUS_CANCELED:
                    self.LongStopOrderId = None
            elif res["status"] != ORDER_STATUS_NEW:
                # TODO
                # The TP order is not NEW or FILLED(PARTIALLY_FILLED, CANCELED, PENDING_CANCEL, REJECTED, EXPIRED)
                # For now close position by market order
                self.order.cancel_order(self.LongProfitOrderId)
                self.check_long_position()

        else: self.check_long_position()
        if self.LongStopOrderId: # In case of stoploss
            res = self.client.futures_get_order(symbol=self.Symbol, orderId=self.LongStopOrderId)
            if res["status"] == ORDER_STATUS_FILLED:
                # TODO:
                # Store trade result(Entry, Exit, Amount, Fee, PnL)
                self.LongStopOrderId = None
                self.LongPosition = False
                self.LastHighForLong = 0
                # Cancel SL order
                CancelOrder = self.order.cancel_order(self.LongProfitOrderId)
                if CancelOrder != None and CancelOrder["orderId"] and CancelOrder["status"] == ORDER_STATUS_CANCELED:
                    self.LongProfitOrderId = None
            elif res["status"] != ORDER_STATUS_NEW:
                # TODO
                # The SL order is not NEW or FILLED(PARTIALLY_FILLED, CANCELED, PENDING_CANCEL, REJECTED, EXPIRED)
                # For now close position by market order
                self.order.cancel_order(self.LongStopOrderId)
                self.check_long_position()
        else: self.check_long_position()
        # Check Short Postion
        if self.ShortProfitOrderId: # In case of takeprofit
            res = self.client.futures_get_order(symbol=self.Symbol, orderId=self.ShortProfitOrderId)
            if res["status"] == ORDER_STATUS_FILLED:
                # TODO:
                # Store trade result(Entry, Exit, Amount, Fee, PnL)
                self.ShortProfitOrderId = None
                self.ShortPosition = False
                self.LastLowForShort = 0
                # Cancel SL order
                CancelOrder = self.order.cancel_order(self.ShortStopOrderId)
                if CancelOrder != None and CancelOrder["orderId"] and CancelOrder["status"] == ORDER_STATUS_CANCELED:
                    self.ShortStopOrderId = None
            elif res["status"] != ORDER_STATUS_NEW:
                # TODO
                # The TP order is not NEW or FILLED(PARTIALLY_FILLED, CANCELED, PENDING_CANCEL, REJECTED, EXPIRED)
                # For now close position by market order
                self.order.cancel_order(self.ShortProfitOrderId)
                self.check_short_position()
        else: self.check_short_position()
        if self.ShortStopOrderId: # In case of stoploss
            res = self.client.futures_get_order(symbol=self.Symbol, orderId=self.ShortStopOrderId)
            if res["status"] == ORDER_STATUS_FILLED:
            # TODO:
            # Store trade result(Entry, Exit, Amount, Fee, PnL)
                self.ShortStopOrderId = None
                self.ShortPosition = False
                self.LastLowForShort = 0
                # Cancel SL order
                CancelOrder = self.order.cancel_order(self.ShortProfitOrderId)
                if CancelOrder != None and CancelOrder["orderId"] and CancelOrder["status"] == ORDER_STATUS_CANCELED:
                    self.ShortProfitOrderId = None
            elif res["status"] != ORDER_STATUS_NEW:
                # TODO
                # The SL order is not NEW or FILLED(PARTIALLY_FILLED, CANCELED, PENDING_CANCEL, REJECTED, EXPIRED)
                # For now close position by market order
                self.order.cancel_order(self.ShortStopOrderId)
                self.check_short_position()
        else: self.check_short_position()

    def handle_order_tp_sl(self, Trend, LastPivotLow, LastPivotHigh, LastCandle):
        self.check_position_order()
        logger.info("The Trend is " + Trend)
        LastHigh = float(LastCandle["High"])
        LastLow = float(LastCandle["Low"])
        if Trend == TREND_UP:
            if self.LongPosition == False:
                if self.LongOrderID == None: # There is no any open long order
                    if LastLow >= LastPivotLow:
                        TriggerPrice = float(round(LastHigh + LastHigh * self.DeltaTrigger / 100, self.PricePrecision))
                        Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                        NewOrder = self.order.open_long_stop_market(Amount, TriggerPrice)
                        if NewOrder != None and NewOrder["orderId"] and NewOrder["status"] == ORDER_STATUS_NEW:
                            self.PositionAmount = Amount
                            self.LongOrderID = NewOrder["orderId"]
                            self.LastHighForLong = LastHigh # Need for next moving SL
                else: # There is open long order
                    res = self.client.futures_get_order(symbol=self.Symbol, orderId=self.LongOrderID)
                    # Check the order is triggered
                    if res["status"] == ORDER_STATUS_FILLED:
                        self.LongPosition = True
                        self.LongAvgPrice = float(res["avgPrice"])
                        LastPivotStopLoss = float(round(LastPivotLow - LastPivotLow * self.DeltaSL / 100, self.PricePrecision))
                        StopPrice = float(round(self.LongAvgPrice - self.LongAvgPrice * self.StopLoss / 100, self.PricePrecision))
                        StopPrice = StopPrice if StopPrice > LastPivotStopLoss else LastPivotStopLoss
                        ProfitPrice = float(round(self.LongAvgPrice + self.LongAvgPrice * self.TakeProfit / 100, self.PricePrecision))
                        StopOrder = self.order.close_long_stop_market(StopPrice)
                        if StopOrder != None and StopOrder["orderId"] and StopOrder["status"] == ORDER_STATUS_NEW:
                            self.LongStopOrderId = StopOrder["orderId"]
                        TakeProfitOrder = self.order.close_long_take_profit_market(ProfitPrice)
                        if TakeProfitOrder != None and TakeProfitOrder["orderId"] and TakeProfitOrder["status"] == ORDER_STATUS_NEW:
                            self.LongProfitOrderId = TakeProfitOrder["orderId"]
                        self.PositionEntry = self.LongAvgPrice
                        self.LongOrderID = None
                    elif res["status"] == ORDER_STATUS_NEW: # Still no filled, Move Stop Trigger
                        # If the last candle low price is greater than last pivot low, continue.
                        if LastLow >= LastPivotLow:
                            if self.LastHighForLong > LastHigh:
                                # Cancel Original Open Long Order
                                OriginalOrder = self.order.cancel_order(self.LongOrderID)
                                if OriginalOrder != None and OriginalOrder["orderId"] and OriginalOrder["status"] == ORDER_STATUS_CANCELED:
                                    self.LongOrderID = None
                                    self.LastHighForLong = 0
                                    TriggerPrice = float(round(LastHigh + LastHigh * self.DeltaTrigger / 100, self.PricePrecision))
                                    Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                                    NewOrder = self.order.open_long_stop_market(Amount, TriggerPrice)
                                    if NewOrder != None and NewOrder["orderId"] and NewOrder["status"] == ORDER_STATUS_NEW:
                                        self.LongOrderID = NewOrder["orderId"]
                                        self.LastHighForLong = LastHigh
                        else:
                            # Cancel Original Open Long Order
                            OriginalOrder = self.order.cancel_order(self.LongOrderID)
                            if OriginalOrder != None and OriginalOrder["orderId"] and OriginalOrder["status"] == ORDER_STATUS_CANCELED:
                                self.LongOrderID = None
                                self.LastHighForLong = 0
                    # TODO
                    else: # Order status is PARTIALLY_FILLED, CANCELED, PENDING_CANCEL, REJECTED, EXPIRED
                        self.LongOrderID = None
                        self.LastHighForLong = 0
            if self.ShortOrderID != None and self.ShortPosition == False: # In the previous downtrend, if there is open short order.
                CloseOpenShort = self.order.cancel_order(self.ShortOrderID)
                if CloseOpenShort != None and CloseOpenShort["orderId"] and CloseOpenShort["status"] == ORDER_STATUS_CANCELED:
                    self.ShortOrderID = None
                    self.LastLowForShort = 0
        if Trend == TREND_DOWN:
            if self.ShortPosition == False:
                if self.ShortOrderID == None: # There is no any open short order
                    if LastPivotHigh >= LastHigh:
                        TriggerPrice = float(round(LastLow - LastLow * self.DeltaTrigger / 100, self.PricePrecision))
                        Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                        NewOrder = self.order.open_short_stop_market(Amount, TriggerPrice)
                        if NewOrder != None and NewOrder["orderId"] and NewOrder["status"] == ORDER_STATUS_NEW:
                            self.PositionAmount = Amount
                            self.ShortOrderID = NewOrder["orderId"]
                            self.LastLowForShort = LastLow # Need for next moving SL
                else: # There is open short order
                    res = self.client.futures_get_order(symbol=self.Symbol, orderId=self.ShortOrderID)
                    # Check if the open short order is filled or not
                    if res["status"] == ORDER_STATUS_FILLED:
                        self.ShortPosition = True
                        self.ShortAvgPrice = float(res["avgPrice"])
                        LastPivotStopLoss = float(round(LastPivotHigh + LastPivotHigh * self.DeltaSL / 100, self.PricePrecision))
                        StopPrice = float(round(self.ShortAvgPrice + self.ShortAvgPrice * self.StopLoss / 100, self.PricePrecision))
                        StopPrice = LastPivotStopLoss if StopPrice > LastPivotStopLoss else StopPrice
                        ProfitPrice = float(round(self.ShortAvgPrice - self.ShortAvgPrice * self.TakeProfit / 100, self.PricePrecision))
                        StopOrder = self.order.close_short_stop_market(StopPrice)
                        if StopOrder != None and StopOrder["orderId"] and StopOrder["status"] == ORDER_STATUS_NEW:
                            self.ShortStopOrderId = StopOrder["orderId"]
                        TakeProfitOrder = self.order.close_short_take_profit_market(ProfitPrice)
                        if TakeProfitOrder != None and TakeProfitOrder["orderId"] and TakeProfitOrder["status"] == ORDER_STATUS_NEW:
                            self.ShortProfitOrderId = TakeProfitOrder["orderId"]
                        self.PositionEntry = self.ShortAvgPrice
                        self.ShortOrderID = None
                    elif res["status"] == ORDER_STATUS_NEW: # Still no filled, Move Stop Trigger
                        # If the last candle high price is greater than last pivot high, continue.
                        if LastHigh < LastPivotHigh:
                            if self.LastLowForShort < LastLow:
                                # Cancel Original Open Long Order
                                OriginalOrder = self.order.cancel_order(self.ShortOrderID)
                                if OriginalOrder != None and OriginalOrder["orderId"] and OriginalOrder["status"] == ORDER_STATUS_CANCELED:
                                    self.ShortOrderID = None
                                    TriggerPrice = float(round(LastLow - LastLow * self.DeltaTrigger / 100, self.PricePrecision))
                                    Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                                    NewOrder = self.order.open_short_stop_market(Amount, TriggerPrice)
                                    if NewOrder != None and NewOrder["orderId"] and NewOrder["status"] == ORDER_STATUS_NEW:
                                        self.ShortOrderID = NewOrder["orderId"]
                                        self.LastLowForShort = LastLow
                        else:
                            # Cancel Original Open Long Order
                            OriginalOrder = self.order.cancel_order(self.ShortOrderID)
                            if OriginalOrder != None and OriginalOrder["orderId"] and OriginalOrder["status"] == ORDER_STATUS_CANCELED:
                                self.ShortOrderID = None
                                self.LastLowForShort = 0
                    else: # Order status is PARTIALLY_FILLED, CANCELED, PENDING_CANCEL, REJECTED, EXPIRED
                        self.ShortOrderID = None
                        self.LastLowForShort = 0
            if self.LongOrderID != None and self.LongPosition == False: # In the previous downtrend, if there is open short order.
                CloseOpenLong = self.order.cancel_order(self.LongOrderID)
                if CloseOpenLong != None and CloseOpenLong["orderId"] and CloseOpenLong["status"] == ORDER_STATUS_CANCELED:
                    self.LongOrderID = None
                    self.LastHighForLong = 0
