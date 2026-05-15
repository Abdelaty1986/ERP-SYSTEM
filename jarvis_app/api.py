from flask import Blueprint, jsonify

from providers.erp_provider import build_erp_provider_status


def _base_status():
    return {
        "system": "JARVIS CORE",
        "mode": "independent_runtime_foundation",
        "phase": "Phase 20 - JARVIS Independence Extraction Layer",
        "bounded": True,
        "autonomous_apply": False,
        "deploy": False,
        "destructive_execution": False,
        "database_mutation": False,
        "file_deletion": False,
        "dangerous_migration": False,
        "governance_gates_preserved": True,
        "human_approval_required": True,
    }


def create_jarvis_blueprint():
    blueprint = Blueprint("jarvis_independent_api", __name__)

    @blueprint.get("/jarvis/api/status")
    def jarvis_api_status():
        status = _base_status()
        status.update({
            "state": "operational",
            "erp_role": "connected_provider_read_only",
            "mobile_backend": "compatible_with_existing_routes",
        })
        return jsonify(status)

    @blueprint.get("/jarvis/api/runtime/status")
    def jarvis_runtime_status():
        status = _base_status()
        status.update({
            "runtime_state": "read_only_status_foundation",
            "runtime_memory_readable": True,
            "execution_locked_without_approval": True,
            "apply_allowed": False,
        })
        return jsonify(status)

    @blueprint.get("/jarvis/api/agents/status")
    def jarvis_agents_status():
        status = _base_status()
        status.update({
            "agents_state": "available_via_existing_runtime_memory",
            "routing_mode": "governed",
            "provider_mutation_allowed": False,
        })
        return jsonify(status)

    @blueprint.get("/jarvis/api/mobile/status")
    def jarvis_mobile_status():
        status = _base_status()
        status.update({
            "mobile_state": "pwa_and_legacy_routes_preserved",
            "legacy_mobile_route": "/jarvis/mobile",
            "legacy_status_route": "/jarvis/mobile/api/status",
            "independent_status_route": "/jarvis/api/mobile/status",
        })
        return jsonify(status)

    @blueprint.get("/jarvis/api/voice/status")
    def jarvis_voice_status():
        status = _base_status()
        status.update({
            "voice_state": "available_through_existing_voice_runtime",
            "legacy_voice_route": "/jarvis/mobile/api/voice/command",
            "voice_commands_bypass_governance": False,
        })
        return jsonify(status)

    @blueprint.get("/jarvis/api/providers/erp/status")
    def jarvis_erp_provider_status():
        return jsonify(build_erp_provider_status())

    return blueprint
