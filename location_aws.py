##
# Functions needed for the geolocation.
#

import geopy.distance, s3_check, time
import json, boto3

##
# Definition of the name and the boto3 client to access the S3 bucket where the addresses are 
# stored, as well as the default value for the radius of the area where the sensors used for 
# the AQI computation are located and the maximum number of sensors to collect information from 
# to compute the AQI for each location.
#

RAD_LOC = 20     # Radius in km from the input location to the limit of the area where the sensors are located
N_SENSORS = 5    # Max number of sensors to collect information from to compute the AQI
S3_BUCKET = "trm-cu-cc-aqi-bucket"
s3 = boto3.client("s3")


##
# Computes and returns the distance between two points given their latitude and longitude.
# To do so, it uses geopy's geodesic distance function.
#

def latlon_dist(lat1, lon1, lat2, lon2):
    # Create the coordinates for both points using the style geopy's function needs
    coords1 = (str(lat1)+","+str(lon1))

    coords2 = (str(lat2)+","+str(lon2))
    # Compute the distance between both points and return it
    dist = geopy.distance.geodesic(coords1, coords2).km
    return dist


##
# Gets the nearest sensors to the location whose latitude, longitude and country code are given
# as arguments inside the circular area defined by the radius. If the radius is not provided as 
# an argument, the function uses the default value RAD_LOC.
#
# Returns a list with up to N_SENSORS sensor ids and a status code depending on whether there are 
# sensors inside the circular area or not.
#

def get_nearest(lat, lon, country, radius=RAD_LOC):
    # Create the list where the distances and the ids of the sensors will be stored
    distances = []
    dist_id = []

    # Get the data.json file from the S3 bucket to retrieve the latitude and longitude of all 
    # the relevant sensors
    resp = s3.get_object(
    Bucket=S3_BUCKET,
    Key="data.json"
    )
    data = json.loads(resp["Body"].read().decode("utf-8"))

    # For each sensor in the json, check if it is close to the given location
    for x in data:
        if x["location"]["country"].lower() == country.lower():
            # If the sensor is located in the same country as the one provided as an argument, 
            # compute the distance from this sensor to the given latitude and longitude and 
            # append the distance and the sensor id to the lists
            dist = latlon_dist(lat, lon, x["location"]["latitude"], x["location"]["longitude"])
            distances.append(dist)
            dist_id.append([x["sensor"]["id"], dist])
    
    # If no sesnors near the given location are found, compute the distance from the provided 
    # location to each sensor and append them and the sensor ids to the lists.
    if len(distances) == 0:
            for x in data:
                dist = latlon_dist(lat, lon, x["location"]["latitude"], x["location"]["longitude"])
                distances.append(dist)
                dist_id.append([x["sensor"]["id"], dist])

    # Compute the distance to the closest sensor
    min_d = min(distances)

    # Sort the list with the distances and their respective sensor ids by distance in ascending order
    sorted_dist_id = sorted(dist_id, key=lambda x: x[1])

    # If more than N_SENSORS have been found inside the area, reduce the list to N_SENSORS sensors
    if len(sorted_dist_id) > N_SENSORS:
        sorted_dist_id = sorted_dist_id[0:N_SENSORS]

    # If the closest sensor is outside the radius, return just the closest sensor to the given 
    # location and a status of 0
    if min_d > radius:
        return [[sorted_dist_id[0][0]], 0]
    # Else, return the sensor ids from the list (capped at N_SENSORS) if they are inside the area 
    # (their distance to the given location is less than the provided radius)
    else:
        return [[x[0] for x in sorted_dist_id if x[1] <= radius], 1]
    

##
# Gets the location for the given S3 bucket key.
#
# Returns the location's latitude, longitude and country code.
#

def get_loc(key):
    # Get the file from the S3 bucket using the provided key
    resp = s3.get_object(
    Bucket=S3_BUCKET,
    Key=key
    )
    data = json.loads(resp["Body"].read().decode("utf-8"))

    # Return the location's latitude, longitude and country code
    return [data["latitude"], data["longitude"], data["country"]]


##
# Waits for the geocoder to retrieve the latitude and longitude of a given address using an 
# exponential backoff algorithm. The geocoder should generate a file stored in the S3 bucket 
# with the key given as an argument.
#
# Returns True if the geocoder has successfully completed its job during the execution.
# Otherwise, returns False.
#

def geocoder_wait(key):
    # Define the starting wait time, the current time waited and the maximum time to wait
    wait = 2
    waited = 0
    max_wait = 180

    # While the current time waited is less than the maximum time to wait, execute the routine
    while waited < max_wait:
        if s3_check.s3_object_exists(key):
            # If the address file exists in the S3 bucket, return True
            return True

        # If the address file does not exist, the geocoder is still processing the address, so 
        # the system waits for wait seconds.
        time.sleep(wait)

        # Update current time waited
        waited += wait

        # Update wait time using an exponential backoff method, using powers of 2 until a wait 
        # time of 15 seconds is reached
        wait = min(wait * 2, 15)

    # If the geocoder has not processed the address successfully in max_wait seconds, return False
    return False
