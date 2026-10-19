##
# Functions needed to launch the geocoder EC2 instance
#

import boto3, base64
from botocore.exceptions import ClientError

##
# Definition of the name and the boto3 client and resource for EC2, the Identity and Access 
# Management and the S3 bucket.
#

ec2 = boto3.resource("ec2")
ec2_c = boto3.client("ec2")
iam = boto3.client("iam")
s3 = boto3.client("s3")
asg = boto3.client('autoscaling')
ec2_name = "Geocoder"
profile_name = "LabInstanceProfile"
sg_name = "SSH-Access-EC2"
template_name = "trm-cu-cc-aqi-geocoder"
asg_name = "Geocoder-Autoscaling"

# Retrieve the LabRole role
profile = iam.get_instance_profile(InstanceProfileName=profile_name)['InstanceProfile']

##
# Launches the geocoder EC2 instance and the security group.
#

def launch_geocoder(bucket_name):
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

    # Geocoder EC2 instance creation
    print(f"[EC2] Uploading EC2 {ec2_name} coding files to S3 bucket {bucket_name}")

    # Create the S3 bucket key for the geocoder code
    geocoder_key = 'code/geocoder.zip'

    # Get the bytes from the geocoder's zip
    with open("geocoder.zip", 'rb') as f:
        geocoder_bytes = f.read()

    # Upload the geocoder code to the S3 bucket
    s3.put_object(
        Bucket=bucket_name,
        Key=geocoder_key,
        Body=geocoder_bytes
    )

    # Create the geocoder EC2 instance using the uploaded code
    print(f"[EC2] Creating EC2 template {ec2_name}")

    # User data for the workers
    user_data = f"""#!/bin/bash
                    sudo yum update -y
                    sudo yum install -y python3.11 python3.11-pip
                    pip3.11 install boto3 geopy pandas numpy requests
                    aws s3 cp s3://{bucket_name}/code/geocoder.zip /home/ec2-user/
                    unzip /home/ec2-user/geocoder.zip -d /home/ec2-user/geocoder
                    cd /home/ec2-user/geocoder
                    nohup python3.11 geocoder_main.py > geocoder.log 2>&1 &
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
        MinSize=1,  # Have just one worker running
        MaxSize=1,  # Have just one worker running
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
