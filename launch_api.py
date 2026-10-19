##
# Functions needed to launch the API Gateway and the lambda function that handles the GET request
#

import boto3
from botocore.exceptions import ClientError

##
# Definition of the name and the boto3 client for the API Gateway, the lambda function,
# the Identity and Access Management and the S3 bucket.
#

apigw = boto3.client("apigateway")
iam = boto3.client("iam")
lamb = boto3.client("lambda")
s3 = boto3.client("s3")
api_name = "trm-cu-cc-aqi-api"
role_name = "LabRole"
lambda_name = "get-results"

# Retrieve the LabRole role
role = iam.get_role(RoleName=role_name)['Role']


##
# Launches the API Gateway and the lambda function.
#
# Returns API's name.
#

def launch_api(uid, bucket_name):
    # Lambda function creation
    try:
        # Get the lambda function's ARN if already created
        lambda_arn = lamb.get_function(FunctionName=lambda_name)['Configuration']['FunctionArn']
        print(f"[LMD] Lambda function {lambda_name} exists")
    except ClientError:
        # Create the lambda function if it does not exist yet
        print(f"[LMD] Uploading lambda function {lambda_name} to S3 bucket {bucket_name}")

        # Create the S3 bucket key for the lambda function code
        lambda_key = 'code/lambda_api.zip'

        # Get the bytes from the lambda function's zip
        with open("lambda_api.zip", 'rb') as f:
            lambda_bytes = f.read()

        # Upload the lambda function code to the S3 bucket
        s3.put_object(
            Bucket=bucket_name,
            Key=lambda_key,
            Body=lambda_bytes
        )
        
        # Create the lambda function using the uploaded code and retrieve its ARN
        print(f"[LMD] Creating lambda function {lambda_name}")
        lambda_arn = lamb.create_function(
            FunctionName=lambda_name,
            Runtime='python3.14',
            Role=role['Arn'],
            Handler='lambda_api.lambda_handler',
            Code={'S3Bucket': bucket_name,
                'S3Key': lambda_key
            },
            Description='Checks in the S3 bucket if the EC2 instance has generated a result.',
            Timeout=10,
            Publish=True
        )['FunctionArn']

    # API Gateway creation
    try:
        # Create the REST API
        api = apigw.create_rest_api(
            name=api_name,
            description="API for AQI computation service"
        )
        print(f"[API] Creating API gateway {api_name}")

        # Get the API its root's ids
        api_id = api["id"]
        root_id = apigw.get_resources(restApiId=api["id"])["items"][0]["id"]

        # Create the submit resource
        submit = apigw.create_resource(
            restApiId=api_id,
            parentId=root_id,
            pathPart="submit"
        )

        # Create the result resource
        result = apigw.create_resource(
            restApiId=api_id,
            parentId=root_id,
            pathPart="result"
        )

        # Create the submit method (POST)
        apigw.put_method(
            restApiId=api_id,
            resourceId=submit["id"],
            httpMethod="POST",
            authorizationType="NONE"
        )

        # Create the submit method's integration, with the needed CORS headers and defining the
        # request template
        apigw.put_integration(
            restApiId=api_id,
            resourceId=submit["id"],
            httpMethod="POST",
            type="AWS",
            integrationHttpMethod="POST",
            uri=f"arn:aws:apigateway:us-east-1:sqs:path/{uid}/aqi-main-queue",
            credentials=role['Arn'],
            requestParameters={
                "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
            },
            requestTemplates={
                "application/json": (
                    "Action=SendMessage&"
                    "MessageBody=$util.urlEncode("
                        "$util.escapeJavaScript("
                            "{\"job_id\":\"$context.requestId\",\"payload\":$input.json('$')}"
                        ")"
                    ")"
                )
            }
        )

        # Method response for successful POST (200) with CORS headers
        apigw.put_method_response(
            restApiId=api_id,
            resourceId=submit["id"],
            httpMethod="POST",
            statusCode="200",
            responseParameters={
                "method.response.header.Access-Control-Allow-Origin": True,
                "method.response.header.Access-Control-Allow-Headers": True,
                "method.response.header.Access-Control-Allow-Methods": True
            }
        )

        # Integration response (200) with CORS headers and success payload
        apigw.put_integration_response(
            restApiId=api_id,
            resourceId=submit["id"],
            httpMethod="POST",
            statusCode="200",
            responseParameters={
                "method.response.header.Access-Control-Allow-Origin": "'*'",
                "method.response.header.Access-Control-Allow-Headers": "'Content-Type'",
                "method.response.header.Access-Control-Allow-Methods": "'POST,OPTIONS'"
            },
            responseTemplates={
                # Return the API Gateway requestId as job_id to the browser
                "application/json": "{\"status\":\"ACCEPTED\",\"job_id\":\"$context.requestId\"}"
            }
        )

        # Create the submit options
        apigw.put_method(
            restApiId=api_id,
            resourceId=submit["id"],
            httpMethod="OPTIONS",
            authorizationType="NONE"
        )

        # OPTIONS integration
        apigw.put_integration(
            restApiId=api_id,
            resourceId=submit["id"],
            httpMethod="OPTIONS",
            type="MOCK",
            requestTemplates={
                "application/json": '{"statusCode": 200}'
            }
        )

        # OPTIONS method response
        apigw.put_method_response(
            restApiId=api_id,
            resourceId=submit["id"],
            httpMethod="OPTIONS",
            statusCode="200",
            responseParameters={
                "method.response.header.Access-Control-Allow-Origin": True,
                "method.response.header.Access-Control-Allow-Headers": True,
                "method.response.header.Access-Control-Allow-Methods": True
            }
        )

        # OPTIONS integration response
        apigw.put_integration_response(
            restApiId=api_id,
            resourceId=submit["id"],
            httpMethod="OPTIONS",
            statusCode="200",
            responseParameters={
                "method.response.header.Access-Control-Allow-Origin": "'*'",
                "method.response.header.Access-Control-Allow-Headers": "'Content-Type'",
                "method.response.header.Access-Control-Allow-Methods": "'POST,OPTIONS'"
            },
            responseTemplates={
                # Return the API Gateway requestId as job_id so the frontend can poll /result?job_id=...
                "application/json": "{\"status\":\"ACCEPTED\",\"job_id\":\"$context.requestId\"}"
            }

        )

        # Create the result method (GET)
        apigw.put_method(
            restApiId=api_id,
            resourceId=result["id"],
            httpMethod="GET",
            authorizationType="NONE",
            requestParameters={
                "method.request.querystring.job_id": True
            }
        )

        # Create the result method integration
        apigw.put_integration(
            restApiId=api_id,
            resourceId=result["id"],
            httpMethod="GET",
            type="AWS_PROXY",
            integrationHttpMethod="POST",
            uri=f"arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/{lambda_arn}/invocations"
        )

        # Create the result options
        apigw.put_method(
            restApiId=api_id,
            resourceId=result["id"],
            httpMethod="OPTIONS",
            authorizationType="NONE"
        )

        # OPTIONS integration
        apigw.put_integration(
            restApiId=api_id,
            resourceId=result["id"],
            httpMethod="OPTIONS",
            type="MOCK",
            requestTemplates={
                "application/json": '{"statusCode": 200}'
            }
        )

        # OPTIONS method response
        apigw.put_method_response(
            restApiId=api_id,
            resourceId=result["id"],
            httpMethod="OPTIONS",
            statusCode="200",
            responseParameters={
                "method.response.header.Access-Control-Allow-Origin": True,
                "method.response.header.Access-Control-Allow-Headers": True,
                "method.response.header.Access-Control-Allow-Methods": True
            }
        )

        # OPTIONS integration response
        apigw.put_integration_response(
            restApiId=api_id,
            resourceId=result["id"],
            httpMethod="OPTIONS",
            statusCode="200",
            responseParameters={
                "method.response.header.Access-Control-Allow-Origin": "'*'",
                "method.response.header.Access-Control-Allow-Headers": "'Content-Type'",
                "method.response.header.Access-Control-Allow-Methods": "'GET,OPTIONS'"
            }
        )

        # Add permissions to the lambda function to be invoked by the API Gateway
        lamb.add_permission(
            FunctionName=lambda_arn,
            StatementId="AllowApiGatewayInvoke",
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=f"arn:aws:execute-api:us-east-1:{uid}:{api_id}/*/GET/result"
        )

        # Deploy the API Gateway
        apigw.create_deployment(
            restApiId=api_id,
            stageName="prod"
        )
    except ClientError:
        # If a ClientError exception is raised, the API already exists
        print(f"[API] The API {api_name} exists")
    
    # Return API's name
    return api_name