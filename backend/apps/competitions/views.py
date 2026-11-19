from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny

from apps.competitions import serializers as schema
from apps.competitions.models import Competition, Edition, Season
from apps.competitions.services import (
    activate_season,
    configuration_edition,
    create_competition,
    create_edition,
    create_season,
    edition_publication_checks,
    edition_seasons,
    managed_competitions,
    managed_editions,
    publish_competition,
    publish_edition,
    set_current_season,
    update_edition_details,
)
from apps.orgs.models import Organization, OrganizationMember
from apps.rbac.services import org_filter, require_perm
from core.api import BaseView, page, success, validated
from core.exceptions import BusinessError
from core.schema import envelope, listing
from core.serializers import EmptySerializer


def offering_data(item, edition):
    start, end = item.registration_window(edition)
    return {
        "id": item.id,
        "event_id": item.event_id,
        "event_code": item.event.code_id,
        "event_name": item.event.name,
        "group_id": item.group_id,
        "group_name": item.group.name,
        "school_level": item.group.school_level,
        "enrollment_type": item.group.enrollment_type,
        "min_members": item.event.min_members,
        "max_members": item.event.max_members,
        "require_coach": item.event.coach_required,
        "enroll_start": start.isoformat(),
        "enroll_end": end.isoformat(),
        "quota": item.quota,
        "required_materials": [
            m["key"] for m in item.event.material_requirements if m.get("required")
        ],
        "is_enabled": item.status == "enabled"
        and item.event.status == "enabled"
        and item.group.status == "enabled",
    }


def edition_data(item):
    return {
        "id": item.id,
        "competition_id": item.competition_id,
        "season_id": item.season_id,
        "name": item.name,
        "status": item.status,
        "approval_mode": item.approval_mode,
        "enroll_start": item.enroll_start.isoformat(),
        "enroll_end": item.enroll_end.isoformat(),
        "start_date": item.start_date.isoformat(),
        "end_date": item.end_date.isoformat(),
        "venue": item.venue,
        "offerings": [
            offering_data(option, item)
            for option in item.offerings.filter(
                is_deleted=False, event__is_deleted=False, group__is_deleted=False
            )
            .select_related("event", "group")
            .order_by("id")
        ],
    }


def published_editions():
    return Edition.objects.filter(
        status="published",
        is_deleted=False,
        competition__status="published",
        competition__is_deleted=False,
        season__is_default=True,
        season__status="active",
        approval_mode="single",
    )


class CurrentSeasonView(BaseView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses=envelope("CurrentSeasonResponse", schema.Season, nullable=True)
    )
    def get(self, request):
        item = Season.objects.filter(is_default=True, status="active").first()
        return success(
            request,
            {
                "id": item.id,
                "name": item.name,
                "start_date": item.starts_on.isoformat(),
                "end_date": item.ends_on.isoformat(),
                "status": item.status,
            }
            if item
            else None,
        )


class SeasonRegistryView(BaseView):
    @extend_schema(
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
        responses=listing("ManagedSeasons", schema.ManagedSeason),
    )
    def get(self, request):
        require_perm(request.user, "season:read")
        return success(
            request,
            page(
                request,
                Season.objects.order_by("-starts_on", "-id"),
                lambda item: schema.ManagedSeason(item).data,
            ),
        )

    @extend_schema(
        request=schema.SeasonDraft,
        responses={201: envelope("SeasonDraftResponse", schema.ManagedSeason)},
    )
    def post(self, request):
        item = create_season(request.user, validated(schema.SeasonDraft, request))
        return success(request, schema.ManagedSeason(item).data, status=201)


class SeasonActivateView(BaseView):
    @extend_schema(
        request=EmptySerializer,
        responses=envelope("SeasonActivateResponse", schema.ManagedSeason),
    )
    def post(self, request, pk):
        validated(EmptySerializer, request)
        return success(
            request, schema.ManagedSeason(activate_season(request.user, pk)).data
        )


class SeasonSetCurrentView(BaseView):
    @extend_schema(
        request=EmptySerializer,
        responses=envelope("SeasonSetCurrentResponse", schema.ManagedSeason),
    )
    def post(self, request, pk):
        validated(EmptySerializer, request)
        return success(
            request, schema.ManagedSeason(set_current_season(request.user, pk)).data
        )


class CompetitionRegistryView(BaseView):
    @extend_schema(
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
        responses=listing("ManagedCompetitions", schema.ManagedCompetition),
    )
    def get(self, request):
        return success(
            request,
            page(
                request,
                managed_competitions(request.user),
                lambda item: schema.ManagedCompetition(item).data,
            ),
        )

    @extend_schema(
        request=schema.CompetitionDraft,
        responses={
            201: envelope("CompetitionDraftResponse", schema.ManagedCompetition)
        },
    )
    def post(self, request):
        item = create_competition(
            request.user, validated(schema.CompetitionDraft, request)
        )
        return success(request, schema.ManagedCompetition(item).data, status=201)


class EditionSeasonListView(BaseView):
    @extend_schema(
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
        responses=listing("EligibleEditionSeasons", schema.ManagedSeason),
    )
    def get(self, request, pk):
        return success(
            request,
            page(
                request,
                edition_seasons(request.user, pk),
                lambda item: schema.ManagedSeason(item).data,
            ),
        )


class EditionRegistryView(BaseView):
    @extend_schema(
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
        responses=listing("ManagedEditions", schema.ManagedEdition),
    )
    def get(self, request, pk):
        return success(
            request,
            page(
                request,
                managed_editions(request.user, pk),
                lambda item: schema.ManagedEdition(item).data,
            ),
        )

    @extend_schema(
        request=schema.EditionDraft,
        responses={201: envelope("EditionDraftResponse", schema.ManagedEdition)},
    )
    def post(self, request, pk):
        item = create_edition(request.user, pk, validated(schema.EditionDraft, request))
        return success(request, schema.ManagedEdition(item).data, status=201)


class ManagedEditionDetailView(BaseView):
    @extend_schema(responses=envelope("ManagedEditionResponse", schema.ManagedEdition))
    def get(self, request, pk):
        edition = configuration_edition(request.user, pk, "edition:read")
        return success(request, schema.ManagedEdition(edition).data)

    @extend_schema(
        request=schema.EditionDetails,
        responses=envelope("EditionUpdateResponse", schema.ManagedEdition),
    )
    def patch(self, request, pk):
        serializer = schema.EditionDetails(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        edition = update_edition_details(request.user, pk, serializer.validated_data)
        return success(request, schema.ManagedEdition(edition).data)


class EditionPublicationChecksView(BaseView):
    @extend_schema(
        responses=envelope(
            "EditionPublicationChecksResponse", schema.EditionPublicationChecks
        )
    )
    def get(self, request, pk):
        edition = configuration_edition(request.user, pk, "edition:read")
        return success(request, edition_publication_checks(edition))


class EditionPublishView(BaseView):
    @extend_schema(
        request=EmptySerializer,
        responses=envelope("EditionPublishResponse", schema.ManagedEdition),
    )
    def post(self, request, pk):
        validated(EmptySerializer, request)
        item = publish_edition(request.user, pk)
        return success(request, schema.ManagedEdition(item).data)


class CompetitionPublishView(BaseView):
    @extend_schema(
        request=EmptySerializer,
        responses=envelope("CompetitionPublishResponse", schema.ManagedCompetition),
    )
    def post(self, request, pk):
        validated(EmptySerializer, request)
        item = publish_competition(request.user, pk)
        return success(request, schema.ManagedCompetition(item).data)


class PublicCompetitionListView(BaseView):
    permission_classes = [AllowAny]

    @extend_schema(responses=listing("Competitions", schema.Competition))
    def get(self, request):
        if "season_id" in request.query_params or "season" in request.query_params:
            raise BusinessError(40001, "The public season cannot be overridden", 400)
        queryset = (
            Competition.objects.filter(
                status="published", is_deleted=False, editions__in=published_editions()
            )
            .distinct()
            .order_by("id")
        )

        def serialize(item):
            return {
                "id": item.id,
                "public_code": item.public_code,
                "name": item.name,
                "summary": item.summary,
                "status": item.status,
                "editions": [
                    edition_data(e)
                    for e in published_editions()
                    .filter(competition=item)
                    .order_by("id")
                ],
            }

        return success(request, page(request, queryset, serialize))


class PublicEditionView(BaseView):
    permission_classes = [AllowAny]

    @extend_schema(responses=envelope("EditionResponse", schema.Edition))
    def get(self, request, pk):
        return success(request, edition_data(published_editions().get(pk=pk)))


class OrganizationListView(BaseView):
    @extend_schema(responses=listing("Organizations", schema.Organization))
    def get(self, request):
        queryset = (
            Organization.objects.filter(is_deleted=False, status="active")
            .filter(org_filter(request.user, "org:read", field="id"))
            .order_by("id")
        )
        return success(
            request,
            page(
                request,
                queryset,
                lambda x: {
                    "id": x.id,
                    "name": x.name,
                    "path": x.path,
                    "status": x.status,
                },
            ),
        )


class OrganizationMemberListView(BaseView):
    @extend_schema(responses=listing("OrganizationMembers", schema.OrganizationMember))
    def get(self, request, pk):
        require_perm(request.user, "org:manage_members", org_id=pk)
        queryset = (
            OrganizationMember.objects.filter(
                org_id=pk, left_at__isnull=True, user__profile__is_deleted=False
            )
            .select_related("user__profile")
            .order_by("id")
        )
        return success(
            request,
            page(
                request,
                queryset,
                lambda x: {
                    "id": x.id,
                    "user_id": x.user_id,
                    "real_name": x.user.profile.real_name,
                    "person_type": x.user.profile.person_type,
                    "school_level": x.user.profile.school_level,
                    "grade": x.user.profile.grade,
                },
            ),
        )
