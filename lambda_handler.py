import logging

from config import job_status_url, validate_required_env_vars
from responses import accepted_response, bad_request_response, internal_server_error_response
from service import start_planning_job
from validations import parse_event_body, validate_payload

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """Lambda entry point for start-planning requests."""
    logger.info("Received lambda event")

    try:
        validate_required_env_vars()
        logger.info("Validated required environment configuration")

        body = parse_event_body(event)
        logger.info("Parsed request body successfully")

        planning_type, _payload = validate_payload(body)
        logger.info("Validated request payload for planningType=%s requestedBy=%s", planning_type, body.get("requestedBy"))

        result = start_planning_job(body, planning_type)
        return accepted_response(
            result["jobId"],
            result["planningType"],
            job_status_url(result["jobId"]),
            result["state"],
        )

    except ValueError as exc:
        logger.warning("Validation failed: %s", exc)
        return bad_request_response(str(exc))

    except EnvironmentError:
        logger.exception("Missing required Lambda configuration")
        return internal_server_error_response()

    except Exception:
        logger.exception("Unexpected error while processing planning request")
        return internal_server_error_response()
