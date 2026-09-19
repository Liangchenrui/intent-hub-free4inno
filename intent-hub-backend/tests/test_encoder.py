from intent_hub.encoder import QwenEmbeddingEncoder


def test_embedding_endpoint_uses_configured_url_verbatim(monkeypatch):
    monkeypatch.setattr(QwenEmbeddingEncoder, "encode_single", lambda self, text: [1., 0.])
    endpoint = "http://embedding.free4inno.com/embed"

    encoder = QwenEmbeddingEncoder(endpoint, api_format="tei")

    assert encoder.endpoint_url == endpoint


def test_encode_uses_text_embeddings_inference_contract(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return [[1.0, 2.0], [3.0, 4.0]]

    def post(self, url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr("intent_hub.encoder.httpx.Client.post", post)
    encoder = QwenEmbeddingEncoder("http://embedding.free4inno.com/embed", api_format="tei")
    calls.clear()

    assert encoder.encode(["first", "second"]) == [[1.0, 2.0], [3.0, 4.0]]
    assert calls == [
        (
            "http://embedding.free4inno.com/embed",
            {"json": {"inputs": ["first", "second"]}, "timeout": 30},
        )
    ]
