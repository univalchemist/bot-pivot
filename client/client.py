from binance import Client
from binance.enums import *
from parameters import *
from utils.log import Logger

logger = Logger()
class BinanceClient():
  def __init__(self, args):
    self.args = args
    self.client = self.create_client()
    
  def create_client(self):
    if self.args.testnet: return Client(TEST_API_KEY, TEST_API_SECRET, testnet=True)
    return Client(API_KEY, API_SECRET)