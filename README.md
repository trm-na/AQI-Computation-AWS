# AQI computation in AWS

This repository includes the code to deploy a service to acquire the AQI for a specific address over a period of time in AWS.

The information for the AQI metric comes from https://archive.sensor.community/.

The service was deployed using an AWS Academy Learner Lab account, which means that there is no complete access to all AWS’ functionalities. For example, there is a budget limit of $50, as well as a time limit of 4 hours to run the configured services (although the stored data in S3 buckets will remain even if the time limit is exceeded). Additionally, there is a risk of blocking the account if more than 4 EC2 instances are running at the same time, which limits the capabilities the service can offer. (AWS Academy Learner Lab - Student Guide, AWS Academy, 2022)

Moreover, due to Nominatim, the open-source geocoder used in this system, there is a request limitation to get the required information for the addresses solicited by the users, as only one request per second is allowed. (Nominatim Usage Policy (aka Geocoding Policy), OpenStreetMap Foundation, n.d., https://operations.osmfoundation.org/policies/nominatim/)

The system's architecture is shown in the following image:

<img width="1920" height="1063" alt="image" src="https://github.com/user-attachments/assets/2396860b-4910-4b35-ad4f-3964b8a4cfcc" />

The user accesses a website stored in an S3 bucket and is asked to input some data (type of computation (for the past hour, for the past week, for the past month or for a custom day), address, radius and date if needed, as the following image shows).

<img width="1181" height="657" alt="image" src="https://github.com/user-attachments/assets/ea4ad7ae-e6c7-4729-bbf2-2554f374a1bc" />

When the user clicks on the Compute AQI button, a POST request is sent to an API Gateway with the parameters requested by the user as the message body, and the API Gateway adds the message to an SQS queue, the main one. Additionally, a GET request is also sent, invoking a lambda function to retrieve the result from the computation.

The main queue is monitored by CloudWatch in order to control the number of EC2 instances in charge of processing the messages and computing the AQI, the workers. If less than 4 messages are visible in the queue, there will only be one active worker, if there are between 5 and 14 messages, there will be two active workers, and if more than 15 messages from the main queue are visible, there will be three active workers.

The workers get the messages from the main queue and process them. They check if the requested parameters have already been processed before, in which case the needed data to perform the computation would be already stored in the S3 bucket, and if not, the parameters have to be processed.

If the address has not been cached to the S3 bucket, the workers send a message with the address to the geocoder queue to be processed by another EC2 instance, the geocoder, which transforms the address to latitude, longitude and country code and stores the result in the S3 bucket.

If the sensors’ data for the computation type have not been cached yet to the S3 bucket, the workers download the files needed for the computation that are not available in the bucket and upload them to it.

Once all the data is present in the S3 bucket, the workers perform the AQI computation and upload a result file and some metadata for administration purposes to the bucket.

When the result file is stored in the S3 bucket, the lambda function previously invoked retrieves it and sends it to the API Gateway, which sends it to the user’s browser and the result of the computation is shown in the website, as the following image shows.

<img width="1181" height="657" alt="image" src="https://github.com/user-attachments/assets/d07dc9ce-6700-4b48-9aeb-f116d2fa0528" />

Additionally, the sensors’ data for the past hour stored in the S3 bucket is updated by a lambda function triggered by an EventBridge schedule that invokes the lambda function every hour.


To replicate the system with the code in this directory, please follow these steps:

	1.	Unzip the coding files.
	2.	Open a console/Powershell in the same directory as the coding files.
	3.	Execute aws configure.
	a.	Input the Access Key ID, Secret Access Key and Session Token given by AWS, enter us-east-1 as the region and leave output format blank.
	4.	Execute python launch_aws_system.py
	5.	Follow the instructions given in the programme. CAUTION: it is important to follow the instructions as stated and inputting the correct data. Failure to do so may make the system to not work. In this case, please, delete all the created systems in the AWS console and repeat the process. In case of additional failures, for example, a problem with the bucket name, please restart the deployment from the beginning, as the failure may affect all the source code files, included the ones that come compressed.
	6.	Access the S3 bucket and get to web/index.html and open it to see the website to request the AQI computations.

In case the stress tests want to be replicated:

	1.	Open stress_test.py with a text editor.
	2.	Change the API URL to the one retrieved for the HTML.
	3.	Change the constants to your liking.
	4.	Save the changes.
	5.	Execute python stress_test.py
		
To see the stress graphs: 

	1.	Access the AWS console and get to EC2 service.
	2.	Select Auto Scaling groups from the list on the left.
	3.	Select Worker-Autoscaling.
	4.	Select Monitoring.
	5.	Enable Auto Scaling group metrics collection.
	6.	Update the graphs when there is relevant data.

	i.	Access the AWS console and get to Simple Queue Service.
	ii.	Select the desired queue.
	iii.	Select Monitoring.
	iv.	Update the graphs when there is relevant data.

This code is my submission for Cranfield University's Cloud Computing module assignment for the MSc in Computational and Software Techniques in Engineering - Computational Intelligence for Data Analytics.
