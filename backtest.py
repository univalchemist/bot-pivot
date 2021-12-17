from binance import ThreadedWebsocketManager as t_ws
from binance.exceptions import BinanceAPIException
from binance.enums import *
import argparse, sys
from utils.arguments import Argument
from utils.draw_pivot import PlotPivot

from utils.log import logbook
from parameters import *
from strategy.pivot import PivotStrategy
from trade.order import *

logger = logbook()

parser = argparse.ArgumentParser(description='Set your Symbol, TradeAmount, PivotStep, DeltaPivot, DeltaSL, DeltaTrigger, StopLoss, Testnet. Example: "main.py -s BTCUSDT"')
parser.add_argument('-s', '--symbol', required=True, help='str, Pair for trading e.g. "-s BTCUSDT"')
parser.add_argument('-a', '--amount', default=50.0, type=float, help='float, Amount in USDT to trade e.g. "-a 50"')
parser.add_argument('-ps', '--pivotstep', default=5, type=int, help='int, Left/Right candle count to calculate Pivot e.g. "-ps 5"')
parser.add_argument('-d', '--delta', default=0, type=float, help='float, delta to determine trend e.g. "-d 10.0"')
parser.add_argument('-dsl', '--deltasl', default=0.05, type=float, help='float, delta SL to calculate with HH, LL. its value is percentage e.g. "-dsl 0.0005"')
parser.add_argument('-dt', '--deltatrigger', default=0.15, type=float, help='float, delta percent to calculate trigger open order. its value is percentage e.g. "-dt 0.15"')
parser.add_argument('-sl', '--stoploss', default=0.45, nargs="?", const=True, type=float, help='float, Percentage Stop loss from your input USDT amount "-sl 0.45" ')
parser.add_argument('-test', '--testnet',  action="store_true", help='Run script in testnet or live mode.')
args = parser.parse_args()
def main():
  # create socket manager
  startTime = 1639526400000
  client = Client(API_KEY, API_SECRET)
  res = client.futures_klines(symbol=args.symbol, interval=KLINE_INTERVAL_1MINUTE, startTime=startTime, limit=1500)
  PlotPivot(res, 5).draw_plot()
def parseArgs():
  if args.symbol == None:
    logger.error("Please Check Symbol argument e.g. -s BTCUSDT")
    logger.error("exit!")
    sys.exit()
  else:
    Argument().set_args(args)
    main()
if __name__ == "__main__":
  parseArgs()