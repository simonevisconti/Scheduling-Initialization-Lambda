import json
import logging
import os
import uuid
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from validations import parse_event_body, validate_payload

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

REQUIRED_ENV_VARS = ("JOB_BUCKET_NAME", "JOB_TABLE_NAME", "JOB_QUEUE_URL")


def _get_env(name, required=True, default=None):
    """Read environment variable with optional requirement check.

    Raises EnvironmentError if required variable is missing.
    """
    value = os.getenv(name, default)
    if required and not value:
        raise EnvironmentError(f"Missing required environment variable: {name}")
    return value


def _validate_required_env_vars():
    """Fail fast when required Lambda configuration is missing."""
    for name in REQUIRED_ENV_VARS:
        _get_env(name)


def _generate_job_id():
    """Generate a unique job identifier."""
    return f"planning-{uuid.uuid4().hex}"


def _current_timestamp():
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.utcnow().isoformat() + "Z"


def _s3_key_for_job(job_id):
    """Build S3 key path for a job payload."""
    return f"planning-input/{job_id}.json"


def persist_payload_s3(job_id, data):
    """Persist request payload as JSON in S3.

    Stores the payload under JOB_BUCKET_NAME at planning-input/{job_id}.json.
    """
    bucket = _get_env("JOB_BUCKET_NAME")
    key = _s3_key_for_job(job_id)
    content = json.dumps(data, default=str).encode("utf-8")

    s3 = boto3.client("s3")
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=content, ContentType="application/json")
    except ClientError as exc:
        logger.exception("Failed to persist payload in S3 for jobId=%s bucket=%s key=%s", job_id, bucket, key)
        raise

    logger.info("Persisted request payload to S3 for jobId=%s bucket=%s key=%s", job_id, bucket, key)

    return key


def create_job_record_dynamo(job_id, planning_type, requested_by, action, s3_key):
    """Create a job record in DynamoDB with initial PENDING state."""
    table_name = _get_env("JOB_TABLE_NAME")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    item = {
        "jobId": job_id,
        "planningType": planning_type,
        "status": "PENDING",
        "createdAt": _current_timestamp(),
        "updatedAt": _current_timestamp(),
        "payloadS3Key": s3_key,
        "requestedBy": requested_by,
    }
    if action:
        item["action"] = action

    try:
        table.put_item(Item=item)
    except ClientError as exc:
        logger.exception("Failed to write job record to DynamoDB for jobId=%s table=%s", job_id, table_name)
        raise

    logger.info("Created DynamoDB job record for jobId=%s planningType=%s status=%s", job_id, planning_type, item["status"])

    return item


def update_job_status_dynamo(job_id, status, error_message=None):
    """Update an existing job record status in DynamoDB."""
    table_name = _get_env("JOB_TABLE_NAME")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    expression_attribute_values = {
        ":status": status,
        ":updatedAt": _current_timestamp(),
    }
    update_expression = "SET #status = :status, updatedAt = :updatedAt"
    expression_attribute_names = {"#status": "status"}

    if error_message is not None:
        expression_attribute_values[":errorMessage"] = error_message
        update_expression += ", errorMessage = :errorMessage"

    try:
        table.update_item(
            Key={"jobId": job_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
        )
    except ClientError:
        logger.exception("Failed to update job status in DynamoDB for jobId=%s status=%s", job_id, status)
        raise

    logger.info("Updated DynamoDB job status for jobId=%s status=%s", job_id, status)


def send_job_message_sqs(job_id, planning_type, s3_key):
    """Send a message to SQS to trigger downstream processing."""
    queue_url = _get_env("JOB_QUEUE_URL")
    sqs = boto3.client("sqs")

    message_body = json.dumps({
        "jobId": job_id,
        "planningType": planning_type,
        "payloadS3Key": s3_key,
    })

    try:
        sqs.send_message(QueueUrl=queue_url, MessageBody=message_body)
    except ClientError as exc:
        logger.exception("Failed to send message to SQS for jobId=%s queueUrl=%s", job_id, queue_url)
        raise

    logger.info("Queued planning job for jobId=%s planningType=%s", job_id, planning_type)


def _job_status_url(job_id):
    """Generate status URL for a given jobId."""
    template = os.getenv("STATUS_URL_TEMPLATE", "/planning/{jobId}")
    return template.format(jobId=job_id)


def lambda_handler(event, context):
    """Lambda entry point.

    Parameters:
        event (dict): API Gateway event payload. Typically contains 'body'.
        context (LambdaContext): AWS Lambda context object.

    Returns:
        dict: HTTP response with statusCode, headers, and JSON body.

    Behavior:
        - Parse and normalize request payload
        - Validate according to planningType (network/region/vehicle)
        - Persist payload in S3, job metadata in DynamoDB, enqueue SQS message
        - Return 202 on success
        - Return 400 on validation/client errors
        - Return 500 on unexpected server errors
    """
    logger.info("Received lambda event")

    try:
        _validate_required_env_vars()
        logger.info("Validated required environment configuration")

        # 1. Parse and normalize the incoming body
        body = parse_event_body(event)
        logger.info("Parsed request body successfully")

        # 2. Validate payload based on planning type (network|region|vehicle)
        planning_type, payload = validate_payload(body)
        logger.info("Validated request payload for planningType=%s requestedBy=%s", planning_type, body.get("requestedBy"))

        # 3. Orchestrate work items
        job_id = _generate_job_id()
        logger.info("Generated jobId=%s for planningType=%s", job_id, planning_type)
        s3_key = persist_payload_s3(job_id, body)
        job_item = create_job_record_dynamo(
            job_id,
            planning_type,
            body["requestedBy"],
            body.get("action"),
            s3_key,
        )
        try:
            send_job_message_sqs(job_id, planning_type, s3_key)
        except Exception as exc:
            logger.warning("Queueing failed for jobId=%s; updating DynamoDB status to FAILED_TO_QUEUE", job_id)
            update_job_status_dynamo(job_id, "FAILED_TO_QUEUE", str(exc))
            raise

        # 4. Return 202 accepted as this is an asynchronous planning job
        logger.info("Accepted planning job jobId=%s planningType=%s status=%s", job_id, planning_type, job_item["status"])
        return {
            "statusCode": 202,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "message": "Job accepted",
                "jobId": job_id,
                "planningType": planning_type,
                "statusUrl": _job_status_url(job_id),
                "state": job_item["status"]
            })
        }

    except ValueError as exc:
        # Validation error: client-side issue, return 400
        logger.warning("Validation failed: %s", exc)
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": str(exc)})
        }

    except EnvironmentError as exc:
        logger.exception("Missing required Lambda configuration")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": "Internal server error"})
        }

    except Exception as exc:
        # Unexpected S3/Dynamo/SQS or runtime issue: server-side
        logger.exception("Unexpected error while processing planning request")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": "Internal server error"})
        }
