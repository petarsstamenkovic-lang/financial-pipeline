import requests
from bs4 import BeautifulSoup

url = "https://webappcenter.nbs.rs/ExchangeRateWebApp/ExchangeRate/CurrentMiddleRate"
r = requests.get(url, timeout=10)
soup = BeautifulSoup(r.text, "html.parser")

# Find rows containing EUR, USD, GBP, CHF
for row in soup.find_all("tr"):
    cells = [td.get_text(strip=True) for td in row.find_all("td")]
    if cells and cells[0] in ("EUR", "USD", "GBP", "CHF"):
        print(cells)