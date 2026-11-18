from drf_spectacular.utils import extend_schema

from apps.teams import serializers as schema
from apps.teams import services
from core.api import BaseView, page, success, validated
from core.schema import envelope, listing
from core.serializers import EmptySerializer, ReviewSerializer


class TeamListView(BaseView):
    @extend_schema(operation_id="teams_list", responses=listing("Teams", schema.Team))
    def get(self, request):
        return success(
            request,
            page(
                request,
                services.teams_for(request.user).order_by("id"),
                lambda item: services.team_data(item, request.user),
            ),
        )


class TeamDetailView(BaseView):
    @extend_schema(responses=envelope("TeamResponse", schema.Team))
    def get(self, request, pk):
        return success(
            request,
            services.team_data(
                services.teams_for(request.user).get(pk=pk), request.user
            ),
        )


class TeamRequestListView(BaseView):
    @extend_schema(
        operation_id="team_change_requests_list",
        responses=listing("TeamChangeRequests", schema.TeamChangeRequest),
    )
    def get(self, request):
        return success(
            request,
            page(
                request,
                services.requests_for(request.user).order_by("-id"),
                services.request_data,
            ),
        )

    @extend_schema(
        request=schema.TeamRequestCreate,
        responses={
            201: envelope("TeamRequestCreateResponse", schema.TeamChangeRequest)
        },
    )
    def post(self, request):
        return success(
            request,
            services.request_data(
                services.create_request(
                    request.user, validated(schema.TeamRequestCreate, request)
                )
            ),
            201,
        )


class TeamRequestDetailView(BaseView):
    @extend_schema(responses=envelope("TeamRequestResponse", schema.TeamChangeRequest))
    def get(self, request, pk):
        return success(
            request,
            services.request_data(services.requests_for(request.user).get(pk=pk)),
        )


class TeamRequestSubmitView(BaseView):
    @extend_schema(
        request=EmptySerializer,
        responses=envelope("TeamRequestSubmitResponse", schema.TeamChangeRequest),
    )
    def post(self, request, pk):
        validated(EmptySerializer, request)
        return success(
            request, services.request_data(services.submit_request(request.user, pk))
        )


class TeamRequestReviewView(BaseView):
    @extend_schema(
        request=ReviewSerializer,
        responses=envelope("TeamRequestReviewResponse", schema.TeamChangeRequest),
    )
    def post(self, request, pk):
        return success(
            request,
            services.request_data(
                services.review_request(
                    request.user, pk, validated(ReviewSerializer, request)
                )
            ),
        )


class SeasonRequestListView(BaseView):
    @extend_schema(
        responses=listing("TeamSeasonRegistrations", schema.SeasonRegistration)
    )
    def get(self, request):
        return success(
            request,
            page(
                request,
                services.seasons_for(request.user).order_by("-id"),
                services.season_data,
            ),
        )

    @extend_schema(
        request=schema.SeasonRequestCreate,
        responses={
            201: envelope("SeasonRequestCreateResponse", schema.SeasonRegistration)
        },
    )
    def post(self, request):
        return success(
            request,
            services.season_data(
                services.create_season_request(
                    request.user, validated(schema.SeasonRequestCreate, request)
                )
            ),
            201,
        )


class SeasonRequestSubmitView(BaseView):
    @extend_schema(
        request=EmptySerializer,
        responses=envelope("SeasonRequestSubmitResponse", schema.SeasonRegistration),
    )
    def post(self, request, pk):
        validated(EmptySerializer, request)
        return success(
            request, services.season_data(services.act_on_season(request.user, pk))
        )


class SeasonRequestReviewView(BaseView):
    @extend_schema(
        request=schema.SeasonReview,
        responses=envelope("SeasonRequestReviewResponse", schema.SeasonRegistration),
    )
    def post(self, request, pk):
        return success(
            request,
            services.season_data(
                services.act_on_season(
                    request.user, pk, validated(schema.SeasonReview, request)
                )
            ),
        )
