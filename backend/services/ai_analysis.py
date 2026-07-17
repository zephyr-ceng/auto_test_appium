import json
import os
from collections.abc import AsyncIterator
from collections.abc import Iterator
from typing import Any

import requests

from backend.config import AI_DEFAULT_PROVIDER, AI_PROVIDERS
from backend.services.fenbi_client import FenbiError


def available_ai_providers() -> list[dict[str, Any]]:
    providers = []
    for provider_id, config in AI_PROVIDERS.items():
        api_key = _provider_api_key(config)
        providers.append(
            {
                "id": provider_id,
                "name": config["name"],
                "model": config["model"],
                "configured": bool(api_key),
                "default": provider_id == AI_DEFAULT_PROVIDER,
            }
        )
    return providers


async def stream_report_analysis(report: dict[str, Any], provider: str = AI_DEFAULT_PROVIDER) -> AsyncIterator[str]:
    config = _provider_config(provider)
    api_key = _provider_api_key(config)
    if not api_key:
        yield _sse_data(
            {
                "content": _local_summary(report, config["name"]),
                "provider": provider,
                "local": True,
            }
        )
        yield "data: [DONE]\n\n"
        return

    messages = [
        {
            "role": "system",
            "content": "你是公务员行测错题分析助手。请基于错题、知识点掌握度和练习历史，输出简洁、具体、可执行的复盘建议。",
        },
        {"role": "user", "content": _build_analysis_prompt(report)},
    ]

    if config.get("wire_api") == "responses":
        async for chunk in _stream_responses(config, api_key, messages, provider):
            yield chunk
        return

    async for chunk in _stream_chat_completions(config, api_key, messages, provider):
        yield chunk


async def _stream_chat_completions(
    config: dict[str, Any],
    api_key: str,
    messages: list[dict[str, str]],
    provider: str,
) -> AsyncIterator[str]:
    payload = {
        "model": config["model"],
        "stream": True,
        "temperature": 0.3,
        "messages": messages,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with requests.post(
            f"{config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=60,
        ) as response:
            response.raise_for_status()
            for line in _iter_utf8_lines(response):
                if line:
                    yield f"{line}\n\n"
    except requests.RequestException as exc:
        raise FenbiError("AI 服务调用失败。", 502, {"provider": provider, "wire_api": "chat_completions", "error": str(exc)}) from exc


async def _stream_responses(
    config: dict[str, Any],
    api_key: str,
    messages: list[dict[str, str]],
    provider: str,
) -> AsyncIterator[str]:
    payload = {
        "model": config["model"],
        "stream": True,
        "temperature": 0.3,
        "input": messages,
    }
    if "store" in config:
        payload["store"] = config["store"]
    if config.get("reasoning_effort"):
        payload["reasoning"] = {"effort": config["reasoning_effort"]}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with requests.post(
            f"{config['base_url']}/responses",
            headers=headers,
            json=payload,
            stream=True,
            timeout=60,
        ) as response:
            response.raise_for_status()
            for line in _iter_utf8_lines(response):
                if not line:
                    continue
                if not line.startswith("data: "):
                    continue
                raw = line.removeprefix("data: ").strip()
                if raw == "[DONE]":
                    yield "data: [DONE]\n\n"
                    continue
                content = _extract_responses_text(raw)
                if content:
                    yield _sse_data({"content": content, "provider": provider})
    except requests.RequestException as exc:
        raise FenbiError("AI 服务调用失败。", 502, {"provider": provider, "wire_api": "responses", "error": str(exc)}) from exc


def _iter_utf8_lines(response: requests.Response) -> Iterator[str]:
    for line in response.iter_lines(decode_unicode=False):
        if isinstance(line, bytes):
            yield line.decode("utf-8", errors="replace")
        else:
            yield line


def _extract_responses_text(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ""

    event_type = payload.get("type")
    if event_type in {"response.output_text.delta", "response.refusal.delta"}:
        return str(payload.get("delta") or "")
    if event_type is None:
        return _response_output_text(payload)
    return ""


def _response_output_text(response: dict[str, Any]) -> str:
    chunks = []
    for item in response.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(str(content["text"]))
    return "".join(chunks)


def _provider_config(provider: str) -> dict[str, Any]:
    if provider not in AI_PROVIDERS:
        raise FenbiError("不支持的 AI 服务商。", 400, {"provider": provider})
    return AI_PROVIDERS[provider]


def _provider_api_key(config: dict[str, Any]) -> str:
    return os.getenv(config["api_key_env"], "").strip() or config.get("fallback_api_key", "").strip()


def _sse_data(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _build_analysis_prompt(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    keypoints = report.get("keypoints", [])
    errors = report.get("errors", [])
    history_items = report.get("history", {}).get("items", [])[:10]
    compact = {
        "summary": {
            "quiz": summary.get("quiz", {}),
            "answerCount": summary.get("answerCount"),
            "correctCount": summary.get("correctCount"),
            "forecastScore": summary.get("forecastScore"),
            "avgForecastScore": summary.get("avgForecastScore"),
            "exerciseCount": summary.get("exerciseCount"),
            "exerciseDay": summary.get("exerciseDay"),
        },
        "weakKeypoints": _weak_keypoints(keypoints),
        "topErrorNodes": _top_error_nodes(errors),
        "recentHistory": [
            {
                "sheetName": item.get("sheetName"),
                "updatedTime": item.get("updatedTime"),
                "questionCount": item.get("questionCount"),
                "correctCount": item.get("correctCount"),
                "difficulty": item.get("difficulty"),
                "status": item.get("status"),
            }
            for item in history_items
        ],
    }
    return (
        "请分析以下行测学习数据，重点围绕当前错题给出结论。\n"
        "请直接使用 Markdown 正文输出，包含二级标题、项目列表和必要的加粗重点；不要把全文包在 ```markdown 代码块中。\n"
        "输出结构：1. 当前主要薄弱点；2. 错因推测；3. 未来 7 天复习安排；4. 刷题优先级。\n"
        f"{json.dumps(compact, ensure_ascii=False)}"
    )


def _weak_keypoints(keypoints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []

    def walk(items: list[dict[str, Any]], path: list[str]) -> None:
        for item in items:
            name = item.get("name", "")
            current_path = [*path, name] if name else path
            answer_count = int(item.get("answerCount") or 0)
            if answer_count:
                flattened.append(
                    {
                        "name": " / ".join(current_path),
                        "answerCount": answer_count,
                        "correctRatio": item.get("correctRatio"),
                        "targetCorrectRatio": item.get("targetCorrectRatio"),
                    }
                )
            children = item.get("keypoints")
            if isinstance(children, list):
                walk(children, current_path)

    walk(keypoints, [])
    return sorted(flattened, key=lambda item: (item.get("correctRatio") or 0, -(item["answerCount"])))[:20]


def _top_error_nodes(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []

    def count_questions(node: dict[str, Any]) -> int:
        own = len(node.get("questionIds") or [])
        children = node.get("children") or []
        return own + sum(count_questions(child) for child in children if isinstance(child, dict))

    def walk(items: list[dict[str, Any]], path: list[str]) -> None:
        for item in items:
            name = item.get("name", "")
            current_path = [*path, name] if name else path
            total = count_questions(item)
            if total:
                nodes.append({"name": " / ".join(current_path), "wrongCount": total})
            children = item.get("children")
            if isinstance(children, list):
                walk(children, current_path)

    walk(errors, [])
    return sorted(nodes, key=lambda item: item["wrongCount"], reverse=True)[:20]


def _local_summary(report: dict[str, Any], provider_name: str) -> str:
    summary = report.get("summary", {})
    errors = report.get("errors", [])
    top_errors = _top_error_nodes(errors)[:5]
    error_items = "\n".join(f"- **{item['name']}**：{item['wrongCount']} 题" for item in top_errors) or "- 暂无错题节点"
    return (
        "## 本地摘要\n\n"
        f"{provider_name} 未配置 API Key，当前返回本地摘要。\n\n"
        "## 当前概况\n\n"
        f"- 预测分：**{summary.get('forecastScore', '--')}**\n"
        f"- 累计练习：**{summary.get('exerciseCount', '--')}** 套\n\n"
        "## 错题集中点\n\n"
        f"{error_items}\n\n"
        "## 建议\n\n"
        "- 先按错题数量从高到低复盘。\n"
        "- 再补做对应知识点，优先处理高频错误节点。"
    )
