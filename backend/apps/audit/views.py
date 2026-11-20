from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.audit import serializers as schema
from apps.audit.queries import query
from core.api import BaseView, page, success
from core.schema import listing


class AuditLogListView(BaseView):
    @extend_schema(
        parameters=[
            schema.AuditFilters,
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses=listing("AuditLogs", schema.AuditLog),
    )
    def get(self, request):
        filters = schema.AuditFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        data = filters.validated_data
        return success(
            request,
            page(
                request,
                query(
                    request.user,
                    actor_id=data.get("actor"),
                    resource=data.get("resource"),
                    date_from=data.get("date_from"),
                    date_to=data.get("date_to"),
                ),
                lambda item: schema.AuditLog(item).data,
            ),
        )
