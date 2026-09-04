"""Health endpoints."""

from flask import jsonify

from intent_hub.services.health_service import check_external_services
from intent_hub.utils.error_handler import handle_errors


@handle_errors
def get_service_health():
    return jsonify(check_external_services()), 200
