"""Voyage AI embedding provider.

Implemented against Voyage's documented REST embeddings API (a single
`POST /v1/embeddings` endpoint, OpenAI-embeddings-API-shaped request/
response) via a direct httpx call -- not the `voyageai` SDK package --
so the exact HTTP contract stays fully visible and testable (via respx)
without depending on an SDK's internal HTTP client choice, mirroring
how app.core.storage.s3_provider talks to S3 via boto3's own client
rather than a higher-level wrapper.

IMPORTANT, disclosed explicitly per the Step 10 instructions: this
session has no live network path to api.voyageai.com and no API key,
so this integration cannot be verified against Voyage's current
production API. It is implemented against the stable, long-documented
shape of their embeddings endpoint. If that contract has materially
changed since, live requests will fail with EmbeddingOperationError
(never silently succeed with wrong data) -- see the Step 10 report.
"""

import time
from typing import Any

import httpx

from app.core.embeddings.exceptions import (
    EmbeddingAuthenticationError,
    EmbeddingOperationError,
    EmbeddingUnavailable,
)
from app.core.embeddings.provider import EmbeddingProvider

_EMBEDDINGS_URL = "https://api.voyageai.com/v1/embeddings"
_MAX_ATTEMPTS = 3
_BASE_RETRY_DELAY_SECONDS = 0.5
_REQUEST_TIMEOUT_SECONDS = 30.0

# Worth one retry: connectivity blips and the service's own "back off"
# signal. Never a 4xx -- an auth or malformed-request failure will fail
# identically on retry, so retrying it only adds latency.
_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


class VoyageEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self, *, api_key: str, model: str, dimension: int, timeout_seconds: float = _REQUEST_TIMEOUT_SECONDS
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._dimension = dimension
        self._client = httpx.Client(timeout=timeout_seconds)

    def __repr__(self) -> str:
        # Deliberately excludes the API key -- this is what would end up
        # in a log line or error report if this object were ever printed.
        return f"VoyageEmbeddingProvider(model={self._model!r})"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_identifier(self) -> str:
        return self._model

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, input_type="document")

    def embed_text(self, text: str) -> list[float]:
        return self._embed([text], input_type="document")[0]

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], input_type="query")[0]

    def _embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        payload = {"input": texts, "model": self._model, "input_type": input_type}
        body = self._call_with_retry(payload)

        data = body.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise EmbeddingOperationError(
                f"Embedding provider returned {len(data) if isinstance(data, list) else 'a non-list'} "
                f"result(s) for {len(texts)} input(s)."
            )

        # Voyage's `data` items carry their own `index`; sort defensively
        # rather than assume response order matches request order.
        try:
            ordered = sorted(data, key=lambda item: item["index"])
            vectors = [item["embedding"] for item in ordered]
        except (KeyError, TypeError) as exc:
            raise EmbeddingOperationError("Embedding provider returned an unexpected response shape.") from exc

        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != self._dimension:
                raise EmbeddingOperationError(
                    f"Embedding provider returned a vector of unexpected shape "
                    f"(expected length {self._dimension})."
                )

        return vectors

    def _call_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = self._client.post(
                    _EMBEDDINGS_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
            except httpx.HTTPError as exc:
                last_exc = exc
            else:
                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise EmbeddingOperationError(
                            "Embedding provider returned a non-JSON response."
                        ) from exc
                if response.status_code in (401, 403):
                    raise EmbeddingAuthenticationError(
                        "Embedding provider rejected the configured API key."
                    )
                if response.status_code not in _TRANSIENT_STATUS_CODES:
                    raise EmbeddingOperationError(
                        f"Embedding provider request failed (status {response.status_code})."
                    )
                last_exc = EmbeddingUnavailable(
                    f"Embedding provider returned status {response.status_code}."
                )

            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_BASE_RETRY_DELAY_SECONDS * (2**attempt))

        raise EmbeddingUnavailable("Embedding provider is temporarily unavailable.") from last_exc

