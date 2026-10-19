##
# Functions needed to launch the workers EC2 instances
#

import boto3, base64
from botocore.exceptions import ClientError

##
# Definition of the names and the boto3 client for EC2, the Identity and Access Management, the 
# S3 bucket, CloudWatch and the Auto Scaling groups.
#

ec2_c = boto3.client("ec2")
iam = boto3.client("iam")
s3 = boto3.client("s3")
asg = boto3.client('autoscaling')
cloudwatch = boto3.client("cloudwatch")
ec2_name = "Worker"
profile_name = "LabInstanceProfile"
sg_name = "SSH-Access-EC2"
asg_name = "Worker-Autoscaling"
template_name = "trm-cu-cc-aqi-workers"

# Retrieve the LabRole role
profile = iam.get_instance_profile(InstanceProfileName=profile_name)['InstanceProfile']


##
# Launches the workers EC2 instances templates, the security group and the autoscaling group.
#

def launch_workers(bucket_name):
    # Security Group creation
    try:
        # Get the security group id if already created
        sg_id = ec2_c.describe_security_groups(GroupNames=[sg_name])['SecurityGroups'][0]['GroupId']
        print(f"[SG] Security group {sg_name} exists")
    except ClientError:
        # Create the security group if it does not exist yet and retrieve its id
        print(f"[SG] Creating security group {sg_name}")
        sg_id = ec2_c.create_security_group(
            Description='Allows SSH access for EC2 instances.',
            GroupName=sg_name
        )['GroupId']

        # Update the security group permissions to allow SSH connection
        print(f"[SG] Updating security group {sg_name} permissions")
        ec2_c.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [
                        {"CidrIp": "0.0.0.0/0"}
                    ]
                }
            ]
        )

    # Worker EC2 instance template creation
    print(f"[EC2] Uploading EC2 {ec2_name} coding files to S3 bucket {bucket_name}")

    # Create the S3 bucket key for the worker code
    worker_key = 'code/worker.zip'

    # Get the bytes from the worker's zip
    with open("worker.zip", 'rb') as f:
        worker_bytes = f.read()
    
    # Upload the worker code to the S3 bucket
    s3.put_object(
        Bucket=bucket_name,
        Key=worker_key,
        Body=worker_bytes
    )

    print(f"[EC2] Creating EC2 template {ec2_name}")

    # User data for the workers
    user_data = f"""#!/bin/bash
                sudo yum update -y
                sudo yum install -y python3.11 python3.11-pip
                pip3.11 install boto3 geopy pandas numpy requests
                aws s3 cp s3://{bucket_name}/code/worker.zip /home/ec2-user/
                unzip /home/ec2-user/worker.zip -d /home/ec2-user/worker
                cd /home/ec2-user/worker
                nohup python3.11 worker_main.py > worker.log 2>&1 &
                """
    
    # Encode the user data in base64 to add it to the template 
    user_data_bytes = user_data.encode("ascii")
    base64_bytes = base64.b64encode(user_data_bytes)
    base64_string = base64_bytes.decode("ascii")

    # Create the worker EC2 instance template using the uploaded code
    ec2_c.create_launch_template(
        LaunchTemplateName=template_name,
        LaunchTemplateData={
            'ImageId':'ami-068c0051b15cdb816',
            'SecurityGroups':[sg_name],
            'InstanceType':'t3.micro',
            'KeyName':'vockey',
            'IamInstanceProfile':{
            'Arn': profile['Arn']
            },
            'TagSpecifications':[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {'Key': 'Name', 'Value': ec2_name}
                    ]
                }
            ],
            'UserData':base64_string
        }
    )

    # Auto Scaling group creation
    print(f"[ASG] Creating auto scaling group {asg_name}")
    asg.create_auto_scaling_group(
        AutoScalingGroupName=asg_name,
        LaunchTemplate={'LaunchTemplateName':template_name},
        MinSize=1,  # Have at least one worker running
        MaxSize=3,  # Have at most three workers running
        DesiredCapacity=1,  # Set the desired value of concurrent workers at 1
        AvailabilityZones=[
            'us-east-1d',
            'us-east-1b',
            'us-east-1f',
            'us-east-1a',
            'us-east-1c'
        ],
        TerminationPolicies=['Default']
    )

    # Scaling out policy creation and retrieve its ARN
    print(f"[ASG] Creating scale out policy")
    scale_out_policy_arn = asg.put_scaling_policy(
        AutoScalingGroupName=asg_name,
        PolicyName="ScaleOutOnQueueDepth", 
        PolicyType="StepScaling",
        AdjustmentType="ChangeInCapacity",
        StepAdjustments=[
        {
            "MetricIntervalLowerBound": 0,
            "MetricIntervalUpperBound": 10,
            "ScalingAdjustment": 1  # If the queue has between 6 and 15 messages, add one instance
        },
        {
            "MetricIntervalLowerBound": 10,
            "ScalingAdjustment": 2  # If the queue has more than 15 messages, add two instances
        }
    ],
        Cooldown=60
    )["PolicyARN"]


    # CloudWatch alarm creation to trigger the scale out policy
    print(f"[CW] Creating scale out alarm")
    cloudwatch.put_metric_alarm(
        AlarmName="AQI-Queue-Depth-High",
        Namespace="AWS/SQS",
        MetricName="ApproximateNumberOfMessagesVisible",
        Dimensions=[
            {"Name": "QueueName", "Value": "aqi-main-queue"}
        ],
        Statistic="Average",
        Period=60,
        EvaluationPeriods=1,
        Threshold=5,    # When more than 5 instances from the lower bound stated from the policy (5 and 15), trigger the autoscaling group
        ComparisonOperator="GreaterThanThreshold",
        AlarmActions=[scale_out_policy_arn]
    )

    # Scaling in policy creation and retrieve its ARN
    print(f"[ASG] Creating scale in policy")
    scale_in_policy_arn = asg.put_scaling_policy(
        AutoScalingGroupName=asg_name,
        PolicyName="ScaleInOnQueueEmpty",
        PolicyType="StepScaling",
        AdjustmentType="ChangeInCapacity",
        StepAdjustments=[
            {
                "MetricIntervalUpperBound": 0,
                "ScalingAdjustment": -1     # If there are no messages for 4 minutes, have only one instance running
            }
        ],
        Cooldown=120
    )["PolicyARN"]


    # CloudWatch alarm creation to trigger the scale in policy
    print(f"[CW] Creating scale in alarm")
    cloudwatch.put_metric_alarm(
        AlarmName="AQI-Queue-Depth-Low",
        Namespace="AWS/SQS",
        MetricName="ApproximateNumberOfMessagesVisible",
        Dimensions=[
            {"Name": "QueueName", "Value": "aqi-main-queue"}
        ],
        Statistic="Average",
        Period=120,
        EvaluationPeriods=2,
        Threshold=0,
        ComparisonOperator="LessThanOrEqualToThreshold",
        AlarmActions=[scale_in_policy_arn]
    )