# Service Monitor

This creates an AWS lambda function that runs once per 10 minutes and checks on the service.  It emails you whenever the service isn't responding as expected.

# Setup

Edit the `secrets.tf_TEMPLATE` to reflect the desired email settings.  Run make to create the deployment code zip file.  Run `AWS_PROFILE="profile_name" terraform apply` to deploy the lambda and security settings.

# Usage

The lambda will run via an EventBridge event once every 10 minutes using the smallest amount of RAM possible, and taking (hopefully) only a short amount of time.  Timeout is set to 1 second...  This will result in free tier usage of Lambda.  Logs will flow to cloudwatch.

You'll want to make sure cloudwatch logs get cleared out.

# TODO

Automatically clear out cloudwatch logs and build longer term metrics from them.
