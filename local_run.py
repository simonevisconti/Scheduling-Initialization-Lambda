import argparse
import json
import os
from pathlib import Path
from unittest.mock import patch

from lambda_function import lambda_handler


DEFAULT_EXAMPLE = "planning_examples/network_planning_final.json"


def load_sample(sample_path):
    return json.loads(Path(sample_path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(
        description="Run lambda_handler locally with mocked AWS dependencies."
    )
    parser.add_argument(
        "sample",
        nargs="?",
        default=DEFAULT_EXAMPLE,
        help="Path to a planning example JSON file.",
    )
    args = parser.parse_args()

    sample = load_sample(args.sample)
    event = {"body": json.dumps(sample)}

    with patch.dict(
        os.environ,
        {
            "JOB_BUCKET_NAME": "test-bucket",
            "JOB_TABLE_NAME": "test-table",
            "JOB_QUEUE_URL": "https://example.com/test-queue",
            "STATUS_URL_TEMPLATE": "/planning/{jobId}",
        },
    ):
        with patch(
            "lambda_function.persist_payload_s3",
            return_value="planning-input/local-test.json",
        ):
            with patch(
                "lambda_function.create_job_record_dynamo",
                return_value={"status": "PENDING"},
            ):
                with patch("lambda_function.send_job_message_sqs"):
                    response = lambda_handler(event, None)

    print("Input file:", args.sample)
    print("Lambda response:")
    print(json.dumps(response, indent=2))
    print("Response body:")
    print(json.dumps(json.loads(response["body"]), indent=2))


if __name__ == "__main__":
    main()
