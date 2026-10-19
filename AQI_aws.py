##
# Functions needed for the AQI computation
#


import json, boto3, io, numpy as np, pandas as pd

##
# UK Air Quality Index for PM10 particles according to “Review of the UK Air Quality Index”, 2011
# Each range corresponds to one value for the AQI, being the values of the range the PM10 particles
# 24 hour mean assigned to each AQI value.
#

PM10_AQI_RANGES = [
    (0, 16),    # AQI 1
    (17, 33),   # AQI 2
    (34, 50),   # AQI 3
    (51, 58),   # AQI 4
    (59, 66),   # AQI 5
    (67, 75),   # AQI 6
    (76, 83),   # AQI 7
    (84, 91),   # AQI 8
    (92, 100)   # AQI 9
]


##
# UK Air Quality Index for PM2.5 particles according to “Review of the UK Air Quality Index”, 2011
# Each range corresponds to one value for the AQI, being the values of the range the PM2.5 particles
# 24 hour mean assigned to each AQI value.
#

PM25_AQI_RANGES = [
    (0, 11),    # AQI 1
    (12, 23),   # AQI 2
    (24, 35),   # AQI 3
    (36, 41),   # AQI 4
    (42, 47),   # AQI 5
    (48, 53),   # AQI 6
    (54, 58),   # AQI 7
    (59, 64),   # AQI 8
    (65, 70)    # AQI 9
]


##
# Definition of the name and the boto3 client to access the S3 bucket where the sensors' data
# files are stored.
#

S3_BUCKET = "trm-cu-cc-aqi-bucket"
s3 = boto3.client("s3")


##
# Returns the corresponding AQI value for the PM10 particles value given as argument.
#

def AQI_PM10(PM10):
    # In case negative values are given, which would not be possible, return 0
    if PM10 < 0:
        return 0

    # Check in which range the PM10 particles value is included and return the associated AQI value
    for index, (low, high) in enumerate(PM10_AQI_RANGES, start=1):
        if low <= PM10 <= high:
            return index
    
    # If the value does not match any of the ranges, the AQI is 10
    return 10  # >100


##
# Returns the corresponding AQI value for the PM2.5 particles value given as argument.
#

def AQI_PM25(PM25):
    # In case negative values are given, which would not be possible, return 0
    if PM25 < 0:
        return 0

    # Check in which range the PM2.5 particles value is included and return the associated AQI value
    for index, (low, high) in enumerate(PM25_AQI_RANGES, start=1):
        if low <= PM25 <= high:
            return index
    
    # If the value does not match any of the ranges, the AQI is 10
    return 10  # >70


##
# Computes the AQI value for the PM10 and PM2.5 particles values given as arguments.
#
# Returns the maximum value between the AQI for PM10 and PM2.5 particles
#

def AQI(P1, P2):
    aqi_1 = AQI_PM10(P1)
    aqi_2 = AQI_PM25(P2)
    return max(aqi_1, aqi_2)


##
# Computes the AQI value for the last hour for the sensors whose ids are provided as an argument.
#
# Returns the mean for all the AQI values from all the required sensors
#

def compute_AQI_json(ids):
    # Get the json where the data for the last hour is listed from the S3 bucket
    resp = s3.get_object(
    Bucket=S3_BUCKET,
    Key="data.json"
    )
    data = json.loads(resp["Body"].read().decode("utf-8"))

    # List where all the individual AQI values will be stored
    aqi_list = []

    # For each sensor included in the json, check if its id is in the id list given as argument,
    # retrieve the PM10 (P1) and PM2.5 (P2) values, compute the AQI and append it to the list
    for x in data:
        if x["sensor"]["id"] in ids:
            for dv in x["sensordatavalues"]:
                if dv["value_type"] == "P1":
                    P1 = dv["value"]
                elif dv["value_type"] == "P2":
                    P2 = dv["value"]
            aqi = AQI(float(P1),float(P2))
            aqi_list.append(aqi)

    # Return the mean for all the AQI values from all the required sensors
    return(np.mean(aqi_list))


##
# Computes and returns the AQI for any csv file, whose key to the S3 bucket is provided as argument.
#

def compute_AQI_csv(key):
    # Get the csv where the data from the sensor is listed from the S3 bucket
    resp = s3.get_object(
    Bucket=S3_BUCKET,
    Key=key
    )
    df = pd.read_csv(io.BytesIO(resp["Body"].read()), sep=',')

    try:
        # Compute the mean for the PM10 (P1) and PM2.5 (P2) values and compute and return the AQI for those values
        P1 = df["P1"].mean()
        P2 = df["P2"].mean()
        return AQI(P1, P2)
    except:
        # Some sensors can have unknown data, listed as 'unknown' in the csv. 
        # Return nan in that case so the value can be ignored for the total AQI computation.
        return np.nan