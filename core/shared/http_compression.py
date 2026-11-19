import gzip

from flask import Flask, Response, request

DEFAULT_COMPRESSIBLE_MIMETYPES: frozenset[str] = frozenset(
    {
        "application/json",
        "application/javascript",
        "text/javascript",
        "text/css",
        "text/html",
        "text/plain",
        "image/svg+xml",
    }
)


def _accepts_gzip() -> bool:
    accept_encoding = request.headers.get("Accept-Encoding", "")
    for part in accept_encoding.split(","):
        encoding = part.split(";")[0].strip().lower()
        if encoding == "gzip":
            return True
    return False


def _append_vary_accept_encoding(response: Response) -> None:
    existing = response.headers.get("Vary", "")
    if not existing:
        response.headers["Vary"] = "Accept-Encoding"
        return
    tokens = [item.strip().lower() for item in existing.split(",") if item.strip()]
    if "accept-encoding" not in tokens and "*" not in tokens:
        response.headers["Vary"] = f"{existing}, Accept-Encoding"


def register_gzip_compression(
    app: Flask,
    min_size: int = 500,
    compress_level: int = 6,
    compressible_mimetypes: frozenset[str] = DEFAULT_COMPRESSIBLE_MIMETYPES,
) -> None:
    """Register an after_request hook that gzip-compresses eligible Flask responses."""

    @app.after_request
    def _compress_response(response: Response) -> Response:
        if request.method == "HEAD":
            return response
        if response.status_code < 200 or response.status_code >= 300 or response.status_code in (204, 304):
            return response
        if "Content-Encoding" in response.headers:
            return response

        mimetype = (response.mimetype or "").lower()
        if mimetype == "text/event-stream" or mimetype not in compressible_mimetypes:
            return response
        if not _accepts_gzip():
            return response

        if response.direct_passthrough:
            response.direct_passthrough = False

        data = response.get_data()
        if len(data) < min_size:
            return response

        compressed = gzip.compress(data, compresslevel=compress_level)
        if len(compressed) >= len(data):
            return response

        response.set_data(compressed)
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Content-Length"] = str(len(compressed))
        _append_vary_accept_encoding(response)

        etag = response.headers.get("ETag")
        if etag and not etag.startswith("W/"):
            response.headers["ETag"] = f"W/{etag}"

        return response
