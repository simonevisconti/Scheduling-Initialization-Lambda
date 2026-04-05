# Scheduling Initialization Lambda

## Overview

This project implements an AWS Lambda function that initializes asynchronous scheduling jobs.

The Lambda accepts a planning request, validates the payload, stores the full request in S3, creates a job record in DynamoDB, sends a message to SQS for downstream processing, and returns a `202 Accepted` response with the generated job information.

![AWS Serverless Planning Diagram](./assets/aws-serverless-planning.svg)

## How It Works

The request flow is:

1. parse the API Gateway event body
2. validate the request based on the selected planning type
3. store the original payload in S3
4. create a job record in DynamoDB
5. enqueue the job in SQS
6. return a `202` response with `jobId`, `planningType`, `statusUrl`, and the initial state

If validation fails, the Lambda returns `400`.

If configuration or AWS interactions fail, the Lambda returns `500`.

## Project Structure

- [lambda_handler.py](/home/visco/projects/PostNL/lambda_handler.py): Lambda entrypoint and top-level request handling
- [service.py](/home/visco/projects/PostNL/service.py): scheduling job orchestration
- [aws_clients.py](/home/visco/projects/PostNL/aws_clients.py): S3, DynamoDB, and SQS interactions
- [validations.py](/home/visco/projects/PostNL/validations.py): request parsing and payload validation
- [responses.py](/home/visco/projects/PostNL/responses.py): reusable HTTP response builders
- [config.py](/home/visco/projects/PostNL/config.py): environment variable helpers and status URL generation
- [assets/aws-serverless-planning.svg](/home/visco/projects/PostNL/assets/aws-serverless-planning.svg): architecture diagram
- [planning_examples/](/home/visco/projects/PostNL/planning_examples): sample request payloads
- [tests/](/home/visco/projects/PostNL/tests): unit tests

## Request Types

The Lambda currently supports these planning types:

- `network`
- `region`
- `vehicle`
- `order`

Each request must include:

- `planningType`
- `requestedBy`
- `payload`

Optional top-level fields:

- `action`
- `metadata`

Validation rules are implemented in [validations.py](/home/visco/projects/PostNL/validations.py), and example payloads are available in [planning_examples/](/home/visco/projects/PostNL/planning_examples).

## AWS Configuration

AWS Lambda handler to configure:

```text
lambda_handler.lambda_handler
```

Required environment variables:

- `JOB_BUCKET_NAME`: S3 bucket where the full request payload is stored
- `JOB_TABLE_NAME`: DynamoDB table used for job metadata
- `JOB_QUEUE_URL`: SQS queue URL used to trigger downstream processing

Optional environment variables:

- `STATUS_URL_TEMPLATE`: template used to build the returned job status URL
  Default: `/planning/{jobId}`

## Local Development

Install dependencies:

```bash
pip install -r requirements/app.txt
```

Recompile locked dependencies after changing [requirements/app.in](/home/visco/projects/PostNL/requirements/app.in):

```bash
pip-compile requirements/app.in --output-file requirements/app.txt
```

If you use the project virtual environment:

```bash
source venv/bin/activate
```

Run the Lambda locally with mocked AWS services:

```bash
venv/bin/python local_run.py
```

Run a specific example file:

```bash
venv/bin/python local_run.py planning_examples/network_planning_final.json
```

## Testing

Run the full test suite:

```bash
venv/bin/python -m pytest

Run with coverage:

```bash
venv/bin/python -m pytest --cov=lambda_handler --cov=service --cov=aws_clients --cov=validations --cov-report=term-missing
```

Test layout:

- [tests/test_validations.py](/home/visco/projects/PostNL/tests/test_validations.py): request parsing and validation
- [tests/test_lambda_function.py](/home/visco/projects/PostNL/tests/test_lambda_function.py): Lambda handler behavior
- [tests/test_service.py](/home/visco/projects/PostNL/tests/test_service.py): orchestration logic
- [tests/test_persistence.py](/home/visco/projects/PostNL/tests/test_persistence.py): S3, DynamoDB, and SQS helper functions

## Example Payloads

Sample payloads are available in:

- [planning_examples/network_planning_final.json](/home/visco/projects/PostNL/planning_examples/network_planning_final.json)
- [planning_examples/region_planning_final.json](/home/visco/projects/PostNL/planning_examples/region_planning_final.json)
- [planning_examples/vehicle_planning_final.json](/home/visco/projects/PostNL/planning_examples/vehicle_planning_final.json)
- [planning_examples/order_rescheduling_final.json](/home/visco/projects/PostNL/planning_examples/order_rescheduling_final.json)

## Notes

- the full request payload is stored in S3
- DynamoDB stores job metadata and state, not the full payload
- SQS is used to trigger asynchronous downstream processing
- the handler is intentionally kept small, with validation, orchestration, AWS access, and responses split into separate modules
