"""Azure OpenAI chat model factory.

A single shared `AzureChatOpenAI` is constructed per pipeline run; all
analysis nodes reuse it so prompt caching can amortise the system prompt
across calls.
"""

from __future__ import annotations

from langchain_openai import AzureChatOpenAI

from src.config import AzureOpenAISettings, LLMSettings


def build_chat_model(azure: AzureOpenAISettings, llm: LLMSettings) -> AzureChatOpenAI:
    return AzureChatOpenAI(
        api_key=azure.api_key,
        azure_endpoint=azure.endpoint,
        azure_deployment=azure.deployment,
        api_version=azure.api_version,
        temperature=llm.temperature,
        max_retries=2,
    )
