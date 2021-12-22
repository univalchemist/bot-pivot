from utils.log import Logger

logger = Logger()

class Position():
  def __init__(self, amount=0):
    self.positions = []
    self.fee = -0.06 # per trade
    self.amount = amount
  def add_position(self, position):
    self.positions.append(position)
  def get_positions(self):
    return self.positions
  def calculate_pnl(self):
    totalTradeCount = len(self.positions)
    successCount = 0
    failureCount = 0
    pnl = 0
    for t in self.positions:
      if t["Side"] == "Long":
        profit = (t["Exit"] - t["Entry"]) * t["Amount"]
      if t["Side"] == "Short":
        profit = (t["Entry"] - t["Exit"]) * t["Amount"]
      if profit > 0:
        successCount = successCount + 1
      else: failureCount = failureCount + 1
      pnl = pnl + round(profit, 2)
    totalFee = self.fee * self.amount / 100 * totalTradeCount
    return totalTradeCount, pnl, totalFee, successCount, failureCount
  def initialize_positions(self):
    self.positions = []