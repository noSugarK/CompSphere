import time
import uuid

import structlog
from django.db import connection

logger = structlog.get_logger()


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid.uuid4())
        start = time.monotonic()
        count, sql_ms = 0, 0.0

        def wrapper(execute, sql, params, many, context):
            nonlocal count, sql_ms
            began = time.monotonic()
            try:
                return execute(sql, params, many, context)
            finally:
                count += 1
                sql_ms += (time.monotonic() - began) * 1000

        with connection.execute_wrapper(wrapper):
            response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        if request.path != "/healthz/":
            logger.info(
                "request.completed",
                request_id=request.request_id,
                method=request.method,
                route=getattr(request.resolver_match, "route", "unmatched"),
                status=response.status_code,
                duration_ms=round((time.monotonic() - start) * 1000, 2),
                queries=count,
                queries_ms=round(sql_ms, 2),
            )
        return response
