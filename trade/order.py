from binance import Client
from binance.enums import *
from parameters import *
from utils.log import logbook

logger = logbook()

class Trade():
  def __init__(self, args):
    self.args = args
    self.client = self.create_client()
  def create_client(self):
    if self.args.testnet: return Client(TEST_API_KEY, TEST_API_SECRET, testnet=True)
    return Client(API_KEY, API_SECRET)
  def open_long_stop_market(self, amount, stopPrice):
    try:
      res = self.client.futures_create_order(
            symbol=self.args.symbol,
            side="BUY",
            positionSide="LONG",
            type=FUTURE_ORDER_TYPE_STOP_MARKET,
            # workingType="MARK_PRICE",
            # timeInForce=TIME_IN_FORCE_GTC,
            quantity=amount,
            stopPrice=stopPrice
          )
      return res
    except Exception as e:
      logger.error("Open Long Order Failed:")
      print(e)
      return None

  def close_long_stop_market(self, stopPrice):
    try:
      res = self.client.futures_create_order(
            symbol=self.args.symbol,
            side="SELL",
            positionSide="LONG",
            type=FUTURE_ORDER_TYPE_STOP_MARKET,
            # workingType="MARK_PRICE",
            # timeInForce=TIME_IN_FORCE_GTC,
            # quantity=amount, # No need if closePosition=True
            stopPrice=stopPrice,
            # reduceOnly=True,
            closePosition=True
          )
      return res
    except Exception as e:
      logger.error("Close Long SL Order Failed:")
      print(e)
      return None

  def close_long_take_profit_market(self, stopPrice):
    try:
      res = self.client.futures_create_order(
            symbol=self.args.symbol,
            side="SELL",
            positionSide="LONG",
            type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
            # workingType="MARK_PRICE",
            # timeInForce=TIME_IN_FORCE_GTC,
            # quantity=amount, # No need if closePosition=True
            stopPrice=stopPrice,
            # reduceOnly=True,
            closePosition=True
          )
      return res
    except Exception as e:
      logger.error("Close Long TP Order Failed:")
      print(e)
      return None

  def open_short_stop_market(self, amount, stopPrice):
    try:
      res = self.client.futures_create_order(
            symbol=self.args.symbol,
            side="SELL",
            positionSide="SHORT",
            type=FUTURE_ORDER_TYPE_STOP_MARKET,
            # workingType="MARK_PRICE",
            # timeInForce=TIME_IN_FORCE_GTC,
            quantity=amount,
            stopPrice=stopPrice
          )
      return res
    except Exception as e:
      logger.error("Open Short Order Failed:")
      print(e)
      return None

  def close_short_stop_market(self, stopPrice):
    try:
      res = self.client.futures_create_order(
            symbol=self.args.symbol,
            side="BUY",
            positionSide="SHORT",
            type=FUTURE_ORDER_TYPE_STOP_MARKET,
            # workingType="MARK_PRICE",
            # timeInForce=TIME_IN_FORCE_GTC,
            # quantity=amount, # No need if closePosition=True
            stopPrice=stopPrice,
            # reduceOnly=True,
            closePosition=True
          )
      return res
    except Exception as e:
      logger.error("Close SHORT SL Order Failed:")
      print(e)
      return None

  def close_short_take_profit_market(self, stopPrice):
    try:
      res = self.client.futures_create_order(
            symbol=self.args.symbol,
            side="BUY",
            positionSide="SHORT",
            type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
            # workingType="MARK_PRICE",
            # timeInForce=TIME_IN_FORCE_GTC,
            # quantity=amount, # No need if closePosition=True
            stopPrice=stopPrice,
            # reduceOnly=True,
            closePosition=True
          )
      return res
    except Exception as e:
      logger.error("Close SHORT TP Order Failed:")
      print(e)
      return None

  def cancel_order(self, orderId):
    try:
      return self.client.futures_cancel_order(symbol=self.args.symbol, orderId=orderId)
    except Exception as e:
      logger.error("Cancel Order Failed:")
      print(e)
      return None
  # It is just for mock order
  def get_order(self, order_price, price, side="buy"):
    if side == "buy":
      if price >= order_price: return { "status": "FILLED", "avgPrice": order_price, "orderId": 123 }
      return { "status": "NEW", "orderId": 123 }
    if side == "sell":
      if price <= order_price: return { "status": "FILLED", "avgPrice": order_price, "orderId": 123 }
      return { "status": "NEW", "orderId": 123 }