import json
from datetime import datetime


SUPPORTED_PLANNING_TYPES = {"network", "region", "vehicle", "order"}


def parse_event_body(event):
    """Extract and parse the API Gateway event body.

    API Gateway often provides a text body. Return a JSON object
    or raise ValueError for invalid JSON.
    """
    body = event.get("body")
    if body is None:
        raise ValueError("Request body is required")

    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON in request body") from exc

    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")

    return body


def _require_non_empty_string(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _validate_planning_date(value):
    planning_date = _require_non_empty_string(value, "planningDate")
    try:
        datetime.strptime(planning_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("planningDate must be a valid date in YYYY-MM-DD format") from exc
    return planning_date


def _validate_string_list(values, field_name):
    if not isinstance(values, list) or not values:
        raise ValueError(f"{field_name} must be a non-empty list")
    for item in values:
        _require_non_empty_string(item, f"{field_name} item")
    return values


def _validate_top_level_fields(body):
    common_required = {"requestedBy", "payload"}
    missing = common_required - body.keys()
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")

    _require_non_empty_string(body["requestedBy"], "requestedBy")

    payload = body["payload"]
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")

    action = body.get("action")
    if action is not None:
        _require_non_empty_string(action, "action")

    metadata = body.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError("metadata must be a JSON object")

    return payload


def _validate_network_payload(payload):
    required = {"planningDate", "planningHorizon", "optimizationGoal", "networkId"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"Missing payload fields for network: {', '.join(sorted(missing))}")

    _validate_planning_date(payload["planningDate"])
    _require_non_empty_string(payload["planningHorizon"], "planningHorizon")
    _require_non_empty_string(payload["optimizationGoal"], "optimizationGoal")
    _require_non_empty_string(payload["networkId"], "networkId")


def _validate_region_payload(payload):
    required = {"planningDate", "regionId", "optimizationGoal", "reason"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"Missing payload fields for region: {', '.join(sorted(missing))}")

    _validate_planning_date(payload["planningDate"])
    _require_non_empty_string(payload["regionId"], "regionId")
    _require_non_empty_string(payload["optimizationGoal"], "optimizationGoal")
    _require_non_empty_string(payload["reason"], "reason")


def _validate_vehicle_payload(payload):
    required = {"planningDate", "regionId"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"Missing payload fields for vehicle: {', '.join(sorted(missing))}")

    _validate_planning_date(payload["planningDate"])
    _require_non_empty_string(payload["regionId"], "regionId")

    vehicle_id = payload.get("vehicleId")
    vehicle_ids = payload.get("vehicleIds")
    if vehicle_id is None and vehicle_ids is None:
        raise ValueError("vehicle planning must include vehicleId or vehicleIds")

    if vehicle_id is not None:
        _require_non_empty_string(vehicle_id, "vehicleId")

    if vehicle_ids is not None:
        _validate_string_list(vehicle_ids, "vehicleIds")


def _validate_order_payload(payload):
    required = {"planningDate", "orderId", "regionId", "reason"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"Missing payload fields for order: {', '.join(sorted(missing))}")

    _validate_planning_date(payload["planningDate"])
    _require_non_empty_string(payload["orderId"], "orderId")
    _require_non_empty_string(payload["regionId"], "regionId")
    _require_non_empty_string(payload["reason"], "reason")

    new_constraints = payload.get("newConstraints")
    if new_constraints is not None and not isinstance(new_constraints, dict):
        raise ValueError("newConstraints must be a JSON object")


def validate_payload(body):
    """Validate request payload based on planningType.

    The function checks all required fields and raises ValueError
    with a descriptive message if any check fails.

    Returns a tuple (planning_type, payload) on success.
    """
    # 1. The top-level request must be a JSON object.
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")

    # 2. planningType must be one of the supported values.
    planning_type = body.get("planningType")
    if planning_type not in SUPPORTED_PLANNING_TYPES:
        supported = ", ".join(sorted(SUPPORTED_PLANNING_TYPES))
        raise ValueError(f"planningType must be one of: {supported}")

    # 3. Ensure required top-level fields are present and valid.
    payload = _validate_top_level_fields(body)

    # 4. Validate payload according to the selected planning type.
    if planning_type == "network":
        _validate_network_payload(payload)
    elif planning_type == "region":
        _validate_region_payload(payload)
    elif planning_type == "vehicle":
        _validate_vehicle_payload(payload)
    else:
        _validate_order_payload(payload)

    # 5. Return validated planning type and payload.
    return planning_type, payload
