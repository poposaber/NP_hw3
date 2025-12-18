import client
import os

c = client.Client()
try:
    c.start(host="linux1.cs.nycu.edu.tw")
except Exception as e:
    print(f"Error occurred: {e}")
os.system("pause")