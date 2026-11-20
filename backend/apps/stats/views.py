from drf_spectacular.utils import extend_schema

from apps.stats import serializers as schema
from apps.stats.services import dashboard, may_view_dashboard
from core.api import BaseView, success
from core.exceptions import BusinessError
from core.schema import envelope


class DashboardView(BaseView):
    @extend_schema(responses=envelope("DashboardResponse", schema.Dashboard))
    def get(self, request):
        if not may_view_dashboard(request.user):
            raise BusinessError(40301, "Permission denied", 403)
        return success(request, dashboard(request.user))
