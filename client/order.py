from binance import Client
from binance.enums import *
from parameters import *
from .client import create_client
from utils.log import Logbook, Logger
from utils.enums import *

logger = Logger()
ERROR = Logbook().createERRORLogger()

class Order():
  def __init__(self, args):
    self.args = args
    self.client = create_client(args)
  def open_long_stop_market(self, amount, stopPrice):
    try:
      res = self.client.futures_create_order(
            symbol=self.args.symbol,
            side=SIDE_BUY,
            positionSide=POSITION_LONG,
            type=FUTURE_ORDER_TYPE_STOP_MARKET,
            # workingType="MARK_PRICE",
            # timeInForce=TIME_IN_FORCE_GTC,
            quantity=amount,
            stopPrice=stopPrice
          )
      return res
    except Exception as e:
      error = f"Failed Open Long Order({self.args.symbol}, {amount}, {stopPrice})"
      logger.error(error)
      ERROR.error(error)
      ERROR.error(e)
      print(e)
      return None

  def close_long_stop_market(self, stopPrice):
    try:
      res = self.client.futures_create_order(
            symbol=self.args.symbol,
            side=SIDE_SELL,
            positionSide=POSITION_LONG,
            type=FUTURE_ORDER_TYPE_STOP_MARKET,
            # workingType="MARK_PRICE",
            timeInForce=TIME_IN_FORCE_GTC, # Good til cancel
            # quantity=amount, # No need if closePosition=True
            stopPrice=stopPrice,
            # reduceOnly=True,
            closePosition=True
          )
      return res
    except Exception as e:
      error = f"Failed Close Long SL Order({self.args.symbol}, {stopPrice})"
      logger.error(error)
      ERROR.error(error)
      ERROR.error(e)
      print(e)
      return None

  def close_long_market(self, amount):
    try:
      res = self.client.futures_create_order(
            symbol=self.args.symbol,
            side=SIDE_SELL,
            positionSide=POSITION_LONG,
            type=FUTURE_ORDER_TYPE_MARKET,
            # reduceOnly=True,
            quantity=amount
          )
      return res
    except Exception as e:
      error = f"Failed Close Long Market Order({self.args.symbol}, {amount})"
      logger.error(error)
      ERROR.error(error)
      ERROR.error(e)
      print(e)
      return None

  def close_long_take_profit_market(self, stopPrice):
    try:
      res = self.client.futures_create_order(
            symbol=self.args.symbol,
            side=SIDE_SELL,
            positionSide=POSITION_LONG,
            type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
            # workingType="MARK_PRICE",
            timeInForce=TIME_IN_FORCE_GTC, # Good til cancel
            # quantity=amount, # No need if closePosition=True
            stopPrice=stopPrice,
            # reduceOnly=True,
            closePosition=True
          )
      return res
    except Exception as e:
      error = f"Failed Close Long TP Order({self.args.symbol}, {stopPrice})"
      logger.error(error)
      ERROR.error(error)
      ERROR.error(e)
      print(e)
      return None

  def open_short_stop_market(self, amount, stopPrice):
    try:
      res = self.client.futures_create_order(
            symbol=self.args.symbol,
            side=SIDE_SELL,
            positionSide=POSITION_SHORT,
            type=FUTURE_ORDER_TYPE_STOP_MARKET,
            # workingType="MARK_PRICE",
            # timeInForce=TIME_IN_FORCE_GTC,
            quantity=amount,
            stopPrice=stopPrice
          )
      return res
    except Exception as e:
      error = f"Failed Open Short Order({self.args.symbol}, {stopPrice})"
      logger.error(error)
      ERROR.error(error)
      ERROR.error(e)
      print(e)
      return None

  def close_short_stop_market(self, stopPrice):
    try:
      res = self.client.futures_create_order(
            symbol=self.args.symbol,
            side=SIDE_BUY,
            positionSide=POSITION_SHORT,
            type=FUTURE_ORDER_TYPE_STOP_MARKET,
            # workingType="MARK_PRICE",
            timeInForce=TIME_IN_FORCE_GTC, # Good til cancel
            # quantity=amount, # No need if closePosition=True
            stopPrice=stopPrice,
            # reduceOnly=True,
            closePosition=True
          )
      return res
    except Exception as e:
      error = f"Failed Close SHORT SL Order({self.args.symbol}, {stopPrice})"
      logger.error(error)
      ERROR.error(error)
      ERROR.error(e)
      print(e)
      return None

  def close_short_take_profit_market(self, stopPrice):
    try:
      res = self.client.futures_create_order(
            symbol=self.args.symbol,
            side=SIDE_BUY,
            positionSide=POSITION_SHORT,
            type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
            # workingType="MARK_PRICE",
            timeInForce=TIME_IN_FORCE_GTC, # Good til cancel
            # quantity=amount, # No need if closePosition=True
            stopPrice=stopPrice,
            # reduceOnly=True,
            closePosition=True
          )
      return res
    except Exception as e:
      error = f"Failed Close SHORT TP Order({self.args.symbol}, {stopPrice})"
      logger.error(error)
      ERROR.error(error)
      ERROR.error(e)
      print(e)
      return None

  def cancel_order(self, orderId):
    try:
      return self.client.futures_cancel_order(symbol=self.args.symbol, orderId=orderId)
    except Exception as e:
      error = f"Failed Cancel Order({self.args.symbol}, {orderId})"
      logger.error(error)
      ERROR.error(error)
      ERROR.error(e)
      print(e)
      return None
  def check_is_sl_tp_order(self, positionSide=POSITION_LONG, checkPoint=POSITION_CHECK_SL):
    res = self.client.futures_get_open_orders(symbol=self.args.symbol)
    if checkPoint == POSITION_CHECK_SL: type = FUTURE_ORDER_TYPE_STOP_MARKET
    if checkPoint == POSITION_CHECK_TP: type = FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET
    if positionSide == POSITION_LONG: side = SIDE_SELL
    if positionSide == POSITION_SHORT: side = SIDE_BUY

    orders = [x for x in res if x["type"] == type and
                                x["positionSide"] == positionSide and
                                x["side"] == side and
                                x["closePosition"] == True and
                                x["reduceOnly"] == True
                                ]
    _orders = []
    IS_SL_TP = False
    for o in orders:
      if o["status"] == ORDER_STATUS_REJECTED or o["status"] == ORDER_STATUS_EXPIRED: # if there is open close order, but it is expired or rejected, cancel it
        self.cancel_order(o["orderId"])
      if o["status"] == ORDER_STATUS_NEW:
        _orders.append(o)
    if len(_orders) > 0:
      IS_SL_TP = True
      return IS_SL_TP, _orders[0]["orderId"]
    else: return False, None