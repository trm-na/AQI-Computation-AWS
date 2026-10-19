##
# Stress testing for the complete AWS system.
#

import asyncio, aiohttp, random, time
from datetime import datetime

##
# Definition of the constants.
#

TOTAL_REQUESTS = 30             # total requests to send
CONCURRENCY = 3                 # how many at once
DELAY_BETWEEN_BATCHES = 30      # seconds

# IMPORTANT, PLEASE, CHANGE THE URL FOR THE NEW VALUE
API_BASE = "https://cze1i6meid.execute-api.us-east-1.amazonaws.com/prod"

##
# Address list whose AQI will be requested.
#

addresses = [
    "London",
    "Paris",
    "Berlin",
    "Madrid",
    "Rome",
    "Amsterdam",
    "Cranfield",
    "Dublin",
    "Tokyo",
    "Cairo"
]

##
# Type of requests available.
#

payloads = [
    {"type": "last_hour"},
    {"type": "last_week"},
    {"type": "last_month"}
]


##
# Sends a request to the API gateway as a user would in the website.
#

async def send_request(session, i):
    # Choose a random type of request
    payload = random.choice(payloads)

    # Complete the request with a random address from the list and a random value fro the radius
    payload.update({
        "address": random.choice(addresses),
        "radius": random.uniform(0, 20),
        "date": None
    })

    # Send the API request
    async with session.post(
        f"{API_BASE}/submit",
        json=payload
    ) as resp:
        data = await resp.json()
        print(f"[{i}] job_id={data.get('job_id')}")


##
# Sends several concurrent requests to the API.
#

async def main():
    # Create the connector to connect to the API
    connector = aiohttp.TCPConnector(limit=CONCURRENCY)

    async with aiohttp.ClientSession(connector=connector) as session:
        # Send CONCURRENCY concurrent requests to the API until TOTAL_REQUESTS requests are sent
        for i in range(0, TOTAL_REQUESTS, CONCURRENCY):
            tasks = [
                send_request(session, i + j)
                for j in range(CONCURRENCY)
                if i + j < TOTAL_REQUESTS
            ]
            
            # Wait until the tasks are sent
            await asyncio.gather(*tasks)

            # Wait the established delay time
            await asyncio.sleep(DELAY_BETWEEN_BATCHES)

if __name__ == "__main__":
    print(f"Current time: {datetime.now()}")
    start = time.time()
    asyncio.run(main())
    print("Done in", time.time() - start, "seconds")