##
# Launches the entire AWS system for the AQI computation
#

import launch_api, launch_geocoder, launch_lambda, launch_s3, launch_sqs, launch_workers, os, boto3

##
# Definition of the S3 bucket name and boto3 client.
#

bucket_name = "trm-cu-cc-aqi-bucket"
s3 = boto3.client("s3")

##
# Launches the entire AWS system to compute the AQI.
#

if __name__ == "__main__":
    print("\n\nLaunching the entire AWS system to compute the AQI.")
    print("\nPlease, follow the instructions when asked.")
    print("\nPlease, input your AWS account id (the twelve numbers that appear in the top-right corner of the AWS console).")
    print("\nPlease, input only the numbers.")
    uid = input("\nYour AWS Account ID: ")
    print("\n")
    launch_s3.launch_s3(bucket_name)
    main_queue_url, geocoder_queue_url = launch_sqs.launch_sqs()
    local_name = os.path.join(os.getcwd(), "sqs_urls.txt")
    with open(local_name, "w") as f:
        f.write(f"Main queue url: {main_queue_url}\n")
        f.write(f"Geocoder queue url: {geocoder_queue_url}")
    launch_lambda.launch_lambda(bucket_name)
    print("\n\nA txt file with the queues URLs has been generated in the working directory (sqs_urls.txt).")
    print("\nPlease, change the queues' URLs in worker_main.py and geocoder_main.py source code and save the changes.")
    print("\nThen, zip geocoder_main.py in geocoder.zip and the following files in worker.zip:\n\n" \
          "AQI_aws.py, download_s3.py, location_aws.py, s3_check.py and worker_main.py")
    done1 = input("\nIs it done? [Yes/No]: ")
    print("\n")
    if done1 == "Yes":
        launch_geocoder.launch_geocoder(bucket_name)
        launch_workers.launch_workers(bucket_name)
        api_name = launch_api.launch_api(uid, bucket_name)
        print("\n\nPlease, access the AWS console and get to the API Gateway Dashboard.")
        print(f"\nAccess the created API ({api_name}), get to Stages (in the list on the left side) and copy prod's stage Invoke URL.")
        print("\nPaste that API URL into the HTML index.html in the script zone (const API_BASE) and save the changes.")
        done2 = input("\nIs it done? [Yes/No]: ")
        print("\n")
        if done2 == "Yes":
            print(f"[S3] Uploading the HTML to the S3 bucket {bucket_name}")
            # Create the S3 bucket key for the HTML
            html_key = 'web/index.html'

            # Get the bytes from the worker's zip
            with open("index.html", 'rb') as f:
                html_bytes = f.read()

            # Upload the HTML to the S3 bucket
            s3.put_object(
                Bucket=bucket_name,
                Key=html_key,
                Body=html_bytes,
                ContentType="text/html; charset=utf-8"
            )
            print("\n\nProcess finished, AWS system fully deployed.")
            print("\nPlease, access the EC2 instances dashboard on the AWS console and make sure the instances are initialised before continuing.")
            print(f"\nPlease, access the S3 bucket {bucket_name} and open web/index.html to access the website.")
            print("\nIf you would prefer to run the stress tests, run stress_test.py, but first, the API base URL must be updated as well from its source code.")
            print("\n\n")
        else:
            print("\n\nThe website will not work if that URL is not changed. Please, change it and upload the html to the S3 bucket.")
            print("\n\n")
    else:
        print("\n\nThe code cannot work if the changes are not made. Please, make the changes and execute this code again.")
        print("\n\n")

