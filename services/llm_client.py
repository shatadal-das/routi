"""
RoamAround / Routi - LLM Client Interface

Configured for AWS Bedrock OpenAI-compatible endpoint using the official OpenAI Python SDK.
Default Model: google.gemma-3-27b-it
Region: ap-south-1 (Mumbai) or configured in .env
Cost-saving Service Tier: flex (saves inferencing cost on AWS Bedrock)

Reads credentials from .env:
  - OPENAI_API_KEY: AWS Bedrock API key
  - OPENAI_BASE_URL: AWS Bedrock endpoint URL (e.g. https://bedrock-runtime.ap-south-1.amazonaws.com/openai/v1)
  - OPENAI_SERVICE_TIER: flex
"""

import os
import json
import re
from typing import Optional, Any, Dict, List
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_MODEL = "google.gemma-3-27b-it"
DEFAULT_SERVICE_TIER = os.getenv("OPENAI_SERVICE_TIER", "flex")


def normalize_base_url(url: Optional[str]) -> Optional[str]:
    """
    Normalizes AWS Bedrock endpoint URLs.
    If the user provides 'https://bedrock-runtime.ap-south-1.amazonaws.com',
    automatically appends '/openai/v1' as required by Amazon Bedrock's OpenAI compatibility layer.
    """
    if not url or not url.strip():
        return None

    cleaned = url.strip().rstrip("/")
    if "bedrock-runtime" in cleaned and not (cleaned.endswith("/openai/v1") or cleaned.endswith("/v1")):
        cleaned = f"{cleaned}/openai/v1"
    elif "bedrock-mantle" in cleaned and not cleaned.endswith("/v1"):
        cleaned = f"{cleaned}/v1"

    return cleaned


def get_openai_client() -> Optional[OpenAI]:
    """
    Initializes and returns an OpenAI client configured with OPENAI_API_KEY
    and OPENAI_BASE_URL (for AWS Bedrock or custom endpoints).
    Returns None if OPENAI_API_KEY is not configured.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        return None

    raw_base_url = os.getenv("OPENAI_BASE_URL")
    normalized_url = normalize_base_url(raw_base_url)

    if normalized_url:
        return OpenAI(api_key=api_key.strip(), base_url=normalized_url)

    return OpenAI(api_key=api_key.strip())


def extract_response_text(response: Any) -> str:
    """
    Safely extracts string content from an OpenAI SDK response object,
    supporting both client.chat.completions.create and client.responses.create.
    """
    if response is None:
        return ""

    # 1. Standard chat completions choices
    if hasattr(response, "choices") and response.choices:
        first_choice = response.choices[0]
        if hasattr(first_choice, "message"):
            msg = first_choice.message
            if hasattr(msg, "content") and msg.content:
                return str(msg.content).strip()

    # 2. Convenience property on Response (Responses API)
    if hasattr(response, "output_text") and response.output_text:
        return str(response.output_text).strip()

    # 3. Inspect output list if present
    if hasattr(response, "output") and response.output:
        parts: List[str] = []
        for item in response.output:
            if getattr(item, "type", None) == "message":
                for content in getattr(item, "content", []):
                    if getattr(content, "type", None) == "output_text" and getattr(content, "text", None):
                        parts.append(str(content.text))
                    elif hasattr(content, "text") and content.text:
                        parts.append(str(content.text))
            elif hasattr(item, "text") and item.text:
                parts.append(str(item.text))
        if parts:
            return "".join(parts).strip()

    return str(response).strip()


def call_llm(
    prompt: str,
    model: str = DEFAULT_MODEL,
    client: Optional[OpenAI] = None,
    system_instruction: Optional[str] = None,
    service_tier: Optional[str] = None
) -> str:
    """
    Invokes the LLM using AWS Bedrock OpenAI compatibility layer.
    Uses cost-saving service tier ('flex') by default.
    Supports chat.completions and responses API with automatic fallback.
    """
    if client is None:
        client = get_openai_client()

    if client is None:
        raise RuntimeError("OPENAI_API_KEY is not set in environment or .env file.")

    tier = service_tier or DEFAULT_SERVICE_TIER

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    # Method 1: Chat Completions API (Officially supported by Bedrock for Gemma 3)
    try:
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if tier and tier != "default":
            kwargs["service_tier"] = tier

        chat_resp = client.chat.completions.create(**kwargs)
        return extract_response_text(chat_resp)
    except Exception as e:
        err_str = str(e).lower()
        # If service_tier=flex is rejected by any specific endpoint, retry without service_tier
        if "service_tier" in err_str or "tier" in err_str:
            try:
                chat_resp = client.chat.completions.create(model=model, messages=messages)
                return extract_response_text(chat_resp)
            except Exception:
                pass

        # Method 2: Responses API fallback
        try:
            resp_kwargs: Dict[str, Any] = {
                "model": model,
                "input": messages
            }
            if tier and tier != "default":
                resp_kwargs["service_tier"] = tier

            response = client.responses.create(**resp_kwargs)
            return extract_response_text(response)
        except Exception:
            raise e


def extract_json_from_text(text: str) -> Any:
    """
    Strips markdown code blocks, cleans up formatting, and parses JSON.
    """
    if not text:
        raise ValueError("Empty response text received from LLM.")

    cleaned = text.strip()
    # Strip markdown block wrappers if present (e.g. ```json ... ```)
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    # Sometimes models wrap JSON with leading/trailing commentary; find first [ or { and last ] or }
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        json_match = re.search(r"(\[.*\]|\{.*\})", cleaned, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        raise


def call_llm_json(
    prompt: str,
    model: str = DEFAULT_MODEL,
    client: Optional[OpenAI] = None,
    system_instruction: Optional[str] = None,
    service_tier: Optional[str] = None
) -> Any:
    """
    Calls the LLM and parses the response into JSON (dict or list).
    """
    raw_text = call_llm(
        prompt=prompt,
        model=model,
        client=client,
        system_instruction=system_instruction,
        service_tier=service_tier
    )
    return extract_json_from_text(raw_text)
