##
# Function to check if a file already exists in the S3 bucket

import boto3
from botocore.exceptions import ClientError

##
# Definition of the name and the boto3 client to access the S3 bucket where the sensors' data
# files are stored.
#

S3_BUCKET = "trm-cu-cc-aqi-bucket"
s3 = boto3.client("s3")


##
# Checks if the S3 bucket key given as an argument already exists.
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