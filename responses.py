import json


def json_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def accepted_response(job_id, planning_type, status_url, state):
    return json_response(
        202,
        {
            "message": "Job accepted",
            "jobId": job_id,
            "planningType": planning_type,
            "statusUrl": status_url,
            "state": state,
        },
    )


def bad_request_response(message):
    return json_response(400, {"message": message})


def internal_server_error_response():
    return json_response(500, {"message": "Internal server error"})
