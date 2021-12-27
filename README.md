# Swing High/Low Trading - Pivot Bot

- Pivot-Bot is based on swing high, low in trend
- Swing High/Low is determinded by Left/Right Candles
- When occur swing high, sell and trailing stop loss
- When occur swign low, buy and trailing stop loss

## Run the bot
```sh
python main.py -s BTCUSDT -a 5000 -ps 10 -i 3
```
For arguments, check the main.py
- s - symbol: pair to trade
- amount - USDT amount per trade
- ps - left/right candle lenght to calculate pivot point
- dt - deltatrigger to trigger order
- sl - stop loss to trail
- tp - take profit
- i - candle timeline
- testnet - run in testnet
- backtest - for condition if it is backtest or real mode.

## Backtest
```sh
python backtest.py -s BTCUSDT -i 3 -backtest -st 1640574573000 -du 30
```

## Backtest without csv
```sh
python backtest.py -s BTCUSDT -i 3 -backtest -st 1640574573000 -du 30
```
