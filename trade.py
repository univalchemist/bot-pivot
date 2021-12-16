from binance import Client
from binance.enums import *
from parameters import *

client = Client(API_KEY, API_SECRET, testnet=True)

def open_long_stop_market(symbol, amount, stopPrice):
  try:
    res = client.futures_create_order(
          symbol=symbol,
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
    print("Open Long Order Failed:")
    print(e)
    return None

def close_long_stop_market(symbol, stopPrice):
  try:
    res = client.futures_create_order(
          symbol=symbol,
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
    print("Close Long Order Failed:")
    print(e)
    return None

def open_short_stop_market(symbol, amount, stopPrice):
  try:
    res = client.futures_create_order(
          symbol=symbol,
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
    print("Open Short Order Failed:")
    print(e)
    return None

def close_short_stop_market(symbol, stopPrice):
  try:
    res = client.futures_create_order(
          symbol=symbol,
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
    print("Close SHORT Order Failed:")
    print(e)
    return None

def cancel_order(symbol, orderId):
  try:
    return client.futures_cancel_order(symbol=symbol, orderId=orderId)
  except Exception as e:
    print("Cancel Order Failed:")
    print(e)
    return None