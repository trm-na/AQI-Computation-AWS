##
# Functions needed to launch the lambda function to update the last hour sensor data
#

import boto3, time
from datetime import datetime
from botocore.exceptions import ClientError

##
# Definition of the name and the boto3 client for the lambda function, the Identity 
# and Access Management, the EventBridge scheduler and the S3 bucket.
#

lamb = boto3.client("lambda")
sch = boto3.client("scheduler")
iam = boto3.client("iam")
s3 = boto3.client("s3")
sch_name = "1-hour"
lambda_name = "update-data"
role_name = "LabRole"
layer_name="CC-assignment"

# Retrieve the LabRole role
role = iam.get_role(RoleName=role_name)['Role']

##
# Launches the lambda function and its layer.
#

def launch_lambda(bucket_name):
    # Lambda Layer creation
    try:
        # Get the layer's ARN if already created
        layer_arn = lamb.get_layer_version(LayerName=layer_name, VersionNumber=1)['LayerVersionArn']
        print(f"[LAY] Lambda layer function {layer_name} exists")
    except ClientError:
        # Create the layer if it does not exist yet and retrieve its ARN
        print(f"[LAY] Uploading lambda layer {layer_name} to S3 bucket {bucket_name}")

        # Create the S3 bucket key for the layer modules
        layer_key = 'code/layer.zip'

        # Get the bytes from the layer's zip
        with open("layer.zip", 'rb') as f:
            layer_bytes = f.read()

        # Upload the layer modules to the S3 bucket
        s3.put_object(
            Bucket=bucket_name,
            Key=layer_key,
            Body=layer_bytes
        )

        # Create the layer using the uploaded code and retrieve its ARN
        print(f"[LAY] Creating lambda layer {layer_name}")
        layer_arn = lamb.publish_layer_version(
            LayerName=layer_name,
            Description='All the needed modules to operate the system with lambda functions',
            Content={'S3Bucket': bucket_name,
                    'S3Key': layer_key}
        )['LayerVersionArn']

    # Lambda function creation
    try:
        # Get the lambda function ARN if already created
        lambda_arn = lamb.get_function(FunctionName=lambda_name)['Configuration']['FunctionArn']
        print(f"[LMD] Lambda function {lambda_name} exists")
    except ClientError:
        # Create the lambda function if it does not exist yet and retrieve its ARN
        print(f"[LMD] Uploading lambda function {lambda_name} to S3 bucket {bucket_name}")

        # Create the S3 bucket key for the lambda function code
        lambda_key = 'code/lambda.zip'

        # Get the bytes from the lambda's zip
        with open("lambda.zip", 'rb') as f:
            lambda_bytes = f.read()
        
        # Upload the lambda code to the S3 bucket
        s3.put_object(
            Bucket=bucket_name,
            Key=lambda_key,
            Body=lambda_bytes
        )
        
        # Create the lambda function using the uploaded code
        print(f"[LMD] Creating lambda function {lambda_name}")
        lambda_arn = lamb.create_function(
            FunctionName=lambda_name,
            Runtime='python3.14',
            Role=role['Arn'],
            Handler='lambda_download_s3.lambda_handler',
            Code={'S3Bucket': bucket_name,
                'S3Key': lambda_key
            },
            Description='Downloads the sensor data for the last hour, filters it and saves it into an S3 bucket.',
            Timeout=60,
            Publish=True,
            Layers=[layer_arn]
        )['FunctionArn']

        # Wait for 10 seconds to ensure the lambda is created and published
        time.sleep(10)

    # Invoke the lambda function to get the sensors' data
    print(f"[LMD] Invoking lambda function {lambda_name}")
    lamb.invoke(FunctionName=lambda_name)

    # EventBridge schedule creation
    try:
        # Check if the schedule has already been created
        sch.get_schedule(Name=sch_name)
        print(f"[SCH] Schedule {sch_name} exists")
    except ClientError:
        # Create the schedule if it does not exist yet
        print(f"[SCH] Creating schedule {sch_name}")
        today = datetime.today()
        sch.create_schedule(
            ActionAfterCompletion='NONE', 
            Description='Triggers the lambda to update the data.json every hour.',
            FlexibleTimeWindow={
                'Mode': 'OFF'
            },
            Name=sch_name,
            ScheduleExpression='rate(1 hours)',     # Trigger every hour
            ScheduleExpressionTimezone='Atlantic/Canary',
            StartDate=datetime(today.year, today.month, today.day, (today.hour + 1)),   # Start from the following hour when the code was executed
            State='ENABLED',
            Target={
            'Arn':lambda_arn,   # Invoke the lambda function when the schedule triggers
            'RoleArn':role['Arn']
            }
            )