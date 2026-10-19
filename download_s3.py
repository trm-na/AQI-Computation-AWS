##
# Functions needed to download the csv files listed in the sensors archive.
#

import requests, boto3, os, re, time, pandas as pd, s3_check
from datetime import datetime


##
# Definition of the name and the boto3 client to access the S3 bucket where the sensors' data
# files are stored, as well as the URL for the sensors archive.
#

BASE_URL = "https://archive.sensor.community"
S3_BUCKET = "trm-cu-cc-aqi-bucket"
s3 = boto3.client("s3")


##
# Checks if the filename provided as argument contains an id from the id list given as argument as well.
#
# Returns True or False and the matching id (if false, an empty list).
#

def contains_any_id(filename, id_list):
    # Remove .gz or .csv.gz
    name = os.path.splitext(filename)[0]
    name = os.path.splitext(name)[0]

    # Splits the filename parts separated by _
    parts = name.split("_")
    parts_set = set(parts)

    # Check intersection
    id_set = set(str(i) for i in id_list)

    # Find intersection
    matching_id = list(parts_set & id_set)

    # Return True (filename contains id included in the list) 
    # or False (filename does not contain id included in the list) 
    # and the matching id (if false, an empty list).
    return [not parts_set.isdisjoint(id_set), matching_id]


##
# Downloads the file available in the url given as argument to the S3 bucket 
# with the key provided as argument as well.
#

def download_file(url, key):
    # Creates a directory into which download the file if it did not exist.
    os.makedirs("sensor_data", exist_ok=True)

    # Filename generation. The filename includes the timestamp and the original url
    # to avoid deletion/overwritting of the data for other request
    t = time.localtime()
    timestamp = time.strftime('%b-%d-%Y_%H%M', t)
    filename = timestamp + "_" + url.split("/")[-1]
    local_name = os.path.join("sensor_data", filename)

    # Get the file from the url
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()

    # Write the file into the local file in chunks to avoid errors with large files.
    with open(local_name, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    f.close()

    # To avoid problems with compressed files, as read_csv reads both csv files and gz compressed csv files
    df = pd.read_csv(local_name, sep=';')

    # Upload the csv to the bucket with the given key
    s3.put_object(
    Bucket=S3_BUCKET,
    Key=key,
    Body=df.to_csv()
    )

    # Remove the local file from the instance as it will not be used anymore
    os.remove(local_name)

    # Printning for the logs
    print("Downloaded:", key)


##
# Downloads the relevant files from an entire directory from the sensors archive.
# It first checks if the data is already available in the S3 bucket to avoid redownloads.
# If a file is not available in the bucket, it is downloaded and uploaded to the S3 bucket.
#
# Returns the ids for the sensors whose data is available for the given date according to 
# the provided id list.
#

def download_directory(country, date, id_list):
    # Create the lists where the ids for the available sensors for the date and 
    # the sensors whose data has to be downloaded (respectively) will be stored
    found_ids = []
    download_ids = []

    # Check for every id in the id list if the data is already available in the S3 bucket.
    for id in id_list:
        # Creation of the S3 key as the files are stored in the S3 bucket, according to country,
        # year, date and id, all given as arguments
        s3_key = (
                    f"sensor_data/"
                    f"{country}/"
                    f"{date.year}/"
                    f"{date}/"
                    f"{id}.csv"
        )
        if s3_check.s3_object_exists(s3_key):
            # If the data is already available, append the id to the found ids list
            found_ids.append(id)
        else:
            # If the data is not available, append the id to the to-download ids list
            download_ids.append(id)

    # If there are files to download, download them.
    if (len(download_ids) > 0):
        # Define the url matching how the sensors archive do it according to the year
        if datetime.now().year == date.year:
            url = BASE_URL + "/" + str(date) + "/"
        else:
            url = BASE_URL + "/" + str(date.year) + "/" + str(date) + "/"

        # Printing for the logs
        print("Listing:", url)

        # Try to download the file in 10 attempts
        for attempt in range(1, 11):
            try:
                # Get the page from the url listing all the available files to download
                resp = requests.get(url)
                resp.raise_for_status()
                break

            except Exception as e:
                # If there was an error (probably a connection one), raise exception
                # Printing for the logs to know what failed
                print(f"Attempt {attempt} failed: {e}")

                if attempt < 11:
                    # If within the 10 attempts, retry getting the file in 5 seconds
                    print(f"Retrying in {5} seconds...")
                    time.sleep(5)
                else:
                    # If reached the maximum number of attempts, return the found ids list
                    # without downloading new files
                    print("Failed after maximum retries.")
                    return found_ids

        # Check if the urls for the downloadable files listed in the page include one of the ids
        # in the to-download list. If there is a match, download the file and upload it to the bucket
        for href in re.findall(r'href="([^"]+)"', resp.text):
            # Ignore irrelevant urls for parent directories
            if not href or href.startswith("?") or href.startswith("/"):
                continue
            if href in ("../", "./"):
                continue

            # Check if the url contains an id from the to-download list
            contains_id, id = contains_any_id(href, download_ids)
            if contains_id:
                # If true, generate the S3 bucket key, download the file and upload it to the bucket
                s3_key = (
                    f"sensor_data/"
                    f"{country}/"
                    f"{date.year}/"
                    f"{date}/"
                    f"{int(id[0])}.csv"
                )
                try:
                    download_file(url + href, s3_key)
                    # After a successful download, add the id to the available data id list
                    found_ids.append(int(id[0]))
                except Exception as e:
                    # If there was an error downloading the file, ignore it
                    print(f"Couldn't download {url + href}")
                    continue
    # Return the available data id list
    return found_ids

