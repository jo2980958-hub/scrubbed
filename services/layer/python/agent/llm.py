"""Shared Bedrock `converse` helper for the agents."""
from __future__ import annotations

import boto3

from common import config

_client = None


def client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=config.REGION)
    return _client


def set_client(c) -> None:
    global _client
    _client = c


def converse_tool(model_id: str, system: str, content: list, tool: dict, max_tokens: int = 1024,
                  temperature: float = 0.0) -> dict:
    """Force a single tool call so the model must return an object matching the
    tool's schema. Returns the tool input dict."""
    r = client().converse(
        modelId=model_id,
        system=[{"text": system}],
        messages=[{"role": "user", "content": content}],
        toolConfig={"tools": [tool], "toolChoice": {"tool": {"name": tool["toolSpec"]["name"]}}},
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    for block in r["output"]["message"]["content"]:
        if "toolUse" in block:
            return block["toolUse"]["input"]
    raise ValueError(f"no tool call from {model_id}; stopReason={r.get('stopReason')}")


def converse_text(model_id: str, system: str, user: str, max_tokens: int = 900,
                  temperature: float = 0.3) -> str:
    r = client().converse(
        modelId=model_id,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    return "".join(b.get("text", "") for b in r["output"]["message"]["content"]).strip()
