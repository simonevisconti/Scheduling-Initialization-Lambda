from unittest.mock import patch

import pytest

from service import current_timestamp, s3_key_for_job, start_planning_job, ttl_timestamp


class TestServiceHelpers:
    def test_s3_key_for_job(self):
        assert s3_key_for_job("planning-test-123") == "planning-input/planning-test-123.json"

    def test_current_timestamp_uses_utc_suffix(self):
        assert current_timestamp().endswith("Z")

    def test_ttl_timestamp_returns_unix_seconds_in_future(self):
        assert ttl_timestamp() > 0


@patch("service.send_job_message_sqs")
@patch("service.update_job_status_dynamo")
@patch("service.create_job_record_dynamo")
@patch("service.persist_payload_s3")
@patch("service.ttl_timestamp", return_value=1796457600)
@patch("service.current_timestamp", side_effect=["2026-04-10T08:00:00Z", "2026-04-10T08:05:00Z"])
@patch("service.generate_job_id", return_value="planning-test-123")
class TestStartPlanningJob:
    def test_start_planning_job_success(
        self,
        mock_generate_job_id,
        mock_current_timestamp,
        mock_ttl_timestamp,
        mock_persist_payload_s3,
        mock_create_job_record_dynamo,
        mock_update_job_status_dynamo,
        mock_send_job_message_sqs,
    ):
        mock_create_job_record_dynamo.return_value = {"status": "PENDING"}
        body = {
            "planningType": "network",
            "requestedBy": "test@example.com",
            "action": "replan",
            "payload": {"planningDate": "2026-04-10"},
        }

        result = start_planning_job(body, "network")

        assert result == {
            "jobId": "planning-test-123",
            "planningType": "network",
            "state": "PENDING",
        }
        mock_persist_payload_s3.assert_called_once_with(
            "planning-test-123",
            body,
            "planning-input/planning-test-123.json",
        )
        mock_create_job_record_dynamo.assert_called_once_with(
            "planning-test-123",
            "network",
            "test@example.com",
            "replan",
            "planning-input/planning-test-123.json",
            "2026-04-10T08:00:00Z",
            1796457600,
        )
        mock_send_job_message_sqs.assert_called_once_with(
            "planning-test-123",
            "network",
            "planning-input/planning-test-123.json",
        )
        mock_update_job_status_dynamo.assert_not_called()

    def test_start_planning_job_marks_job_failed_to_queue(
        self,
        mock_generate_job_id,
        mock_current_timestamp,
        mock_ttl_timestamp,
        mock_persist_payload_s3,
        mock_create_job_record_dynamo,
        mock_update_job_status_dynamo,
        mock_send_job_message_sqs,
    ):
        mock_create_job_record_dynamo.return_value = {"status": "PENDING"}
        mock_send_job_message_sqs.side_effect = Exception("SQS error")
        body = {
            "planningType": "network",
            "requestedBy": "test@example.com",
            "payload": {"planningDate": "2026-04-10"},
        }

        with pytest.raises(Exception, match="SQS error"):
            start_planning_job(body, "network")

        mock_update_job_status_dynamo.assert_called_once_with(
            "planning-test-123",
            "FAILED_TO_QUEUE",
            "2026-04-10T08:05:00Z",
            "SQS error",
        )
