from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny

from apps.awards import serializers as schema
from apps.awards.models import Award
from apps.awards.services import (
    change_records,
    create_award,
    decide_roster,
    delete_award,
    edition_info,
    list_rosters,
    managed_edition,
    public_roster,
    publish_roster,
    set_publication,
    update_award,
)
from core.api import BaseView, page, success, validated
from core.schema import envelope, listing
from core.serializers import EmptySerializer

optional_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)


def query_id(request, name):
    raw = request.query_params.get(name)
    return None if raw in (None, "", "null") else optional_id.run_validation(raw)


class EditionAwardListView(BaseView):
    @extend_schema(
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
        responses=listing("ManagedAwards", schema.Award),
    )
    def get(self, request, pk):
        edition = managed_edition(request.user, pk, "award:read")
        return success(
            request,
            page(
                request,
                Award.objects.filter(edition=edition, is_deleted=False).order_by(
                    "sort_order", "id"
                ),
                lambda item: schema.Award(item).data,
            ),
        )

    @extend_schema(
        request=schema.AwardDraft,
        responses={201: envelope("AwardCreateResponse", schema.Award)},
    )
    def post(self, request, pk):
        item = create_award(request.user, pk, validated(schema.AwardDraft, request))
        return success(request, schema.Award(item).data, status=201)


class AwardDetailView(BaseView):
    @extend_schema(
        request=schema.AwardPatch,
        responses=envelope("AwardUpdateResponse", schema.Award),
    )
    def patch(self, request, pk):
        item = update_award(request.user, pk, validated(schema.AwardPatch, request))
        return success(request, schema.Award(item).data)

    @extend_schema(
        responses=envelope("AwardDeleteResponse", EmptySerializer, nullable=True)
    )
    def delete(self, request, pk):
        delete_award(request.user, pk)
        return success(request)


class EditionRosterListView(BaseView):
    @extend_schema(
        parameters=[OpenApiParameter("offering_id", int, required=False)],
        responses=envelope("RostersResponse", schema.AwardRoster, many=True),
    )
    def get(self, request, pk):
        return success(
            request, list_rosters(request.user, pk, query_id(request, "offering_id"))
        )


class RosterRecordsView(BaseView):
    @extend_schema(
        parameters=[OpenApiParameter("offering_id", int, required=False)],
        request=schema.AwardRecordChange,
        responses=envelope("RosterRecordsResponse", schema.AwardRoster),
    )
    def put(self, request, pk):
        data = validated(schema.AwardRecordChange, request)
        return success(
            request,
            change_records(
                request.user,
                pk,
                query_id(request, "offering_id"),
                data["version"],
                data.get("add"),
                data.get("remove"),
            ),
        )


class RosterDecisionView(BaseView):
    action = ""

    @extend_schema(
        parameters=[OpenApiParameter("offering_id", int, required=False)],
        request=schema.RosterDecision,
        responses=envelope("RosterDecisionResponse", schema.AwardRoster),
    )
    def post(self, request, pk):
        data = validated(schema.RosterDecision, request)
        return success(
            request,
            decide_roster(
                request.user,
                pk,
                query_id(request, "offering_id"),
                self.action,
                data["version"],
                data.get("comment", ""),
            ),
        )


class RosterPublicationView(BaseView):
    @extend_schema(responses=envelope("RosterPublicationState", schema.EditionInfo))
    def get(self, request, pk):
        return success(
            request, edition_info(managed_edition(request.user, pk, "award:read"))
        )

    @extend_schema(
        request=schema.RosterPublicationPatch,
        responses=envelope("RosterPublicationResponse", schema.EditionInfo),
    )
    def patch(self, request, pk):
        edition = set_publication(
            request.user, pk, validated(schema.RosterPublicationPatch, request)
        )
        return success(request, edition_info(edition))


class RosterPublishView(BaseView):
    action = ""

    @extend_schema(
        request=EmptySerializer,
        responses=envelope("RosterPublishResponse", schema.EditionInfo),
    )
    def post(self, request, pk):
        validated(EmptySerializer, request)
        return success(
            request, edition_info(publish_roster(request.user, pk, self.action))
        )


class PublicRosterView(BaseView):
    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter("event", int, required=False),
            OpenApiParameter("group", int, required=False),
        ],
        responses=envelope("PublicRosterResponse", schema.PublicRoster),
    )
    def get(self, request, pk):
        return success(
            request,
            public_roster(
                request,
                pk,
                query_id(request, "event"),
                query_id(request, "group"),
            ),
        )
