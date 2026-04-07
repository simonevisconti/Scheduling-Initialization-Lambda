import pytest

from validations import parse_event_body, validate_payload


class TestParseEventBody:
    def test_parse_event_body_valid_json_string(self):
        event = {"body": '{"planningType": "network", "requestedBy": "test"}'}
        result = parse_event_body(event)
        assert result == {"planningType": "network", "requestedBy": "test"}

    def test_parse_event_body_already_dict(self):
        event = {"body": {"planningType": "network", "requestedBy": "test"}}
        result = parse_event_body(event)
        assert result == {"planningType": "network", "requestedBy": "test"}

    def test_parse_event_body_missing_body(self):
        event = {}
        with pytest.raises(ValueError, match="Request body is required"):
            parse_event_body(event)

    def test_parse_event_body_invalid_json(self):
        event = {"body": "{invalid json"}
        with pytest.raises(ValueError, match="Invalid JSON in request body"):
            parse_event_body(event)

    def test_parse_event_body_not_dict(self):
        event = {"body": '["not", "a", "dict"]'}
        with pytest.raises(ValueError, match="Request body must be a JSON object"):
            parse_event_body(event)


class TestValidatePayload:
    def test_validate_payload_network_success(self):
        body = {
            "planningType": "network",
            "action": "replan",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-04-10",
                "planningHorizon": "daily",
                "optimizationGoal": "distance",
                "networkId": "nl-main-network",
            },
            "metadata": {"source": "planning-ui"},
        }
        planning_type, payload = validate_payload(body)
        assert planning_type == "network"
        assert payload["networkId"] == "nl-main-network"

    def test_validate_payload_region_success(self):
        body = {
            "planningType": "region",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-04-10",
                "regionId": "utrecht-region",
                "optimizationGoal": "time",
                "reason": "capacity-imbalance",
            }
        }
        planning_type, payload = validate_payload(body)
        assert planning_type == "region"
        assert payload["regionId"] == "utrecht-region"

    def test_validate_payload_vehicle_single_success(self):
        body = {
            "planningType": "vehicle",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-04-10",
                "regionId": "utrecht-region",
                "vehicleId": "VEH-001"
            }
        }
        planning_type, payload = validate_payload(body)
        assert planning_type == "vehicle"
        assert payload["vehicleId"] == "VEH-001"

    def test_validate_payload_vehicle_multiple_success(self):
        body = {
            "planningType": "vehicle",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-04-10",
                "regionId": "zuid-holland-region",
                "vehicleIds": ["VEH-002", "VEH-003"]
            }
        }
        planning_type, payload = validate_payload(body)
        assert planning_type == "vehicle"
        assert payload["vehicleIds"] == ["VEH-002", "VEH-003"]

    def test_validate_payload_order_success(self):
        body = {
            "planningType": "order",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-04-10",
                "orderId": "ORD-1007",
                "regionId": "utrecht-region",
                "reason": "customer-change",
                "newConstraints": {"preferredTimeWindow": "14:00-16:00"},
            }
        }
        planning_type, payload = validate_payload(body)
        assert planning_type == "order"
        assert payload["orderId"] == "ORD-1007"

    def test_validate_payload_invalid_planning_type(self):
        body = {
            "planningType": "invalid",
            "requestedBy": "test@example.com",
            "payload": {}
        }
        with pytest.raises(ValueError, match="planningType must be one of"):
            validate_payload(body)

    def test_validate_payload_missing_requested_by(self):
        body = {
            "planningType": "network",
            "payload": {}
        }
        with pytest.raises(ValueError, match="Missing required fields"):
            validate_payload(body)

    def test_validate_payload_missing_payload(self):
        body = {
            "planningType": "network",
            "requestedBy": "test@example.com"
        }
        with pytest.raises(ValueError, match="Missing required fields"):
            validate_payload(body)

    def test_validate_payload_payload_not_dict(self):
        body = {
            "planningType": "network",
            "requestedBy": "test@example.com",
            "payload": "not a dict"
        }
        with pytest.raises(ValueError, match="payload must be a JSON object"):
            validate_payload(body)

    def test_validate_payload_network_missing_fields(self):
        body = {
            "planningType": "network",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-04-10"
            }
        }
        with pytest.raises(ValueError, match="Missing payload fields for network"):
            validate_payload(body)

    def test_validate_payload_vehicle_missing_vehicle_id(self):
        body = {
            "planningType": "vehicle",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-04-10",
                "regionId": "utrecht-region"
            }
        }
        with pytest.raises(ValueError, match="vehicle planning must include vehicleId or vehicleIds"):
            validate_payload(body)

    def test_validate_payload_invalid_planning_date(self):
        body = {
            "planningType": "network",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-99-99",
                "planningHorizon": "daily",
                "optimizationGoal": "distance",
                "networkId": "nl-main-network",
            }
        }
        with pytest.raises(ValueError, match="planningDate must be a valid date in YYYY-MM-DD format"):
            validate_payload(body)

    def test_validate_payload_empty_requested_by(self):
        body = {
            "planningType": "network",
            "requestedBy": "   ",
            "payload": {
                "planningDate": "2026-04-10",
                "planningHorizon": "daily",
                "optimizationGoal": "distance",
                "networkId": "nl-main-network",
            }
        }
        with pytest.raises(ValueError, match="requestedBy must be a non-empty string"):
            validate_payload(body)

    def test_validate_payload_empty_action(self):
        body = {
            "planningType": "network",
            "action": "   ",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-04-10",
                "planningHorizon": "daily",
                "optimizationGoal": "distance",
                "networkId": "nl-main-network",
            }
        }
        with pytest.raises(ValueError, match="action must be a non-empty string"):
            validate_payload(body)

    def test_validate_payload_vehicle_ids_must_be_non_empty_list(self):
        body = {
            "planningType": "vehicle",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-04-10",
                "regionId": "utrecht-region",
                "vehicleIds": [],
            }
        }
        with pytest.raises(ValueError, match="vehicleIds must be a non-empty list"):
            validate_payload(body)

    def test_validate_payload_vehicle_id_must_be_non_empty_string(self):
        body = {
            "planningType": "vehicle",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-04-10",
                "regionId": "utrecht-region",
                "vehicleId": "   ",
            }
        }
        with pytest.raises(ValueError, match="vehicleId must be a non-empty string"):
            validate_payload(body)

    def test_validate_payload_vehicle_ids_items_must_be_non_empty_strings(self):
        body = {
            "planningType": "vehicle",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-04-10",
                "regionId": "utrecht-region",
                "vehicleIds": ["VEH-001", "   "],
            }
        }
        with pytest.raises(ValueError, match="vehicleIds item must be a non-empty string"):
            validate_payload(body)

    def test_validate_payload_metadata_must_be_object(self):
        body = {
            "planningType": "network",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-04-10",
                "planningHorizon": "daily",
                "optimizationGoal": "distance",
                "networkId": "nl-main-network",
            },
            "metadata": "not-an-object",
        }
        with pytest.raises(ValueError, match="metadata must be a JSON object"):
            validate_payload(body)

    def test_validate_payload_metadata_can_be_empty_object(self):
        body = {
            "planningType": "network",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-04-10",
                "planningHorizon": "daily",
                "optimizationGoal": "distance",
                "networkId": "nl-main-network",
            },
            "metadata": {},
        }
        planning_type, payload = validate_payload(body)
        assert planning_type == "network"
        assert payload["networkId"] == "nl-main-network"

    def test_validate_payload_order_new_constraints_must_be_object(self):
        body = {
            "planningType": "order",
            "requestedBy": "test@example.com",
            "payload": {
                "planningDate": "2026-04-10",
                "orderId": "ORD-1007",
                "regionId": "utrecht-region",
                "reason": "customer-change",
                "newConstraints": "high-priority",
            }
        }
        with pytest.raises(ValueError, match="newConstraints must be a JSON object"):
            validate_payload(body)
