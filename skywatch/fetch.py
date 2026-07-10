"""HTTP fetch layer: one function, explicit timeout, errors mapped to FetchError.

Everything upstream-facing goes through http_get_json so tests can inject a
fake with the same signature (see docs/specs/sources.md).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from skywatch import __version__

DEFAULT_TIMEOUT = 10.0


class FetchError(Exception):
    """Network, HTTP-status, or JSON-decoding failure talking to an upstream."""


def http_get_json(url: str, timeout: float = DEFAULT_TIMEOUT) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"skywatch/{__version__}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as err:
        raise FetchError(f"HTTP {err.code} from {url}") from err
    except TimeoutError as err:
        raise FetchError(f"timed out after {timeout:g}s: {url}") from err
    except urllib.error.URLError as err:
        reason = err.reason
        if isinstance(reason, TimeoutError):
            raise FetchError(f"timed out after {timeout:g}s: {url}") from err
        raise FetchError(f"cannot reach {url}: {reason}") from err
    try:
        return json.loads(body)
    except json.JSONDecodeError as err:
        raise FetchError(f"invalid JSON from {url}: {err}") from err
