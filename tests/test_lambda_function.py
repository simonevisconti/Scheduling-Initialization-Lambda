import json
import os
from unittest.mock import patch

import pytest

from lambda_handler import lambda_handler


@patch.dict(os.environ, {
    "JOB_BUCKET_NAME": "test-bucket",
    "JOB_TABLE_NAME": "test-table",
    "JOB_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
    "STATUS_URL_TEMPLATE": "/planning/{jobId}",
})
@patch("lambda_handler.start_planning_job")
class TestLambdaHandler:
    def test_lambda_handler_network_success(self, mock_start_planning_job):
        mock_start_planning_job.return_value = {
            "jobId": "planning-test-123",
            "planningType": "network",
            "state": "PENDING",
        }

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
        mock_start_planning_job.assert_called_once()

    def test_lambda_handler_region_success(self, mock_start_planning_job):
        mock_start_planning_job.return_value = {
            "jobId": "planning-test-123",
            "planningType": "region",
            "state": "PENDING",
        }

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

    def test_lambda_handler_vehicle_success(self, mock_start_planning_job):
        mock_start_planning_job.return_value = {
            "jobId": "planning-test-123",
            "planningType": "vehicle",
            "state": "PENDING",
        }

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

    def test_lambda_handler_order_success(self, mock_start_planning_job):
        mock_start_planning_job.return_value = {
            "jobId": "planning-test-123",
            "planningType": "order",
            "state": "PENDING",
        }

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

    def test_lambda_handler_invalid_json(self, mock_start_planning_job):
        event = {"body": "{invalid json"}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid JSON in request body" in body["message"]
        mock_start_planning_job.assert_not_called()

    def test_lambda_handler_validation_error(self, mock_start_planning_job):
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
        mock_start_planning_job.assert_not_called()

    @patch.dict(os.environ, {}, clear=True)
    def test_lambda_handler_missing_required_env_returns_server_error(self, mock_start_planning_job):
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
        mock_start_planning_job.assert_not_called()

    def test_lambda_handler_server_error(self, mock_start_planning_job):
        mock_start_planning_job.side_effect = Exception("S3 error")
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
