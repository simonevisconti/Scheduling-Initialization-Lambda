# PostNL Lambda Planning Tests

## API Contract

`lambda_handler.py` accepts planning requests from API Gateway, validates the payload, stores the original request, creates a job record, queues downstream processing, and returns an asynchronous job response.

### Top-Level Request Schema

Required fields:

- `planningType`: one of `network`, `region`, `vehicle`, `order`
- `requestedBy`: non-empty string
- `payload`: JSON object

Optional fields:

- `action`: non-empty string
- `metadata`: JSON object

### Payload by Planning Type

#### `network`

Required payload fields:

- `planningDate`: valid date in `YYYY-MM-DD` format
- `planningHorizon`: non-empty string
- `optimizationGoal`: non-empty string
- `networkId`: non-empty string

#### `region`

Required payload fields:

- `planningDate`: valid date in `YYYY-MM-DD` format
- `regionId`: non-empty string
- `optimizationGoal`: non-empty string
- `reason`: non-empty string

#### `vehicle`

Required payload fields:

- `planningDate`: valid date in `YYYY-MM-DD` format
- `regionId`: non-empty string

Additional rule:

- at least one of `vehicleId` or `vehicleIds` must be present
- if `vehicleIds` is provided, it must be a non-empty list of non-empty strings

#### `order`

Required payload fields:

- `planningDate`: valid date in `YYYY-MM-DD` format
- `orderId`: non-empty string
- `regionId`: non-empty string
- `reason`: non-empty string

Optional payload fields:

- `newConstraints`: JSON object

### Success Response

On success the Lambda returns `202 Accepted` with a body like:

```json
{
  "message": "Job accepted",
  "jobId": "planning-1234567890abcdef",
  "planningType": "network",
  "statusUrl": "/planning/planning-1234567890abcdef",
  "state": "PENDING"
}
```

### Error Responses

- `400 Bad Request`: invalid JSON, missing fields, invalid `planningType`, or invalid payload values
- `500 Internal Server Error`: missing environment configuration or failures while interacting with S3, DynamoDB, or SQS

### Request Examples

Example payloads are available in [planning_examples/network_planning_final.json](/home/visco/projects/PostNL/planning_examples/network_planning_final.json), [planning_examples/region_planning_final.json](/home/visco/projects/PostNL/planning_examples/region_planning_final.json), [planning_examples/vehicle_planning_final.json](/home/visco/projects/PostNL/planning_examples/vehicle_planning_final.json), and [planning_examples/order_rescheduling_final.json](/home/visco/projects/PostNL/planning_examples/order_rescheduling_final.json).

## Setup

AWS Lambda handler to configure:

```text
lambda_handler.lambda_handler
```

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

## Environment Variables

`lambda_handler.py` expects some configuration from AWS Lambda environment variables.

Required custom variables:

- `JOB_BUCKET_NAME`: S3 bucket where the input payload is stored
- `JOB_TABLE_NAME`: DynamoDB table used to persist the job record
- `JOB_QUEUE_URL`: SQS queue URL used to trigger downstream processing

Optional custom variable:

- `STATUS_URL_TEMPLATE`: Template used to build the returned job status URL. Default: `/planning/{jobId}`

AWS also provides standard runtime variables automatically in Lambda, such as `AWS_REGION`, but the function currently reads the custom variables above directly.

Example local setup:

```bash
export JOB_BUCKET_NAME=postnl-planning-input
export JOB_TABLE_NAME=postnl-planning-jobs
export JOB_QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/123456789012/postnl-planning
export STATUS_URL_TEMPLATE=/planning/{jobId}
```

## Run Tests

Run all tests:

```bash
venv/bin/pytest -q
```

Run specific test file:

```bash
venv/bin/pytest -q tests/test_validations.py
venv/bin/pytest -q tests/test_lambda_function.py
venv/bin/pytest -q tests/test_service.py
venv/bin/pytest -q tests/test_persistence.py
```

Run with coverage:

```bash
venv/bin/pytest --cov=lambda_handler --cov=service --cov=aws_clients --cov=validations --cov-report=term-missing
```

## Test Structure

- `tests/test_validations.py`: Tests for `parse_event_body` and `validate_payload`
- `tests/test_lambda_function.py`: Tests for `lambda_handler`
- `tests/test_service.py`: Tests for job orchestration in `service.py`
- `tests/test_persistence.py`: Tests for S3, DynamoDB, and SQS helper functions
- `tests/conftest.py`: Ensures project root imports work when running `pytest` directly from the virtual environment

Tests use pytest fixtures and mocking to avoid real AWS calls.

