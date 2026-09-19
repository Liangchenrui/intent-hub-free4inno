"""Management probes use the same HTTP environment policy as routing clients."""
import requests as _requests
from requests import RequestException

from intent_hub.config import Config


def _request(method, url, **kwargs):
    with _requests.Session() as session:
        session.trust_env = Config.SERVICE_HTTP_TRUST_ENV
        return session.request(method, url, **kwargs)


def get(url, **kwargs):
    return _request('GET', url, **kwargs)


def post(url, **kwargs):
    return _request('POST', url, **kwargs)
