from binance import ThreadedWebsocketManager as t_ws
from binance.exceptions import BinanceAPIException
from binance.enums import *
import argparse, sys
from utils.arguments import Argument

from utils.log import Logger
from parameters import *
import strategy.pivot as sp
from client.order import *
from back.position import Position

logger = Logger()

parser = argparse.ArgumentParser(description='Set your Symbol, TradeAmount, PivotStep, DeltaPivot, DeltaSL, DeltaTrigger, StopLoss, Testnet. Example: "main.py -s BTCUSDT"')
parser.add_argument('-s', '--symbol', required=True, help='str, Pair for trading e.g. "-s BTCUSDT"')
parser.add_argument('-a', '--amount', default=5000.0, type=float, help='float, Amount in USDT to trade e.g. "-a 50"')
parser.add_argument('-ps', '--pivotstep', default=5, type=int, help='int, Left/Right candle count to calculate Pivot e.g. "-ps 5"')
parser.add_argument('-d', '--delta', default=0, type=float, help='float, delta to determine trend e.g. "-d 10.0"')
parser.add_argument('-dsl', '--deltasl', default=0.2, type=float, help='float, delta SL to calculate with HH, LL. its value is percentage e.g. "-dsl 0.0005"')
parser.add_argument('-dt', '--deltatrigger', default=0.05, type=float, help='float, delta percent to calculate trigger open order. its value is percentage e.g. "-dt 0.15"')
parser.add_argument('-sl', '--stoploss', default=0.6, nargs="?", const=True, type=float, help='float, Percentage Stop loss from your input USDT amount "-sl 0.45" ')
parser.add_argument('-tp', '--takeprofit', default=0.6, type=float, help='float, Percentage of Take Profit"-sl 0.8" ')
parser.add_argument('-i', '--interval', default=1, type=int, help='int, time interval as minute"-i 1" ')
parser.add_argument('-test', '--testnet',  action="store_true", help='Run script in testnet or live mode.')
parser.add_argument('-backtest', '--backtest',  action="store_true", help='Run script in backtest. No need in main.py')
args = parser.parse_args()

def main():
    # create socket manager
    try:
        logger.info_blue("Connecting Thread Websocket...")
        twm = t_ws(api_key=TEST_API_KEY, api_secret=TEST_API_SECRET, testnet=True) if args.testnet else t_ws(api_key=API_KEY, api_secret=API_SECRET)
        twm.start()
        position = Position(args.amount)
        twm.start_kline_futures_socket(callback=sp.PivotStrategy(args, position=position).handle_kline_msg, symbol=args.symbol)
    except BinanceAPIException as e:
        logger.error("Socket connection error!")
        print(e)
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