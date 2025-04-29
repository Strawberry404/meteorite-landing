import numpy as np
import pandas as pd
import requests

# Define the API endpoind:
url = "https://data.nasa.gov/resource/y77d-th95.json"

# Call API and get json response:
response = requests.get(url)
if response.status_code == 200:
	data = response.json()
# Store response in DataFrame
df = pd.DataFrame(data)

print(df.head())
