import pandas as pd
import mplfinance as mpf
from collections import deque
import numpy as np

# df = pd.read_csv('dataset/ADAUSDT-1m-2021-12-13-PERP.csv',usecols=[0,1,2,3,4])
# df.columns = ["Timestamp", "Open", "High", "Low", "Close"]
# df["Date"] = pd.to_datetime(df["Timestamp"], unit="ms")
# df.index = pd.DatetimeIndex(df['Date'])
# values = df.values
class PlotPivot():
    def __init__(self, data_array, length):
        self.length = length
        self.data_array = np.array(data_array)
    def draw_plot(self):
        i = self.length
        columns = ["OpenTime", "Open", "High", "Low", "Close", "Volume", "CloseTime", "Qav", "Not", "Bv", "Qv", "I"]
        dataframe = pd.DataFrame(data=self.data_array[0:, 0:],    # values
                                # index=self.data_array[1:,0],    # 1st column as index
                                columns=columns)  # 1st row as the column names
        dataframe = dataframe[["OpenTime", "Open", "High", "Low", "Close"]]
        dataframe["Date"] = pd.to_datetime(dataframe["OpenTime"], unit="ms")
        dataframe.index = pd.DatetimeIndex(dataframe['Date'])
        dataframe['Open'] = dataframe['Open'].astype('float64')
        dataframe['High'] = dataframe['High'].astype('float64')
        dataframe['Low'] = dataframe['Low'].astype('float64')
        dataframe['Close'] = dataframe['Close'].astype('float64')
        close_mav50 = dataframe["Close"].rolling(50).mean().values
        close_mav100 = dataframe["Close"].rolling(100).mean().values
        low_mav50 = dataframe["Low"].rolling(50).mean().values
        low_mav100 = dataframe["Low"].rolling(100).mean().values
        mavdf = pd.DataFrame(dict(OpMav100=close_mav100),index=dataframe.index)
        dataframe.dropna()
        values = dataframe.values

        next_pivot = "None"
        high_pivot = [np.nan]*len(values)
        low_pivot = [np.nan]*len(values)
        next_pivot = "None"
        trend = "None"
        delta = 0.001
        LastHigh = 0
        LastLow = 0
        LastHighIndex = 0
        LastLowIndex = 0

        for row in values[i + 1:-i]:
            i = i + 1
            Open = float(row[1])
            Close = float(row[4])
            High = float(row[2]) # Get high value of 5th candle to compare left/right 5 candles
            Low = float(row[3]) # Get low value of 5th candle to compare left/right 5 candles
            _klins_left = values[(i - self.length):i]
            _klins_righ = values[(i + 1):(i + self.length)]
            HighsLeft = [float(x[2]) for x in _klins_left]
            LowsLeft = [float(x[3]) for x in _klins_left]
            HighsRight = [float(x[2]) for x in _klins_righ]
            LowsRight = [float(x[3]) for x in _klins_righ]
            HighCheck = True if all(x <= High for x in HighsLeft) and all(x < High for x in HighsRight) else False
            LowCheck = True if all(x >= Low for x in LowsLeft) and all(x > Low for x in LowsRight) else False
            # Check the candle is green or red
            IsUpCandle = True if Close > Open else False
            # It is just for the process to find the first high/low point
            if next_pivot == "None":
                if HighCheck == True:
                    high_pivot[i] = High
                    next_pivot = "Low"
                    LastHigh = High
                    LastHighIndex = i
                elif LowCheck == True:
                    low_pivot[i] = Low
                    next_pivot = "High"
                    LastLow = Low
                    LastLowIndex = i

            else:
                if HighCheck == True:
                    # Check the current high pivot is greater than the previous one. If true, replace the previous one to current
                    if next_pivot == "Low" and High >= LastHigh:
                        if LastHigh > 0:
                            high_pivot[LastHighIndex] = np.nan
                            high_pivot[i] = High
                            LastHigh = High
                            LastHighIndex = i
                    if next_pivot == "High":
                        high_pivot[i] = High
                        next_pivot = "Low"
                        LastHigh = High
                        LastHighIndex = i
                elif LowCheck == True:
                    # Check the current low pivot is less than the previous one. If true, replace the previous one to current
                    if next_pivot == "High" and LastLow >= Low:
                        if LastLow > 0:
                            low_pivot[LastLowIndex] = np.nan
                            low_pivot[i] = Low
                            LastLow = Low
                            LastLowIndex = i
                    if next_pivot == "Low":
                        low_pivot[i] = Low
                        next_pivot = "High"
                        LastLow = Low
                        LastLowIndex = i

        apd_low = mpf.make_addplot(low_pivot, type='scatter', markersize=200, marker='^')
        apd_high = mpf.make_addplot(high_pivot, type='scatter', markersize=200, marker='v')
        ap = mpf.make_addplot(mavdf,type='line')
        apds = [apd_low, apd_high, ap]
        # mpf.plot(dataframe, addplot=apds, type='candle', mav=(50, 100))
        mpf.plot(dataframe, addplot=apds, type='candle')
        # mpf.plot(dataframe, type='candle')