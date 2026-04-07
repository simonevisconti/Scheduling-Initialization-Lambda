import logging
import uuid
from datetime import datetime, timedelta, timezone

from aws_clients import (
    create_job_record_dynamo,
    persist_payload_s3,
    send_job_message_sqs,
    update_job_status_dynamo,
)

logger = logging.getLogger(__name__)


def generate_job_id():
    """Generate a unique job identifier."""
    return f"planning-{uuid.uuid4().hex}"


def current_timestamp():
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ttl_timestamp(days=365):
    """Return a Unix timestamp in seconds for DynamoDB TTL."""
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    return int(expires_at.timestamp())


def s3_key_for_job(job_id):
    """Build S3 key path for a job payload."""
    return f"planning-input/{job_id}.json"


def start_planning_job(body, planning_type):
    """Persist the request and enqueue downstream planning work."""
    job_id = generate_job_id()
    logger.info("Generated jobId=%s for planningType=%s", job_id, planning_type)

    s3_key = s3_key_for_job(job_id)
    persist_payload_s3(job_id, body, s3_key)

    timestamp = current_timestamp()
    job_item = create_job_record_dynamo(
        job_id,
        planning_type,
        body["requestedBy"],
        body.get("action"),
        s3_key,
        timestamp,
        ttl_timestamp(),
    )

    try:
        send_job_message_sqs(job_id, planning_type, s3_key)
    except Exception as exc:
        logger.warning("Queueing failed for jobId=%s; updating DynamoDB status to FAILED_TO_QUEUE", job_id)
        update_job_status_dynamo(job_id, "FAILED_TO_QUEUE", current_timestamp(), str(exc))
        raise

    logger.info("Accepted planning job jobId=%s planningType=%s status=%s", job_id, planning_type, job_item["status"])
    return {
        "jobId": job_id,
        "planningType": planning_type,
        "state": job_item["status"],
    }
