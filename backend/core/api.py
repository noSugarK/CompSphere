from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import BusinessError


def success(request, data=None, status=200):
    response = Response(
        {"code": 0, "message": "ok", "data": data, "request_id": request.request_id},
        status=status,
    )
    response["Cache-Control"] = "no-store"
    return response


def page(request, queryset, serialize):
    try:
        current = int(request.query_params.get("page", "1"))
        size = int(request.query_params.get("page_size", "20"))
        if current < 1 or not 1 <= size <= 100:
            raise ValueError
    except ValueError as exc:
        raise BusinessError(40001, "Invalid pagination", 400) from exc
    total = queryset.count()
    return {
        "items": [
            serialize(x) for x in queryset[(current - 1) * size : current * size]
        ],
        "page": current,
        "page_size": size,
        "total": total,
    }


def validated(serializer_class, request):
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class BaseView(APIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if (
            request.user
            and request.user.must_change_password
            and request.path
            not in (
                "/api/v1/me",
                "/api/v1/auth/password/change",
                "/api/v1/auth/logout",
                "/api/v1/auth/csrf",
            )
        ):
            raise BusinessError(40304, "Change your password first", 403)
