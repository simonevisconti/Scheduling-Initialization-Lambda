import os


REQUIRED_ENV_VARS = ("JOB_BUCKET_NAME", "JOB_TABLE_NAME", "JOB_QUEUE_URL")


def get_env(name, required=True, default=None):
    """Read environment variable with optional requirement check."""
    value = os.getenv(name, default)
    if required and not value:
        raise EnvironmentError(f"Missing required environment variable: {name}")
    return value


def validate_required_env_vars():
    """Fail fast when required Lambda configuration is missing."""
    for name in REQUIRED_ENV_VARS:
        get_env(name)


def job_status_url(job_id):
    """Generate status URL for a given jobId."""
    template = os.getenv("STATUS_URL_TEMPLATE", "/planning/{jobId}")
    return template.format(jobId=job_id)


def sqs_message_group_id(planning_type):
    """Return the FIFO message group id for SQS."""
    return os.getenv("JOB_QUEUE_MESSAGE_GROUP_ID", f"planning-{planning_type}")
