import yfinance as yf
from datetime import datetime, timedelta

ticker = "GLDG"  # ou un autre ticker que tu utilises
start = datetime.today() - timedelta(days=365)
end = datetime.today()

df = yf.download(ticker, start=start, end=end, interval="1d")
print(df.tail())
