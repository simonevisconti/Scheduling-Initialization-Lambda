import json
import logging

import boto3
from botocore.exceptions import ClientError

from config import get_env, sqs_message_group_id

logger = logging.getLogger(__name__)


def persist_payload_s3(job_id, data, s3_key):
    """Persist request payload as JSON in S3."""
    bucket = get_env("JOB_BUCKET_NAME")
    content = json.dumps(data, default=str).encode("utf-8")

    s3 = boto3.client("s3")
    try:
        s3.put_object(Bucket=bucket, Key=s3_key, Body=content, ContentType="application/json")
    except ClientError:
        logger.exception("Failed to persist payload in S3 for jobId=%s bucket=%s key=%s", job_id, bucket, s3_key)
        raise

    logger.info("Persisted request payload to S3 for jobId=%s bucket=%s key=%s", job_id, bucket, s3_key)
    return s3_key


def create_job_record_dynamo(job_id, planning_type, requested_by, action, s3_key, timestamp):
    """Create a job record in DynamoDB with initial PENDING state."""
    table_name = get_env("JOB_TABLE_NAME")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    item = {
        "jobId": job_id,
        "planningType": planning_type,
        "status": "PENDING",
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "payloadS3Key": s3_key,
        "requestedBy": requested_by,
    }
    if action:
        item["action"] = action

    try:
        table.put_item(Item=item)
    except ClientError:
        logger.exception("Failed to write job record to DynamoDB for jobId=%s table=%s", job_id, table_name)
        raise

    logger.info("Created DynamoDB job record for jobId=%s planningType=%s status=%s", job_id, planning_type, item["status"])
    return item


def update_job_status_dynamo(job_id, status, timestamp, error_message=None):
    """Update an existing job record status in DynamoDB."""
    table_name = get_env("JOB_TABLE_NAME")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    expression_attribute_values = {
        ":status": status,
        ":updatedAt": timestamp,
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
    """Send a message to a FIFO SQS queue to trigger downstream processing."""
    queue_url = get_env("JOB_QUEUE_URL")
    sqs = boto3.client("sqs")

    message_body = json.dumps({
        "jobId": job_id,
        "planningType": planning_type,
        "payloadS3Key": s3_key,
    })
    message_group_id = sqs_message_group_id(planning_type)

    try:
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body,
            MessageGroupId=message_group_id,
            MessageDeduplicationId=job_id,
        )
    except ClientError:
        logger.exception("Failed to send message to SQS for jobId=%s queueUrl=%s", job_id, queue_url)
        raise

    logger.info(
        "Queued planning job for jobId=%s planningType=%s messageGroupId=%s",
        job_id,
        planning_type,
        message_group_id,
    )
