from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers

from apps.notifications.models import RegistrationNotice
from apps.notifications.services import inbox, mark_read
from core.api import BaseView, page, success, validated
from core.schema import envelope, listing
from core.serializers import EmptySerializer, StrictSerializer


class RegistrationNoticeSerializer(StrictSerializer):
    id = serializers.IntegerField(min_value=1)
    registration_id = serializers.IntegerField(min_value=1)
    submission_no = serializers.IntegerField(min_value=1)
    kind = serializers.ChoiceField(choices=RegistrationNotice.Kind.choices)
    created_at = serializers.DateTimeField()
    read_at = serializers.DateTimeField(allow_null=True)


class InboxView(BaseView):
    @extend_schema(
        parameters=[
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses=listing("RegistrationNoticeList", RegistrationNoticeSerializer),
    )
    def get(self, request):
        return success(
            request,
            page(
                request,
                inbox(request.user),
                lambda notice: RegistrationNoticeSerializer(notice).data,
            ),
        )


class ReadNoticeView(BaseView):
    @extend_schema(
        request=EmptySerializer,
        responses=envelope("ReadNoticeResponse", RegistrationNoticeSerializer),
    )
    def post(self, request, pk):
        validated(EmptySerializer, request)
        return success(
            request,
            RegistrationNoticeSerializer(mark_read(request.user, pk)).data,
        )
