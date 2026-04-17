from intent_hub_cli import IntentHubClient

client = IntentHubClient(
    endpoint="http://127.0.0.1:5000",
    access_code="ih_live_1_5369278694ca9ac55f140d05",
)

print(client.whoami())
print(client.route("帮我整理 wiki"))
print(client.dispatch("帮我整理 wiki"))
