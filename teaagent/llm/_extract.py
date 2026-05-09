from __future__ import annotations

from typing import Any

from teaagent.llm._types import LLMProviderError, LLMResponseFormatError


def _extract_openai_content(provider: str, response: dict[str, Any]) -> str:
    _raise_provider_error(provider, response)
    choices = response.get('choices')
    if not isinstance(choices, list) or not choices:
        raise LLMResponseFormatError(f'{provider} response missing choices')
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise LLMResponseFormatError(f'{provider} response choice is not an object')
    message = first_choice.get('message')
    if not isinstance(message, dict):
        raise LLMResponseFormatError(f'{provider} response missing message')
    content = message.get('content')
    if not isinstance(content, str) or not content:
        raise LLMResponseFormatError(f'{provider} response missing text content')
    return content


def _first_choice_delta(provider: str, response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get('choices')
    if not isinstance(choices, list) or not choices:
        raise LLMResponseFormatError(f'{provider} stream chunk missing choices')
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise LLMResponseFormatError(f'{provider} stream choice is not an object')
    delta = first_choice.get('delta', {})
    if not isinstance(delta, dict):
        raise LLMResponseFormatError(f'{provider} stream delta is not an object')
    return delta


def _extract_claude_content(response: dict[str, Any]) -> str:
    _raise_provider_error('claude', response)
    content_blocks = response.get('content')
    if not isinstance(content_blocks, list):
        raise LLMResponseFormatError('claude response missing content blocks')
    text_parts = [
        block.get('text', '')
        for block in content_blocks
        if isinstance(block, dict) and block.get('type') == 'text'
    ]
    content = ''.join(part for part in text_parts if isinstance(part, str))
    if not content:
        raise LLMResponseFormatError('claude response missing text content')
    return content


def _extract_gemini_content(response: dict[str, Any]) -> str:
    _raise_provider_error('gemini', response)
    candidates = response.get('candidates')
    if not isinstance(candidates, list) or not candidates:
        raise LLMResponseFormatError('gemini response missing candidates')
    first_candidate = candidates[0]
    if not isinstance(first_candidate, dict):
        raise LLMResponseFormatError('gemini candidate is not an object')
    content = first_candidate.get('content')
    if not isinstance(content, dict):
        raise LLMResponseFormatError('gemini response missing content')
    parts = content.get('parts')
    if not isinstance(parts, list):
        raise LLMResponseFormatError('gemini response missing parts')
    text = ''.join(
        part.get('text', '')
        for part in parts
        if isinstance(part, dict) and isinstance(part.get('text'), str)
    )
    if not text:
        raise LLMResponseFormatError('gemini response missing text content')
    return text


def _raise_provider_error(provider: str, response: dict[str, Any]) -> None:
    error = response.get('error')
    if isinstance(error, dict):
        message = error.get('message') or error.get('status') or error
        raise LLMProviderError(f'{provider} provider error: {message}')
    if isinstance(error, str):
        raise LLMProviderError(f'{provider} provider error: {error}')
    prompt_feedback = response.get('promptFeedback')
    if isinstance(prompt_feedback, dict) and prompt_feedback.get('blockReason'):
        raise LLMProviderError(
            f'{provider} provider blocked prompt: {prompt_feedback["blockReason"]}'
        )
