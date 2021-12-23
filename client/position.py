from binance import Client
from binance.enums import *
from parameters import *
from .client import BinanceClient
from utils.enums import *
from utils.log import Logger

logger = Logger()

class Position():
  def __init__(self, args):
    self.args = args
    self.client = BinanceClient(args).client
    pass
  def check_is_position(self):
    position_info = self.client.futures_position_information(symbol=self.args.symbol, recvWindow=recvWindow)

    position_long = [x for x in position_info if x["positionSide"] == POSITION_LONG and float(x["positionAmt"]) > 0 and float(x["entryPrice"]) > 0]
    position_short = [x for x in position_info if x["positionSide"] == POSITION_SHORT  and float(x["positionAmt"]) > 0 and float(x["entryPrice"]) > 0]

    IS_LONG = False
    IS_SHORT = False
    long_position_amt = 0
    short_position_amt = 0
    if len(position_long) > 0:
      IS_LONG = True
      long_position_amt = float(position_long[0]["positionAmt"])
    if len(position_short) > 0:
      IS_SHORT = True
      short_position_amt = float(position_short[0]["positionAmt"])
    return (IS_LONG, long_position_amt), (IS_SHORT, short_position_amt)
