# PostNL Lambda Planning Tests

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

If you use the project virtual environment:

```bash
source venv/bin/activate
```

## Environment Variables

`lambda_function.py` expects some configuration from AWS Lambda environment variables.

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
```

Run with coverage:

```bash
venv/bin/pytest --cov=lambda_function --cov=validations
```

## Test Structure

- `tests/test_validations.py`: Tests for `parse_event_body` and `validate_payload`
- `tests/test_lambda_function.py`: Tests for `lambda_handler` with mocked AWS services
- `tests/conftest.py`: Ensures project root imports work when running `pytest` directly from the virtual environment

Tests use pytest fixtures and mocking to avoid real AWS calls.

