from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.competitions.services import configuration_edition
from apps.events import serializers as schema
from apps.events.models import Event, EventType
from apps.events.services import create_event
from core.api import BaseView, page, success, validated
from core.schema import envelope, listing


class EditionEventTypeListView(BaseView):
    @extend_schema(
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
        responses=listing("EventTypeSummaries", schema.EventTypeSummary),
    )
    def get(self, request, pk):
        configuration_edition(request.user, pk, "event:create")
        return success(
            request,
            page(
                request,
                EventType.objects.order_by("code"),
                lambda item: schema.EventTypeSummary(item).data,
            ),
        )


class EditionEventListView(BaseView):
    @extend_schema(
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
        responses=listing("ManagedEvents", schema.ManagedEvent),
    )
    def get(self, request, pk):
        edition = configuration_edition(request.user, pk, "event:read")
        return success(
            request,
            page(
                request,
                Event.objects.filter(edition=edition, is_deleted=False).order_by("id"),
                lambda item: schema.ManagedEvent(item).data,
            ),
        )

    @extend_schema(
        request=schema.EditionEventDraft,
        responses={201: envelope("EditionEventDraftResponse", schema.ManagedEvent)},
    )
    def post(self, request, pk):
        item = create_event(
            request.user, pk, validated(schema.EditionEventDraft, request)
        )
        return success(request, schema.ManagedEvent(item).data, status=201)
