import requests
from dotenv import load_dotenv
import os
from alith.lazai import Client

load_dotenv()  # load from .env file

private_key = os.getenv("PRIVATE_KEY")
if not private_key:
    raise ValueError("PRIVATE_KEY not found in .env")

client = Client(private_key=private_key)
node = "0x3717706c2dF083Edd7264a953bBAF24017d49E00" #change this address with one you registered with admin 

try:
    print("try to get user")
    user =  client.get_user(client.wallet.address)
    print(user)
except Exception as e:
    print("try to get user failed")
    print(e)
    print("try to add user failed")
    client.add_user(1000000)
    print("user added")


print("try to get query account")

url = "http://127.0.0.1:8000" 
print(url)
headers = client.get_request_headers(node)
print("request headers:", headers)
print(
    "request result:",
    requests.post(
        f"{url}/query/rag",
        headers=headers,
        json={
            "file_id": 11, #change with your file_id 
            "query": "summarise the best character?",
        },
    ).json(),
)