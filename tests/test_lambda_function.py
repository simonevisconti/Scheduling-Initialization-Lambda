import json
import os
from unittest.mock import patch

import pytest

from lambda_function import lambda_handler


@patch.dict(os.environ, {
    "JOB_BUCKET_NAME": "test-bucket",
    "JOB_TABLE_NAME": "test-table",
    "JOB_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
    "STATUS_URL_TEMPLATE": "/planning/{jobId}",
})
@patch("lambda_function.persist_payload_s3")
@patch("lambda_function.create_job_record_dynamo")
@patch("lambda_function.send_job_message_sqs")
@patch("lambda_function.update_job_status_dynamo")
@patch("lambda_function._generate_job_id", return_value="planning-test-123")
class TestLambdaHandler:
    def test_lambda_handler_network_success(self, mock_generate_job_id, mock_update_dynamo_status, mock_send_sqs, mock_create_dynamo, mock_persist_s3):
        mock_persist_s3.return_value = "planning-input/planning-test-123.json"
        mock_create_dynamo.return_value = {"status": "PENDING"}

        event = {
            "body": json.dumps({
                "planningType": "network",
                "action": "replan",
                "requestedBy": "test@example.com",
                "payload": {
                    "planningDate": "2026-04-10",
                    "planningHorizon": "daily",
                    "optimizationGoal": "distance",
                    "networkId": "nl-main-network"
                },
                "metadata": {"source": "planning-ui"},
            })
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body["jobId"] == "planning-test-123"
        assert body["planningType"] == "network"
        assert body["statusUrl"] == "/planning/planning-test-123"
        assert body["state"] == "PENDING"

        mock_persist_s3.assert_called_once()
        mock_create_dynamo.assert_called_once()
        mock_send_sqs.assert_called_once()
        mock_update_dynamo_status.assert_not_called()
        mock_create_dynamo.assert_called_once_with(
            "planning-test-123",
            "network",
            "test@example.com",
            "replan",
            "planning-input/planning-test-123.json",
        )

    def test_lambda_handler_region_success(self, mock_generate_job_id, mock_update_dynamo_status, mock_send_sqs, mock_create_dynamo, mock_persist_s3):
        mock_persist_s3.return_value = "planning-input/planning-test-123.json"
        mock_create_dynamo.return_value = {"status": "PENDING"}

        event = {
            "body": json.dumps({
                "planningType": "region",
                "requestedBy": "test@example.com",
                "payload": {
                    "planningDate": "2026-04-10",
                    "regionId": "utrecht-region",
                    "optimizationGoal": "time",
                    "reason": "capacity-imbalance",
                }
            })
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body["planningType"] == "region"

    def test_lambda_handler_vehicle_success(self, mock_generate_job_id, mock_update_dynamo_status, mock_send_sqs, mock_create_dynamo, mock_persist_s3):
        mock_persist_s3.return_value = "planning-input/planning-test-123.json"
        mock_create_dynamo.return_value = {"status": "PENDING"}

        event = {
            "body": json.dumps({
                "planningType": "vehicle",
                "requestedBy": "test@example.com",
                "payload": {
                    "planningDate": "2026-04-10",
                    "regionId": "utrecht-region",
                    "vehicleId": "VEH-001"
                }
            })
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body["planningType"] == "vehicle"

    def test_lambda_handler_order_success(self, mock_generate_job_id, mock_update_dynamo_status, mock_send_sqs, mock_create_dynamo, mock_persist_s3):
        mock_persist_s3.return_value = "planning-input/planning-test-123.json"
        mock_create_dynamo.return_value = {"status": "PENDING"}

        event = {
            "body": json.dumps({
                "planningType": "order",
                "requestedBy": "test@example.com",
                "payload": {
                    "planningDate": "2026-04-10",
                    "orderId": "ORD-1007",
                    "regionId": "utrecht-region",
                    "reason": "customer-change",
                    "newConstraints": {"preferredTimeWindow": "14:00-16:00"},
                }
            })
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body["planningType"] == "order"

    def test_lambda_handler_invalid_json(self, mock_generate_job_id, mock_update_dynamo_status, mock_send_sqs, mock_create_dynamo, mock_persist_s3):
        event = {"body": "{invalid json"}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid JSON in request body" in body["message"]

    def test_lambda_handler_validation_error(self, mock_generate_job_id, mock_update_dynamo_status, mock_send_sqs, mock_create_dynamo, mock_persist_s3):
        event = {
            "body": json.dumps({
                "planningType": "invalid",
                "requestedBy": "test@example.com",
                "payload": {}
            })
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "planningType must be one of" in body["message"]

    @patch.dict(os.environ, {}, clear=True)
    def test_lambda_handler_missing_required_env_returns_server_error(self, mock_generate_job_id, mock_update_dynamo_status, mock_send_sqs, mock_create_dynamo, mock_persist_s3):
        event = {
            "body": json.dumps({
                "planningType": "network",
                "requestedBy": "test@example.com",
                "payload": {
                    "planningDate": "2026-04-10",
                    "planningHorizon": "daily",
                    "optimizationGoal": "distance",
                    "networkId": "nl-main-network",
                }
            })
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["message"] == "Internal server error"
        mock_persist_s3.assert_not_called()
        mock_create_dynamo.assert_not_called()
        mock_send_sqs.assert_not_called()
        mock_update_dynamo_status.assert_not_called()

    @patch("lambda_function.persist_payload_s3", side_effect=Exception("S3 error"))
    def test_lambda_handler_server_error(self, mock_s3_error, mock_generate_job_id, mock_update_dynamo_status, mock_send_sqs, mock_create_dynamo, mock_persist_s3):
        event = {
            "body": json.dumps({
                "planningType": "network",
                "requestedBy": "test@example.com",
                "payload": {
                    "planningDate": "2026-04-10",
                    "planningHorizon": "daily",
                    "optimizationGoal": "distance",
                    "networkId": "nl-main-network",
                }
            })
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["message"] == "Internal server error"

    def test_lambda_handler_marks_job_failed_to_queue(self, mock_generate_job_id, mock_update_dynamo_status, mock_send_sqs, mock_create_dynamo, mock_persist_s3):
        mock_persist_s3.return_value = "planning-input/planning-test-123.json"
        mock_create_dynamo.return_value = {"status": "PENDING"}
        mock_send_sqs.side_effect = Exception("SQS error")

        event = {
            "body": json.dumps({
                "planningType": "network",
                "requestedBy": "test@example.com",
                "payload": {
                    "planningDate": "2026-04-10",
                    "planningHorizon": "daily",
                    "optimizationGoal": "distance",
                    "networkId": "nl-main-network",
                }
            })
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["message"] == "Internal server error"
        mock_update_dynamo_status.assert_called_once_with(
            "planning-test-123",
            "FAILED_TO_QUEUE",
            "SQS error",
        )
