##
# Geocoder's routine
#

import geopy.geocoders, time, re
import json, boto3
from botocore.exceptions import ClientError

##
# Definition of the name and the boto3 client to access the S3 bucket where the sensors' data
# files are stored, as well as the URL and boto3 client for the geocoder queue.
#

S3_BUCKET = "trm-cu-cc-aqi-bucket"
AWS_REGION = "us-east-1"
s3 = boto3.client("s3")
sqs = boto3.client("sqs", region_name=AWS_REGION)

# IMPORTANT, PLEASE, CHANGE THE URL FOR THE NEW VALUE. NORMALLY IT WILL ONLY AFFECT TO THE ACCOUNT ID (THE NUMBERS)
GEO_QUEUE = "https://sqs.us-east-1.amazonaws.com/624045726277/aqi-geocoder-queue"

##
# Initialisation of the Nominatim geocoder used to translated an address to latitude and longitude.
#

geolocator = geopy.geocoders.Nominatim(user_agent="my_geopy_app", timeout=60)


##
# Checks if the S3 bucket key given as an argument already exists.
#
# Returns True or False.
#

def s3_object_exists(key):
    try:
        # If file/key already exists, return True
        s3.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except ClientError as e:
        # If file/key does not exist, return False
        if e.response["Error"]["Code"] == "404":
            return False
        raise


##
# Transforms an address provided as an argument to a latitude and longitude using Nominatim's geocoder.
#
# Returns and stores into the S3 bucket the latitude, longitude and country code.
#

def get_loc(address):
    # Parse the address given as an argument so that it is safe to operate with
    safe_address = re.sub(r"[,;:._\?¿¡!\|\\/()\[\]\-\s+]", " ", address.strip().lower())
    safe_address = re.sub(r"\s+", "_", safe_address)

    # Create the S3 bucket key for the address
    s3_key = (
        f"addresses/"
        f"{safe_address.lower()}.json"
    )

    if (not s3_object_exists(s3_key)):  # To check if a previous request from the queue has already found the location while this request was queued
        try:
            # Transform the address to latitude and longitude with the geocoder
            location = geolocator.geocode(address, addressdetails=True)
            data = {
                "latitude":location.latitude, 
                "longitude":location.longitude, 
                "country":location.raw['address']['country_code']
            }

            # Upload the data to the S3 bucket
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=json.dumps(data, indent=2)
            )
    
        except Exception as e:
            # Printing for logs if address is not valid. With this, the geocoder will not
            # stop even if an address could not be processed correctly.
            print("Invalid address, please try again.")

##
# Geocoder's routine
#

while True:
    # Retrieve the messages from the geocoder queue
    resp = sqs.receive_message(
        QueueUrl=GEO_QUEUE,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=20
    )

    # If there are no messages, continue the execution of the code
    if "Messages" not in resp:
        continue

    # Get the address from the SQS message
    msg = resp["Messages"][0]
    body = json.loads(msg["Body"])
    address = body["address"]

    # Get the latitude and longitude
    get_loc(address)

    # Delete the processed SQS message
    sqs.delete_message(
        QueueUrl=GEO_QUEUE,
        ReceiptHandle=msg["ReceiptHandle"]
    )

    # Sleep for 1 second as Nominatim's Usage Policy states that only one request per second is allowed
    time.sleep(1)