##
# Functions needed to launch the S3 bucket
#

import boto3
from botocore.exceptions import ClientError

##
# Definition of the name and the boto3 client for the S3 bucket.
#

s3 = boto3.client("s3")

##
# Launches the S3 bucket
#

def launch_s3(bucket_name):
    # S3 bucket creation
    try:
        # Check if the S3 bucket already exists
        s3.head_bucket(Bucket=bucket_name)
        print(f"[S3] Bucket {bucket_name} exists")
    except ClientError:
        # Create the S3 bucket if it does not exist yet
        print(f"[S3] Creating bucket {bucket_name}")
        s3.create_bucket(
            Bucket=bucket_name  # No region specification to be located in us-east-1 according to documentation
            )