##
# Worker's routine
#

import download_s3, location_aws, AQI_aws, s3_check, time, json, re, warnings, boto3, requests, pandas as pd, numpy as np
from datetime import datetime, timedelta

##
# Definition of the name and the boto3 client to access the S3 bucket where the sensors' data
# files are stored, as well as the URL and boto3 client for the geocoder and main queue.
#

S3_BUCKET = "trm-cu-cc-aqi-bucket"
AWS_REGION = "us-east-1"
s3 = boto3.client("s3")
sqs = boto3.client("sqs", region_name=AWS_REGION)

# IMPORTANT, PLEASE, CHANGE THE URLS FOR THE NEW VALUES. NORMALLY IT WILL ONLY AFFECT TO THE ACCOUNT ID (THE NUMBERS)
MAIN_QUEUE = "https://sqs.us-east-1.amazonaws.com/624045726277/aqi-main-queue"
GEO_QUEUE = "https://sqs.us-east-1.amazonaws.com/624045726277/aqi-geocoder-queue"


##
# Computes the AQI for the given address, whose latitude, longitude and country are also given as 
# arguments, depending on the provided type and radius. It computes it only for a date, given as 
# an argument, for one specific type.
#
# Returns the AQI value and a message.
#

def get_aqi(type, address, radius, date, lat, lon, country):
    # If the type is custom_day, process the given date
    if (type == "custom_day"):
        try:
            # Parse the date as year-month-day and give it a date format
            date = datetime.strptime(date, "%Y-%m-%d").date()
            if not 2016 <= date.year <= datetime.today().date().year:
                # If the year is lower than 2016 or greater than the current one, raise 
                # exception as there is no data for it
                raise Exception
        except Exception:
            # Return no AQI if the date is not valid (outside the range or an incorrect string)
            return [None, "Invalid date, please try again."]
        
    # Create the lists where the AQIs and the and the ids of the sensors used to compute said AQIs
    # will be stored
    aqi_list = []
    found_ids = []

    try:
        # Change the data type of the radius to float
        radius = float(radius)

        if radius < 0:
            # Radius can't be negative, changing it to default (20 km).
            raise ValueError
        elif radius > 20:
            # Radius too big, changing it to default (20 km).
            raise ValueError
        
        # Get the ids of the nearest sensors to the given address and a status code.
        # If the status is 0, no sensors were found inside the circular area defined by the 
        # provided radius.
        # If the status is 1, at least one sensor was found inside the circular area defined 
        # by the provided radius.
        ids, status = location_aws.get_nearest(lat, lon, country, radius)

    except ValueError:
        # If the radius has an invalid type (it was not a number) or is outside the limits 
        # (lower than 0 or greater than 20), get the ids of the nearest sensors to the given 
        # address and a status code using the default radius (20 km).
        ids, status = location_aws.get_nearest(lat, lon, country)
    
    # AQI computation for the last hour
    if (type == "last_hour"):
        # Append to the aqi list the value returned by compute_AQI_json (the AQI value for the 
        # last hour in the given address, using the id list retrieved earlier)
        aqi_list.append(AQI_aws.compute_AQI_json(ids))

    # AQI computation for the last week
    elif (type == "last_week"):
        # Compute the week start date for the previous week
        week_start = datetime.today().date() - timedelta(days=datetime.today().weekday(), weeks=1)

        # Add six days to the week start date to get the week end date
        week_end = week_start + timedelta(days=6)

        # Use pandas to create a date range for the week
        week = pd.date_range(week_start, week_end)

        # Change the data type of each date to date
        week = [x.date() for x in week]

        # For each weekday, upload the relevant files to the S3 bucket and compute the AQI for each sensor
        for date in week:
            # Upload to the S3 bucket the files containing the data from the sensors in the id list 
            # retrieved earlier. Saves the ids of the sensors whose data has been obtained in the 
            # found ids list.
            found_ids = download_s3.download_directory(country, date, ids)

            # For each sensor whose data has been obtained, compute its AQI
            for id in found_ids:
                # Create the S3 bucket key for the sensor data
                key = (
                    f"sensor_data/"
                    f"{country}/"
                    f"{date.year}/"
                    f"{date}/"
                    f"{id}.csv"
                )

                # Compute the AQI for the sensor and append it to the AQI list
                aqi_list.append(AQI_aws.compute_AQI_csv(key))

    # AQI computation for the last week
    elif (type == "last_month"):
        # Calculate the start date for this month
        today = datetime.today().date()
        start_cm = today.replace(day=1)

        # Calculate the start date for the previous month
        end_lm = start_cm - timedelta(days=1)
        start_lm = end_lm.replace(day=1)

        # Use pandas to create a date range for the month
        month = pd.date_range(start_lm, end_lm)

        # Change the data type of each date to date
        month = [x.date() for x in month]

        # For each day in the month, upload the relevant files to the S3 bucket and compute the AQI 
        # for each sensor
        for date in month:
            # Upload to the S3 bucket the files containing the data from the sensors in the id list 
            # retrieved earlier. Saves the ids of the sensors whose data has been obtained in the 
            # found ids list.
            found_ids = download_s3.download_directory(country, date, ids)

            # For each sensor whose data has been obtained, compute its AQI
            for id in found_ids:
                # Create the S3 bucket key for the sensor data
                key = (
                    f"sensor_data/"
                    f"{country}/"
                    f"{date.year}/"
                    f"{date}/"
                    f"{id}.csv"
                )

                # Compute the AQI for the sensor and append it to the AQI list
                aqi_list.append(AQI_aws.compute_AQI_csv(key))

    # AQI computation for a custom day
    elif (type == "custom_day"):
        # Upload to the S3 bucket the files containing the data from the sensors in the id list 
        # retrieved earlier for the given date. Saves the ids of the sensors whose data has been 
        # obtained in the found ids list.
        found_ids = download_s3.download_directory(country, date, ids)

        # For each sensor whose data has been obtained, compute its AQI
        for id in found_ids:
            # Create the S3 bucket key for the sensor data
            key = (
                f"sensor_data/"
                f"{country}/"
                f"{date.year}/"
                f"{date}/"
                f"{id}.csv"
            )

            # Compute the AQI for the sensor and append it to the AQI list
            aqi_list.append(AQI_aws.compute_AQI_csv(key))

    # Catch the possible warnings raised
    with warnings.catch_warnings(record=True) as w:
        # Compute the total AQI as the mean of all the computed AQIs, ignoring the nan values
        aqi = np.nanmean(aqi_list)

        if np.isnan(aqi):
            # If the AQI is nan, that means that the sensor data is unknown
            # Return no AQI
            return [None, "No valid sensor data available."]
        
        # If there are no warnings, return the AQI value and the message depending on the status 
        # described before
        if len(w) == 0:
            if (status == 1):
                return [aqi, f"The AQI for {address} is {aqi}"]
            else:
                return [aqi, f"There are no sensors near {address}, but the nearest one reports an AQI of {aqi}"]
    
        # If there are warnings, no sensors near the given address were found
        # Return no AQI
        else:
            return [None, f"No sensors near {address} were found for that option, please try with other date or location."]


##
# Returns the id of the EC2 instance running the programme.
#

def get_instance_id():
    # Get IMDSv2 token
    token_resp = requests.put(
        "http://169.254.169.254/latest/api/token",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
        timeout=2
    )
    token_resp.raise_for_status()
    token = token_resp.text

    # Use token to get instance id
    id_resp = requests.get(
        "http://169.254.169.254/latest/meta-data/instance-id",
        headers={"X-aws-ec2-metadata-token": token},
        timeout=2
    )
    id_resp.raise_for_status()

    # Returns the EC2 instance id
    return id_resp.text


##
# Parses the API Gateway SQS message to be processed by the instance as a json.
#
# Returns the parsed message.
#

def parse_apigw_sqs_message(msg_body: str) -> dict:
    # Remove outer braces
    body = msg_body.strip()
    if body.startswith("{") and body.endswith("}"):
        body = body[1:-1]

    # Split top-level fields (job_id, payload)
    parts = {}
    for part in re.split(r",\s(?=[a-zA-Z_]+=)", body):
        key, value = part.split("=", 1)
        parts[key.strip()] = value.strip()

    # job_id is plain text
    job_id = parts["job_id"]

    # payload is json but escaped
    payload_raw = parts["payload"]

    # Unescape quotes
    payload_raw = payload_raw.replace('\\"', '"')

    # Load the json
    payload = json.loads(payload_raw)

    # Return the parsed message as a json
    return {
        "job_id": job_id,
        "payload": payload
    }


##
# Worker's routine
#

while True:
    # Get the messages from the main queue
    resp = sqs.receive_message(
        QueueUrl=MAIN_QUEUE,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=20
    )

    # If there are no messages, try to get them again until one is obtained
    if "Messages" not in resp:
        continue

    # Get the first message from the queue and parse it as a json
    msg = resp["Messages"][0]
    req = parse_apigw_sqs_message(msg["Body"])

    # Get the data from the message
    job_id = req["job_id"]
    payload = req["payload"]
    type = payload["type"]
    address = payload["address"]
    radius = payload["radius"]
    date = payload["date"]

    # Start time for the timer for the admin metadata
    t0 = time.time()

    # Parse the address given as an argument so that it is safe to operate with
    safe_address = re.sub(r"[,;:._\?¿¡!\|\\/()\[\]\-\s+]", " ", address.strip().lower())
    safe_address = re.sub(r"\s+", "_", safe_address)

    # Create the S3 bucket key for the address
    s3_address_key = (
        f"addresses/"
        f"{safe_address.lower()}.json"
    )

    # If the address has not been processed before, get the geocoder to do it
    if (not s3_check.s3_object_exists(s3_address_key)):
        # Send a message to the geocoder queue so that the geocoder gets the latitude and 
        # longitude of the given address
        sqs.send_message(
            QueueUrl=GEO_QUEUE,
            MessageBody=json.dumps({"address": address})
        )

    # If the geocoder fails to retrieve the data for the provided address or the wait for it 
    # is too long (more than 3 minutes), set no value to the AQI.
    if not location_aws.geocoder_wait(s3_address_key):
        aqi = None
        message = "Geocoding timed out. Please try again later."
    else:
        # Get the latitude, longitude and country for the given address from the S3 bucket
        lat, lon, country = location_aws.get_loc(s3_address_key)

        # Get the AQI value and the message according to the data from the SQS message
        aqi, message = get_aqi(type, address, radius, date, lat, lon, country)
    
    # Ending time for the timer for the admin metadata
    t1 = time.time()

    # Create the json for the data to present to the user in the website
    user_data = {
        "status":"DONE", 
        "aqi":aqi, 
        "message":message
    }

    # Create the S3 bucket key for the user data
    s3_result_key = (
        f"results/"
        f"{job_id}.json"
    )

    # Upload the user data to the S3 bucket
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_result_key,
        Body=json.dumps(user_data, indent=2)
    )

    # Retrieve the EC2 instance id
    instance_id = get_instance_id()

    # Create the json for the admin metadata
    admin_data = {
        "aqi":aqi, 
        "message":message,
        "type":type,
        "address":address,
        "radius":radius,
        "date":date,
        "proc_time":t1-t0,
        "instance_id":instance_id
    }

    # Create the S3 bucket key for the admin metadata
    s3_admin_key = (
        f"admin/"
        f"{job_id}.json"
    )

    # Upload the admin metadata to the S3 bucket
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_admin_key,
        Body=json.dumps(admin_data, indent=2)
    )

    # Delete the processed SQS message
    sqs.delete_message(
        QueueUrl=MAIN_QUEUE,
        ReceiptHandle=msg["ReceiptHandle"]
    )
