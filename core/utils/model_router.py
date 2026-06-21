from __future__ import annotations

import os
from dataclasses import dataclass

from openai import OpenAI

from core.utils.config_utils import load_key


@dataclass
class APIConfig:
    role: str
    key: str
    base_url: str
    model: str
    llm_support_json: bool
    temperature: float | None = None
    max_tokens: int | None = None
    timeout: int = 300


def normalize_base_url(base_url):
    base_url = str(base_url or "").strip()
    if "ark" in base_url:
        return "https://ark.cn-beijing.volces.com/api/v3"
    if "v1" not in base_url:
        return base_url.strip("/") + "/v1"
    return base_url

def drop_invalid_ca_bundle_env():
    for env_key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        ca_path = os.environ.get(env_key)
        if ca_path and not os.path.exists(ca_path):
            os.environ.pop(env_key, None)


class ModelRouter:
    """Route calls to workflow or translator model profiles."""

    def load_config(self, api_role="workflow"):
        prefix = "translator_api" if api_role == "translator" else "api"
        config = APIConfig(
            role=api_role,
            key=load_key(f"{prefix}.key"),
            base_url=normalize_base_url(load_key(f"{prefix}.base_url")),
            model=load_key(f"{prefix}.model"),
            llm_support_json=bool(load_key(f"{prefix}.llm_support_json")),
            timeout=600 if api_role == "translator" else 300,
        )
        if api_role == "translator":
            try:
                config.temperature = float(load_key("translator_api.temperature"))
            except (KeyError, TypeError, ValueError):
                pass
            try:
                config.max_tokens = int(load_key("translator_api.max_tokens"))
            except (KeyError, TypeError, ValueError):
                pass
        return config

    def client(self, api_role="workflow"):
        config = self.load_config(api_role)
        if not config.key:
            raise ValueError("API key is not set")
        drop_invalid_ca_bundle_env()
        return OpenAI(api_key=config.key, base_url=config.base_url), config

    def list_available_models(self, api_role="workflow"):
        client, _ = self.client(api_role)
        try:
            models = client.models.list()
            return sorted(model.id for model in models.data)
        finally:
            client.close()

    def chat_completion(self, messages, resp_type=None, api_role="workflow"):
        client, config = self.client(api_role)
        try:
            response_format = {"type": "json_object"} if resp_type == "json" and config.llm_support_json else None
            params = dict(
                model=config.model,
                messages=messages,
                response_format=response_format,
                timeout=config.timeout,
            )
            if config.temperature is not None:
                params["temperature"] = config.temperature
            if config.max_tokens is not None:
                params["max_tokens"] = config.max_tokens
            return client.chat.completions.create(**params), config
        finally:
            client.close()


router = ModelRouter()
