import os
import requests
import json

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
print(f"OPENAI_API_KEY: {OPENAI_API_KEY}")

URL = "https://www.multibagg.ai/api/v1/chatbot/chat-data"

HEADERS = {
    "accept": "*/*",
    "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
    "content-type": "application/json",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "referer": "https://www.multibagg.ai/ask-iris/ebd14df8-d387-4dc6-9a89-1a7337de8ccb",
}

HOLDINGS = [
    {"name": "Suzlon Energy Ltd", "quantity": 5, "avgCost": 6.65, "price": 40.8},
    {"name": "Brightcom Group Ltd", "quantity": 8, "avgCost": 110.6, "price": 8.57},
    {"name": "Coal India Ltd", "quantity": 11, "avgCost": 223.03, "price": 445.15},
    {
        "name": "Indian Railway Catering and Tourism Corporation Ltd",
        "quantity": 20,
        "avgCost": 700.85,
        "price": 510.6,
    },
    {"name": "Laurus Labs Ltd", "quantity": 11, "avgCost": 361.22, "price": 1009.3},
    {
        "name": "Data Patterns (India) Ltd",
        "quantity": 5,
        "avgCost": 585,
        "price": 3151.05,
    },
    {"name": "HDFC Bank Ltd", "quantity": 12, "avgCost": 729.13, "price": 756.25},
    {"name": "Vodafone Idea Ltd", "quantity": 20, "avgCost": 13.12, "price": 8.9},
    {
        "name": "Adani Enterprises Ltd",
        "quantity": 1,
        "avgCost": 3422.14,
        "price": 1822.85,
    },
    {
        "name": "Imagicaaworld Entertainment Ltd",
        "quantity": 50,
        "avgCost": 13.62,
        "price": 37.63,
    },
    {
        "name": "Surat Trade and Mercantile Ltd",
        "quantity": 10,
        "avgCost": 24.15,
        "price": 3.65,
    },
    {
        "name": "Tata Motors Passenger Vehicles Ltd",
        "quantity": 30,
        "avgCost": 293.65,
        "price": 303.2,
    },
    {
        "name": "Dr Reddy's Laboratories Ltd",
        "quantity": 15,
        "avgCost": 777.23,
        "price": 1286.2,
    },
    {"name": "Tata Motors Ltd", "quantity": 30, "avgCost": 132.86, "price": 427.6},
    {"name": "3i Infotech Ltd", "quantity": 4, "avgCost": 22.96, "price": 13.33},
    {"name": "Tejas Networks Ltd", "quantity": 2, "avgCost": 412, "price": 410.2},
    {"name": "Wipro Ltd", "quantity": 54, "avgCost": 270.22, "price": 191.45},
    {"name": "Infosys Ltd", "quantity": 9, "avgCost": 1699.65, "price": 1270},
    {
        "name": "Railtel Corporation of India Ltd",
        "quantity": 1,
        "avgCost": 115.44,
        "price": 260.25,
    },
    {
        "name": "Central Depository Services (India) Ltd",
        "quantity": 6,
        "avgCost": 662.7,
        "price": 1171.3,
    },
    {"name": "Relaxo Footwears Ltd", "quantity": 8, "avgCost": 1185.25, "price": 249},
    {"name": "Bharti Airtel Ltd", "quantity": 4, "avgCost": 715.65, "price": 1842.15},
    {"name": "Eicher Motors Ltd", "quantity": 4, "avgCost": 2679.55, "price": 6807.95},
    {"name": "Deepak Nitrite Ltd", "quantity": 6, "avgCost": 1907.57, "price": 1348},
    {
        "name": "Solar Industries India Ltd",
        "quantity": 1,
        "avgCost": 2313.11,
        "price": 12427.85,
    },
    {"name": "Trident Ltd", "quantity": 46, "avgCost": 51.86, "price": 23.79},
    {
        "name": "Pidilite Industries Ltd",
        "quantity": 4,
        "avgCost": 1091.35,
        "price": 1315,
    },
    {"name": "Titan Company Ltd", "quantity": 2, "avgCost": 2374.36, "price": 3975},
    {
        "name": "Avenue Supermarts Ltd",
        "quantity": 5,
        "avgCost": 4152.95,
        "price": 3908.9,
    },
    {"name": "Aarti Industries Ltd", "quantity": 1, "avgCost": 533.1, "price": 413.8},
    {
        "name": "L&T Technology Services Ltd",
        "quantity": 2,
        "avgCost": 3728.74,
        "price": 3198,
    },
    {"name": "LTIMindtree Ltd", "quantity": 1, "avgCost": 4202.42, "price": 4201.9},
    {"name": "Bajaj Finserv Ltd", "quantity": 10, "avgCost": 1132.35, "price": 1696.15},
    {"name": "GAIL (India) Ltd", "quantity": 26, "avgCost": 91.95, "price": 137.15},
    {"name": "Eternal Ltd", "quantity": 64, "avgCost": 83.16, "price": 233.1},
    {
        "name": "Tata Power Company Ltd",
        "quantity": 20,
        "avgCost": 233.36,
        "price": 385.7,
    },
    {
        "name": "HCL Technologies Ltd",
        "quantity": 3,
        "avgCost": 1218.01,
        "price": 1363.7,
    },
    {
        "name": "Tata Consultancy Services Ltd",
        "quantity": 2,
        "avgCost": 3644.67,
        "price": 2389.85,
    },
]

QUESTION = "give me max drawdown of all the shares in my portfolio?"

SESSION_ID = "ebd14df8-d387-4dc6-9a89-1a7337de8ccb"

MODE_INFO = {
    "mode": "portfolio",
    "mbCode": "",
    "lockedPdfUrl": "",
    "screenerData": None,
}

PAYLOAD = {
    "question": QUESTION,
    "sessionId": SESSION_ID,
    "sessionTitle": None,
    "mbCode": "$CHATBOT$",
    "type": "portfolio",
    "model": "gpt-5.2",
    "promptType": "General",
    "searchType": "PORTFOLIO",
    "brevity": "Balanced",
    "modeInfo": MODE_INFO,
}


def main():
    response = requests.post(
        URL,
        headers=HEADERS,
        json=PAYLOAD,
    )

    print(f"Status Code: {response.status_code}")

    try:
        data = response.json()
        print(json.dumps(data, indent=2))
    except requests.exceptions.JSONDecodeError:
        print(response.text)


if __name__ == "__main__":
    main()
