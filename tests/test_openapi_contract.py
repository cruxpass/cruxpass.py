import json
import os
from pathlib import Path
from unittest import TestCase

SCHEMA_PATH = Path(__file__).parent / "fixtures" / "openapi-schema.json"


CLIENT_METHOD_CONTRACT = [
    ("get_project", "get", "/api/project/"),
    ("update_project", "patch", "/api/project/"),
    ("list_groups", "get", "/api/groups/"),
    ("create_group", "post", "/api/groups/"),
    ("get_group", "get", "/api/groups/{slug}/"),
    ("update_group", "patch", "/api/groups/{slug}/"),
    ("delete_group", "delete", "/api/groups/{slug}/"),
    ("list_feeds", "get", "/api/feeds/"),
    ("create_feed", "post", "/api/feeds/"),
    ("get_feed", "get", "/api/feeds/{slug}/"),
    ("update_feed", "patch", "/api/feeds/{slug}/"),
    ("delete_feed", "delete", "/api/feeds/{slug}/"),
    ("list_events", "get", "/api/feeds/{slug}/events/"),
    ("upsert_event", "post", "/api/feeds/{slug}/events/"),
    ("upsert_recurring_schedule", "post", "/api/feeds/{slug}/recurring-schedules/"),
    (
        "upsert_recurring_exception",
        "post",
        "/api/feeds/{slug}/recurring-schedules/{schedule_external_id}/exceptions/",
    ),
    ("list_subscribers", "get", "/api/subscribers/"),
    ("create_subscriber", "post", "/api/subscribers/"),
    ("get_subscriber", "get", "/api/subscribers/{token}/"),
    ("update_subscriber", "patch", "/api/subscribers/{token}/"),
    ("deactivate_subscriber", "post", "/api/subscribers/{token}/deactivate/"),
    ("rotate_subscriber_token", "post", "/api/subscribers/{token}/rotate-token/"),
    (
        "refresh_subscriber_artifact",
        "post",
        "/api/subscribers/{token}/refresh-artifact/",
    ),
]


class OpenApiContractTests(TestCase):
    def load_schema(self):
        schema_path = Path(os.environ.get("CRUXPASS_OPENAPI_SCHEMA", SCHEMA_PATH))
        with schema_path.open() as handle:
            return json.load(handle)

    def test_named_client_helpers_are_described_by_openapi_schema(self):
        schema = self.load_schema()
        paths = schema["paths"]

        missing = []
        for helper_name, method, path in CLIENT_METHOD_CONTRACT:
            if path not in paths or method not in paths[path]:
                missing.append(f"{helper_name}: {method.upper()} {path}")

        self.assertEqual(missing, [])

    def test_schema_documents_project_api_key_auth(self):
        schema = self.load_schema()

        security_schemes = schema["components"]["securitySchemes"]
        self.assertIn("ProjectApiKey", security_schemes)
        self.assertEqual(security_schemes["ProjectApiKey"]["in"], "header")
        self.assertEqual(security_schemes["ProjectApiKey"]["name"], "Authorization")
        self.assertIn(
            {"ProjectApiKey": []},
            schema["paths"]["/api/feeds/"]["get"]["security"],
        )
