from binance import Client
from binance.enums import *
from parameters import *
from utils.log import Logger

logger = Logger()

def create_client(args):
  if args.testnet: return Client(TEST_API_KEY, TEST_API_SECRET, testnet=True)
  return Client(API_KEY, API_SECRET)