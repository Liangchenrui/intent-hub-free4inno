from types import SimpleNamespace

from intent_hub_cli import IntentHubClient


class DummySession:
    def __init__(self):
        self.calls = []

    def request(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"ok": True, "path": kwargs["url"]},
        )


def test_route_uses_bearer_auth_and_expected_path():
    session = DummySession()
    client = IntentHubClient("https://api.example.com/", "ih_live_test", session=session)

    payload = client.route("整理 wiki")

    assert payload["ok"] is True
    assert session.calls[0]["url"] == "https://api.example.com/v1/route"
    assert session.calls[0]["headers"]["Authorization"] == "Bearer ih_live_test"
    assert session.calls[0]["json"] == {"text": "整理 wiki"}


def test_skills_apply_posts_expected_payload():
    session = DummySession()
    client = IntentHubClient("https://api.example.com", "ih_live_test", session=session)

    client.skills_apply("draft.json")

    assert session.calls[0]["url"] == "https://api.example.com/tenant/skill-drafts/apply"
    assert session.calls[0]["json"] == {"draft_file": "draft.json"}


def test_skills_scan_uploaded_posts_expected_payload():
    session = DummySession()
    client = IntentHubClient("https://api.example.com", "ih_live_test", session=session)

    client.skills_scan_uploaded(
        source_id="src_001",
        source_label="My Local Skills",
        client_path_hint="D:/skills",
        skills=[
            {
                "skill_name": "wiki_builder",
                "relative_path": "wiki_builder/SKILL.md",
                "content": "# Wiki Builder\nbuild wiki",
            }
        ],
    )

    assert session.calls[0]["url"] == "https://api.example.com/tenant/skill-sources/scan"
    assert session.calls[0]["json"]["source_id"] == "src_001"
    assert session.calls[0]["json"]["source_label"] == "My Local Skills"
    assert session.calls[0]["json"]["skills"][0]["relative_path"] == "wiki_builder/SKILL.md"
