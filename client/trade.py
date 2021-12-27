from time import sleep
from binance import Client
from binance.enums import *
from collections import deque
import json
import websocket
import datetime as dt
from threading import Lock, Thread
from .client import BinanceClient
from .position import Position
from utils.enums import *

from utils.log import Logbook, Logger
from parameters import *
from .order import Order

logger = Logger()
ERROR = Logbook().createERRORLogger()

class Trade():
    def __init__(self, args, pricePrecision, qtyPrecision):
        logger.info_magenta("Trade Class initializing...")
        self.args = args
        self.Symbol = args.symbol
        self.Delta = args.delta # Default is 10
        self.DeltaSL = args.deltasl # Default is 0.05
        self.PricePrecision = pricePrecision
        self.QtyPrecision = qtyPrecision
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

        self.LongOriginalProfitOrderId = None
        self.LongOriginalStopOrderId = None
        self.ShortOriginalProfitOrderId = None
        self.ShortOriginalStopOrderId = None

        # self.LastPivotLow = 0
        # self.LastPivotHigh = 0
        # self.LastHigh = 0
        # self.LastLow = 0
        self.MA_100 = 0

        self.PositionAmount = 0
        self.PositionEntry = 0

        self.StartStreamTime = 0

        self.client = BinanceClient(self.args).client
        self.order = Order(self.args)
        self.position = Position(self.args)
        self.get_precision()
        self.check_long_position()
        self.check_short_position()
        self.thread_stream()
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
    def thread_stream(self):
        Thread(target=self.start_user_data_stream).start()
    def start_user_data_stream(self):
        try:
            key = self.client.futures_stream_get_listen_key()
            BASE_URL = DATA_STREAM_URL_TESTNET if self.args.testnet else DATA_STREAM_URL
            SOCKET = BASE_URL + "/ws/" + key
            self.StartStreamTime = dt.datetime.now().timestamp()
            ws = websocket.WebSocketApp(SOCKET, on_open=self.on_open, on_close=self.on_close, on_message=self.on_message)
            ws.run_forever()
        except Exception as e:
            logger.error("Stream User Data Connection error!")
            ERROR.error(e)
    def keep_alive(self):
        now = dt.datetime.now().timestamp()
        diff = now - self.StartStreamTime # Difference between the current time and the previous activated time
        if diff > 1800: # If difference is greater than 1800s(30m), activate listenkey again
            try:
                logger.info_blue("putting new listenkey to keep stream alive...")
                new_key = self.client.futures_stream_get_listen_key()
                self.client.futures_stream_keepalive(new_key)
                self.StartStreamTime = now
            except Exception as e:
                logger.error("Putting new listenkey to keep alive error!")
                ERROR.error(e)

    def on_open(self, ws):
        logger.info("opened connection to User Data streams")

    def on_close(self, ws):
        logger.error("closed connection to User Data streams")

    def on_message(self, ws, message):
        logger.info_magenta("message received from User Data streams")
        json_message = json.loads(message)
        print(json_message)
        # if json_message["e"] == "listenKeyExpired": self.keep_alive()
        if json_message["e"] == "ORDER_TRADE_UPDATE": self.handle_order_update(json_message)
    def handle_order_update(self, msg):
        info = msg["o"]
        symbol = info["s"] # BTCUSDT
        side = info["S"] # BUY/SELL
        position_side = info["ps"] # LONG/SHORT
        order_type = info["o"] # STOP_MARKET
        order_status = info["X"] # NEW
        order_id = info["i"] # 5671234
        reduce_only = info["R"] # TRUE
        close_position = info["cp"] # FALSE
        original_quantity = info["q"] # Quantity
        avg_price = info["ap"] # Average Filled Price
        # Long Position
        if position_side == POSITION_LONG:
            if side == SIDE_BUY:
                if order_status == ORDER_STATUS_NEW: # If order is new, it is open long order
                    self.LongOrderID = order_id
                    self.LastHighForLong = self.LastHigh # Need for next moving SL
                elif order_status == ORDER_STATUS_FILLED: # If order is filled, create SL/TP order
                    self.LongPosition = True
                    self.LongAvgPrice = float(avg_price)
                    self.PositionAmount = original_quantity
                    # Should open SL/TP order
                    # LastPivotStopLoss = float(round(self.LastPivotLow - self.LastPivotLow * self.DeltaSL / 100, self.PricePrecision))
                    # StopPrice = float(round(self.LongAvgPrice - self.LongAvgPrice * self.StopLoss / 100, self.PricePrecision))
                    # StopPrice = StopPrice if StopPrice > LastPivotStopLoss else LastPivotStopLoss
                    ProfitPrice = float(round(self.LongAvgPrice + self.LongAvgPrice * self.TakeProfit / 100, self.PricePrecision))
                    self.order.close_long_stop_market(self.MA_100)
                    sleep(1)
                    self.order.close_long_take_profit_market(ProfitPrice)
                    self.PositionEntry = self.LongAvgPrice
                    self.LongOrderID = None
                else: # Order status is CANCELED, PENDING_CANCEL, REJECTED, EXPIRED
                    self.LongOrderID = None
                    self.LastHighForLong = 0
                # TODO if PARTIALLY_FILLED
            elif reduce_only == True and close_position == True: # SELL and reduct & close_position is true, it should be SL/TP order
                # In case of Take Profit Order
                if order_type == FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET:
                    if order_status == ORDER_STATUS_NEW: self.LongProfitOrderId = order_id
                    elif order_status == ORDER_STATUS_EXPIRED: # when stop-market/take-profit-market is filled, it is expired and then changed to market order
                        self.LongOriginalProfitOrderId = self.LongProfitOrderId
                        self.LongProfitOrderId = None
                        
                elif order_type == FUTURE_ORDER_TYPE_MARKET and order_id == self.LongOriginalProfitOrderId: # The previous order is expired and it is chanegd to market order
                    if order_status == ORDER_STATUS_NEW: self.LongProfitOrderId = order_id
                    elif order_status == ORDER_STATUS_FILLED:
                        self.LongOriginalProfitOrderId = None
                        self.LongProfitOrderId = None
                        self.LongPosition = False
                        self.LastHighForLong = 0
                        # Cancel SL order
                        self.order.cancel_order(self.LongStopOrderId)
                # In case of Stop Loss Order
                if order_type == FUTURE_ORDER_TYPE_STOP_MARKET:
                    if order_status == ORDER_STATUS_NEW: self.LongStopOrderId = order_id
                    elif order_status == ORDER_STATUS_EXPIRED:
                        self.LongOriginalStopOrderId = self.LongStopOrderId
                        self.LongStopOrderId = None
                elif order_type == FUTURE_ORDER_TYPE_MARKET and order_id == self.LongOriginalStopOrderId:
                    if order_status == ORDER_STATUS_NEW: self.LongStopOrderId = order_id
                    elif order_status == ORDER_STATUS_FILLED:
                        self.LongOriginalStopOrderId = None
                        self.LongStopOrderId = None
                        self.LongPosition = False
                        self.LastHighForLong = 0
                        # Cancel TP order
                        self.order.cancel_order(self.LongProfitOrderId)
        # Short Position
        elif position_side == POSITION_SHORT:
            if side == SIDE_SELL:
                if order_status == ORDER_STATUS_NEW: # If order is new, it is open short order
                    self.ShortOrderID = order_id
                    self.LastLowForShort = self.LastLow # Need for next moving SL
                elif order_status == ORDER_STATUS_FILLED: # If order is filled, create SL/TP order
                    self.ShortPosition = True
                    self.ShortAvgPrice = float(avg_price)
                    self.PositionAmount = original_quantity
                    # LastPivotStopLoss = float(round(self.LastPivotHigh + self.LastPivotHigh * self.DeltaSL / 100, self.PricePrecision))
                    # StopPrice = float(round(self.ShortAvgPrice + self.ShortAvgPrice * self.StopLoss / 100, self.PricePrecision))
                    # StopPrice = LastPivotStopLoss if StopPrice > LastPivotStopLoss else StopPrice
                    ProfitPrice = float(round(self.ShortAvgPrice - self.ShortAvgPrice * self.TakeProfit / 100, self.PricePrecision))
                    self.order.close_short_stop_market(self.MA_100)
                    sleep(1)
                    self.order.close_short_take_profit_market(ProfitPrice)
                    self.PositionEntry = self.LongAvgPrice
                    self.ShortOrderID = None
                else: # Order status is CANCELED, PENDING_CANCEL, REJECTED, EXPIRED
                    self.ShortOrderID = None
                    self.LastLowForShort = 0
                # TODO if PARTIALLY_FILLED
            elif reduce_only == True and close_position == True: # SELL and reduct & close_position is true, it should be SL/TP order
                # In case of Take Profit Order
                if order_type == FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET:
                    if order_status == ORDER_STATUS_NEW: self.ShortProfitOrderId = order_id
                    elif order_status == ORDER_STATUS_EXPIRED:
                        self.ShortOriginalProfitOrderId = self.ShortProfitOrderId
                        self.ShortProfitOrderId = None
                        
                elif order_type == FUTURE_ORDER_TYPE_MARKET and order_id == self.ShortOriginalProfitOrderId: # The previous order is expired and it is chanegd to market order
                    if order_status == ORDER_STATUS_NEW: self.ShortProfitOrderId = order_id
                    elif order_status == ORDER_STATUS_FILLED:
                        self.ShortOriginalProfitOrderId = None
                        self.ShortProfitOrderId = None
                        self.ShortPosition = False
                        self.LastLowForShort = 0
                        # Cancel SL order
                        self.order.cancel_order(self.ShortStopOrderId)
                # In case of Stop Loss Order
                if order_type == FUTURE_ORDER_TYPE_STOP_MARKET:
                    if order_status == ORDER_STATUS_NEW: self.ShortStopOrderId = order_id
                    elif order_status == ORDER_STATUS_EXPIRED:
                        self.ShortOriginalStopOrderId = self.ShortStopOrderId
                        self.ShortStopOrderId = None
                elif order_type == FUTURE_ORDER_TYPE_MARKET and order_id == self.ShortOriginalStopOrderId:
                    if order_status == ORDER_STATUS_NEW: self.ShortStopOrderId = order_id
                    elif order_status == ORDER_STATUS_FILLED:
                        self.ShortOriginalStopOrderId = None
                        self.ShortStopOrderId = None
                        self.ShortPosition = False
                        self.LastLowForShort = 0
                        # Cancel TP order
                        self.order.cancel_order(self.ShortProfitOrderId)

    def handle_order_tp_sl(self, Trend, LastHigh, LastLow, MA_100):
        self.keep_alive() # For checking listenkey expiration
        logger.info("The Trend is " + Trend)
        # self.LastPivotLow = LastPivotLow
        # self.LastPivotHigh = LastPivotHigh
        # self.LastHigh = LastHigh
        # self.LastLow = LastLow
        self.MA_100 = MA_100
        if Trend == TREND_UP:
            if self.LongPosition == False:
                if self.LongOrderID == None: # There is no any open long order
                    # if LastLow >= LastPivotLow:
                        TriggerPrice = float(round(LastHigh + LastHigh * self.DeltaTrigger / 100, self.PricePrecision))
                        Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                        self.order.open_long_stop_market(Amount, TriggerPrice)
                else: # There is open long order
                    if LastLow >= MA_100:
                        if self.LastHighForLong > LastHigh:
                            # Cancel Original Open Long Order and create new one
                            self.order.cancel_order(self.LongOrderID)
                            TriggerPrice = float(round(LastHigh + LastHigh * self.DeltaTrigger / 100, self.PricePrecision))
                            Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                            self.order.open_long_stop_market(Amount, TriggerPrice)

                    else:
                        # Cancel Original Open Long Order
                        self.order.cancel_order(self.LongOrderID)

            if self.ShortOrderID != None and self.ShortPosition == False: # In the previous downtrend, if there is open short order.
                self.order.cancel_order(self.ShortOrderID)
        if Trend == TREND_DOWN:
            if self.ShortPosition == False:
                if self.ShortOrderID == None: # There is no any open short order
                    # if LastPivotHigh >= LastHigh:
                        TriggerPrice = float(round(LastLow - LastLow * self.DeltaTrigger / 100, self.PricePrecision))
                        Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                        self.order.open_short_stop_market(Amount, TriggerPrice)
                else: # There is open short order
                    if LastHigh <= MA_100:
                        if self.LastLowForShort < LastLow:
                            # Cancel Original Open Short Order and create new one
                            self.order.cancel_order(self.ShortOrderID)
                            TriggerPrice = float(round(LastLow - LastLow * self.DeltaTrigger / 100, self.PricePrecision))
                            Amount = float(round(self.AmountPerTrade / TriggerPrice, self.QtyPrecision))
                            self.order.open_short_stop_market(Amount, TriggerPrice)
                    else:
                        # Cancel Original Open Long Order
                        self.order.cancel_order(self.ShortOrderID)
            if self.LongOrderID != None and self.LongPosition == False: # In the previous downtrend, if there is open short order.
                self.order.cancel_order(self.LongOrderID)

