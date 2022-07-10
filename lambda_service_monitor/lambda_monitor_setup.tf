terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 3.70"
    }
  }
}

provider "aws" {
  region = var.region
}

# Create the function role and policy, and attach them
resource "aws_iam_role" "role" {
  name               = join("_", [var.environ_tag, "role"])
  description        = "Functions require a role, these allow it to run and send logs"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": [
            "lambda.amazonaws.com",
            "events.amazonaws.com",
            "delivery.logs.amazonaws.com"
        ]
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF

  tags = { Environment = var.environ_tag }
}
resource "aws_iam_policy" "policy" {
  name        = join("_", [var.environ_tag, "policy"])
  description = "This policy gives the function permission to send logs"
  path        = "/"
  policy = templatefile("templates/policy", {
    loggroup_name = join("_", [var.environ_tag, "function"])
    to_addrs      = var.to_addrs
    from_addr     = var.from_addr
  })

  tags = { Environment = var.environ_tag }
}
resource "aws_iam_role_policy_attachment" "policy_atch" {
  role       = aws_iam_role.role.name
  policy_arn = aws_iam_policy.policy.arn
}

resource "aws_lambda_function" "function" {
  description   = "Check the service, log result, email if failure"
  function_name = join("_", [var.environ_tag, "function"])
  role          = aws_iam_role.role.arn
  handler       = "service_monitor.service_monitor"
  runtime       = "python3.9"

  filename         = "service_monitor.zip"
  source_code_hash = filebase64sha256("service_monitor.zip")

  environment {
    variables = {
      monitor_url    = var.monitor_url
      email_url      = var.email_url
      region         = var.region
      email_from     = var.from_addr
      email_to       = "%{for addr in var.to_addrs}${addr};%{endfor}"
      diff_threshold = var.diff_threshold
      timeout        = var.timeout
    }
  }

  tags = { Environment = var.environ_tag }
}

# Setup the EventBridge rule and attach it to the function
resource "aws_cloudwatch_event_rule" "event_rule" {
  name                = join("_", [var.environ_tag, "event_rule"])
  description         = "Run something every 1 hour"
  schedule_expression = "rate(1 hour)"

  tags = { Environment = var.environ_tag }
}
resource "aws_cloudwatch_event_target" "event_target" {
  # Associate the event rule with the function
  rule = aws_cloudwatch_event_rule.event_rule.name
  arn  = aws_lambda_function.function.arn
}
resource "aws_cloudwatch_log_group" "log_group" {
  name              = format("%s%s", "/aws/lambda/", aws_lambda_function.function.function_name)
  retention_in_days = 120
  tags              = { Environment = var.environ_tag }
}
resource "aws_lambda_permission" "perms" {
  # This permission lets EventBridge run the lambda
  statement_id  = "AllowEventBridgeExecution"
  action        = "lambda:InvokeFunction"
  principal     = "events.amazonaws.com"
  function_name = aws_lambda_function.function.function_name
  source_arn    = aws_cloudwatch_event_rule.event_rule.arn
}
