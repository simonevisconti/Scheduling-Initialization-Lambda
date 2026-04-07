import json
import os
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from aws_clients import (
    create_job_record_dynamo,
    persist_payload_s3,
    send_job_message_sqs,
    update_job_status_dynamo,
)


@patch.dict(os.environ, {
    "JOB_BUCKET_NAME": "test-bucket",
    "JOB_TABLE_NAME": "test-table",
    "JOB_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue.fifo",
})
class TestPersistenceHelpers:
    @patch("aws_clients.boto3.client")
    def test_persist_payload_s3_success(self, mock_boto3_client):
        mock_s3 = Mock()
        mock_boto3_client.return_value = mock_s3

        payload = {"planningType": "network"}

        key = persist_payload_s3("planning-test-123", payload, "planning-input/planning-test-123.json")

        assert key == "planning-input/planning-test-123.json"
        mock_boto3_client.assert_called_once_with("s3")
        mock_s3.put_object.assert_called_once()
        kwargs = mock_s3.put_object.call_args.kwargs
        assert kwargs["Bucket"] == "test-bucket"
        assert kwargs["Key"] == "planning-input/planning-test-123.json"
        assert kwargs["ContentType"] == "application/json"
        assert json.loads(kwargs["Body"].decode("utf-8")) == payload

    @patch("aws_clients.boto3.client")
    def test_persist_payload_s3_client_error(self, mock_boto3_client):
        mock_s3 = Mock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "S3 failure"}},
            "PutObject",
        )

        with pytest.raises(ClientError):
            persist_payload_s3("planning-test-123", {"planningType": "network"}, "planning-input/planning-test-123.json")

    @patch("aws_clients.boto3.resource")
    def test_create_job_record_dynamo_success(self, mock_boto3_resource):
        mock_table = Mock()
        mock_dynamodb = Mock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        item = create_job_record_dynamo(
            "planning-test-123",
            "network",
            "planner@postnl.nl",
            "replan",
            "planning-input/planning-test-123.json",
            "2026-04-10T08:00:00Z",
        )

        mock_boto3_resource.assert_called_once_with("dynamodb")
        mock_dynamodb.Table.assert_called_once_with("test-table")
        mock_table.put_item.assert_called_once()
        saved_item = mock_table.put_item.call_args.kwargs["Item"]
        assert saved_item["jobId"] == "planning-test-123"
        assert saved_item["planningType"] == "network"
        assert saved_item["status"] == "PENDING"
        assert saved_item["payloadS3Key"] == "planning-input/planning-test-123.json"
        assert saved_item["requestedBy"] == "planner@postnl.nl"
        assert saved_item["action"] == "replan"
        assert "requestBody" not in saved_item
        assert item == saved_item

    @patch("aws_clients.boto3.resource")
    def test_create_job_record_dynamo_omits_empty_action(self, mock_boto3_resource):
        mock_table = Mock()
        mock_dynamodb = Mock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        create_job_record_dynamo(
            "planning-test-123",
            "region",
            "planner@postnl.nl",
            None,
            "planning-input/planning-test-123.json",
            "2026-04-10T08:00:00Z",
        )

        saved_item = mock_table.put_item.call_args.kwargs["Item"]
        assert "action" not in saved_item

    @patch("aws_clients.boto3.resource")
    def test_update_job_status_dynamo_success(self, mock_boto3_resource):
        mock_table = Mock()
        mock_dynamodb = Mock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        update_job_status_dynamo("planning-test-123", "FAILED_TO_QUEUE", "2026-04-10T08:00:00Z", "SQS error")

        mock_boto3_resource.assert_called_once_with("dynamodb")
        mock_dynamodb.Table.assert_called_once_with("test-table")
        mock_table.update_item.assert_called_once()
        kwargs = mock_table.update_item.call_args.kwargs
        assert kwargs["Key"] == {"jobId": "planning-test-123"}
        assert kwargs["ExpressionAttributeValues"][":status"] == "FAILED_TO_QUEUE"
        assert kwargs["ExpressionAttributeValues"][":errorMessage"] == "SQS error"

    @patch("aws_clients.boto3.resource")
    def test_update_job_status_dynamo_without_error_message(self, mock_boto3_resource):
        mock_table = Mock()
        mock_dynamodb = Mock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        update_job_status_dynamo("planning-test-123", "PROCESSING", "2026-04-10T08:00:00Z")

        kwargs = mock_table.update_item.call_args.kwargs
        assert ":errorMessage" not in kwargs["ExpressionAttributeValues"]
        assert "errorMessage" not in kwargs["UpdateExpression"]

    @patch("aws_clients.boto3.client")
    def test_send_job_message_sqs_success(self, mock_boto3_client):
        mock_sqs = Mock()
        mock_boto3_client.return_value = mock_sqs

        send_job_message_sqs(
            "planning-test-123",
            "vehicle",
            "planning-input/planning-test-123.json",
        )

        mock_boto3_client.assert_called_once_with("sqs")
        mock_sqs.send_message.assert_called_once()
        kwargs = mock_sqs.send_message.call_args.kwargs
        assert kwargs["QueueUrl"] == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue.fifo"
        assert kwargs["MessageGroupId"] == "planning-vehicle"
        assert kwargs["MessageDeduplicationId"] == "planning-test-123"
        message_body = json.loads(kwargs["MessageBody"])
        assert message_body == {
            "jobId": "planning-test-123",
            "planningType": "vehicle",
            "payloadS3Key": "planning-input/planning-test-123.json",
        }

    @patch.dict(os.environ, {
        "JOB_BUCKET_NAME": "test-bucket",
        "JOB_TABLE_NAME": "test-table",
        "JOB_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue.fifo",
        "JOB_QUEUE_MESSAGE_GROUP_ID": "planning-jobs",
    })
    @patch("aws_clients.boto3.client")
    def test_send_job_message_sqs_uses_configured_message_group_id(self, mock_boto3_client):
        mock_sqs = Mock()
        mock_boto3_client.return_value = mock_sqs

        send_job_message_sqs(
            "planning-test-123",
            "vehicle",
            "planning-input/planning-test-123.json",
        )

        kwargs = mock_sqs.send_message.call_args.kwargs
        assert kwargs["MessageGroupId"] == "planning-jobs"

    @patch("aws_clients.boto3.client")
    def test_send_job_message_sqs_client_error(self, mock_boto3_client):
        mock_sqs = Mock()
        mock_boto3_client.return_value = mock_sqs
        mock_sqs.send_message.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "SQS failure"}},
            "SendMessage",
        )

        with pytest.raises(ClientError):
            send_job_message_sqs(
                "planning-test-123",
                "vehicle",
                "planning-input/planning-test-123.json",
            )
