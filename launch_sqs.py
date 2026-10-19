##
# Functions needed to launch the SQS queues
#

import boto3
from botocore.exceptions import ClientError

##
# Definition of the names, visibility timeouts and the boto3 client for the SQS.
#

sqs = boto3.client("sqs")
queue_names = ["aqi-main-queue", "aqi-geocoder-queue"]
queue_vis_to = ['300', '60']    # Visibility timeouts for the queues

##
# Launches the SQS queues.
#
# Returns the queues' urls
#

def launch_sqs():
    # Create the list where the queues' urls will be stored
    urls = []
    
    # Launch both SQS queues
    for i in range(len(queue_names)):
        # SQS creation
        try:
            # Get the SQS url's if already created
            urls.append(sqs.get_queue_url(QueueName=queue_names[i])['QueueUrl'])
            print(f"[SQS] Queue {queue_names[i]} exists")
        except ClientError:
            # Create the SQS if it does not exist yet and retrieve its url
            print(f"[SQS] Creating queue {queue_names[i]}")
            urls.append(sqs.create_queue(QueueName=queue_names[i], Attributes={'VisibilityTimeout':queue_vis_to[i]})["QueueUrl"])

    # Return the queues' urls
    return urls