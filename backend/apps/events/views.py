from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.competitions.services import configuration_edition
from apps.events import serializers as schema
from apps.events.models import Event, EventType, Offering
from apps.events.services import (
    change_event_state,
    change_offering_state,
    create_event,
    create_offering,
    delete_event,
    delete_offering,
    update_event,
)
from core.api import BaseView, page, success, validated
from core.schema import envelope, listing
from core.serializers import EmptySerializer


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


class EventDetailView(BaseView):
    @extend_schema(
        request=schema.EditionEventRules,
        responses=envelope("EditionEventUpdateResponse", schema.ManagedEvent),
    )
    def patch(self, request, pk):
        form = schema.EditionEventRules(data=request.data, partial=True)
        form.is_valid(raise_exception=True)
        item = update_event(request.user, pk, form.validated_data)
        return success(request, schema.ManagedEvent(item).data)

    @extend_schema(
        responses=envelope("EditionEventDeleteResponse", EmptySerializer, nullable=True)
    )
    def delete(self, request, pk):
        delete_event(request.user, pk)
        return success(request)


class EventStateView(BaseView):
    action = ""

    @extend_schema(
        request=EmptySerializer,
        responses=envelope("EditionEventStateResponse", schema.ManagedEvent),
    )
    def post(self, request, pk):
        validated(EmptySerializer, request)
        return success(
            request,
            schema.ManagedEvent(change_event_state(request.user, pk, self.action)).data,
        )


class EditionOfferingListView(BaseView):
    @extend_schema(
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
        responses=listing("ManagedOfferings", schema.ManagedOffering),
    )
    def get(self, request, pk):
        edition = configuration_edition(request.user, pk, "edition:read")
        offerings = (
            Offering.objects.filter(edition=edition, is_deleted=False)
            .select_related("event", "group")
            .order_by("id")
        )
        return success(
            request,
            page(request, offerings, lambda item: schema.ManagedOffering(item).data),
        )

    @extend_schema(
        request=schema.OfferingDraft,
        responses={201: envelope("OfferingDraftResponse", schema.ManagedOffering)},
    )
    def post(self, request, pk):
        item = create_offering(
            request.user, pk, validated(schema.OfferingDraft, request)
        )
        return success(request, schema.ManagedOffering(item).data, status=201)


class OfferingStateView(BaseView):
    action = ""

    @extend_schema(
        request=EmptySerializer,
        responses=envelope("OfferingStateResponse", schema.ManagedOffering),
    )
    def post(self, request, pk):
        validated(EmptySerializer, request)
        item = change_offering_state(request.user, pk, self.action)
        return success(request, schema.ManagedOffering(item).data)


class OfferingDetailView(BaseView):
    @extend_schema(
        responses=envelope("OfferingDeleteResponse", EmptySerializer, nullable=True)
    )
    def delete(self, request, pk):
        delete_offering(request.user, pk)
        return success(request)
