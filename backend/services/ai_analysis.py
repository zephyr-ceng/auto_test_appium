import json
from collections.abc import AsyncIterator
from typing import Any

import requests

from backend.config import AI_API_KEY, AI_BASE_URL, AI_MODEL


async def stream_report_analysis(report: dict[str, Any]) -> AsyncIterator[str]:
    """Stream AI analysis as Server-Sent Events.

    If AI_API_KEY is not configured, return a deterministic local summary so
    the report page can still offer an analysis endpoint during local testing.
    """
    if not AI_API_KEY:
        summary = report.get("summary", {})
        text = (
            f"当前预测分 {summary.get('forecastScore', '--')}，"
            f"答题正确率 {summary.get('accuracy', 0):.1f}%，"
            f"累计练习 {summary.get('exerciseCount', '--')} 套。"
            "建议优先复盘低正确率知识点，并保持稳定练习频率。"
        )
        yield f"data: {json.dumps({'content': text}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    payload = {
        "model": AI_MODEL,
        "stream": True,
        "messages": [
            {
                "role": "system",
                "content": "你是公务员行测学习报告分析助手，回答要简洁、具体、可执行。",
            },
            {"role": "user", "content": json.dumps(report, ensure_ascii=False)[:12000]},
        ],
    }
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }

    with requests.post(
        f"{AI_BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        stream=True,
        timeout=60,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if line:
                yield f"{line}\n\n"
