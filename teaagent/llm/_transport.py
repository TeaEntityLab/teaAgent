from __future__ import annotations

import json
from typing import Any
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from teaagent.llm._types import LLMHTTPError


class UrllibHTTPTransport:
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        *,
        timeout: int,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode('utf-8')
        req = urllib_request.Request(
            url,
            data=body,
            headers={
                'content-type': 'application/json',
                'user-agent': 'TeaAgent',
                **headers,
            },
            method='POST',
        )
        try:
            with urllib_request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            raise LLMHTTPError(
                f'HTTP {exc.code}: {detail}', status_code=exc.code
            ) from exc
        except URLError as exc:
            raise LLMHTTPError(f'HTTP request failed: {exc.reason}') from exc
