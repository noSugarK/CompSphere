from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers

from apps.competitions.models import Edition
from apps.competitions.serializers import Offering, offering_data
from apps.rbac.services import require_perm
from apps.registrations import serializers as schema
from apps.registrations import services
from core.api import BaseView, page, success, validated
from core.schema import envelope, listing
from core.serializers import VersionSerializer


class AvailableOfferingListView(BaseView):
    required_perm = "registration:create"

    @extend_schema(
        parameters=[
            OpenApiParameter("team_id", int),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses=listing("AvailableOfferings", Offering),
    )
    def get(self, request, pk):
        raw_team_id = request.query_params.get("team_id")
        team_id = (
            None
            if raw_team_id is None
            else serializers.IntegerField(
                min_value=1, max_value=2**53 - 1
            ).run_validation(raw_team_id)
        )
        edition, options = services.available_offerings(request.user, pk, team_id)
        return success(
            request,
            page(request, options, lambda option: offering_data(option, edition)),
        )


class EditionRegistrationListView(BaseView):
    @extend_schema(responses=listing("EditionRegistrations", schema.Registration))
    def get(self, request, pk):
        queryset = (
            services.visible_registrations(request.user)
            .filter(edition_id=pk)
            .order_by("-id")
        )
        return success(
            request,
            page(
                request,
                queryset,
                lambda x: services.serialize_registration(x, request.user),
            ),
        )

    @extend_schema(
        request=schema.RegistrationCreate,
        responses={201: envelope("RegistrationCreateResponse", schema.Registration)},
    )
    def post(self, request, pk):
        edition = Edition.objects.select_related("competition", "season").get(
            pk=pk, is_deleted=False
        )
        item = services.create_registration(
            request.user,
            edition,
            validated(schema.RegistrationCreate, request),
            request.headers.get("Idempotency-Key"),
        )
        return success(
            request, services.serialize_registration(item, request.user), 201
        )


class RegistrationListView(BaseView):
    @extend_schema(
        operation_id="registrations_list",
        parameters=[
            schema.ReviewQueueFilters,
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses=listing("Registrations", schema.ReviewQueueItem),
    )
    def get(self, request):
        filters = schema.ReviewQueueFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        queryset = services.review_queue_items(request.user, filters.validated_data)
        return success(
            request,
            page(
                request,
                queryset,
                lambda item: schema.ReviewQueueItem(item).data,
            ),
        )


class ReviewQueueOptionsView(BaseView):
    @extend_schema(
        parameters=[
            schema.ReviewQueueFacetQuery,
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses=listing("ReviewQueueOptions", schema.ReviewQueueOption),
    )
    def get(self, request):
        filters = schema.ReviewQueueFacetQuery(data=request.query_params)
        filters.is_valid(raise_exception=True)
        options = services.review_queue_options(request.user, **filters.validated_data)
        return success(
            request,
            page(
                request,
                options,
                lambda item: {"id": item["option_id"], "name": item["name"]},
            ),
        )


class RegistrationDetailView(BaseView):
    @extend_schema(responses=envelope("RegistrationResponse", schema.Registration))
    def get(self, request, pk):
        return success(
            request,
            services.serialize_registration(
                services.visible_registrations(request.user).get(pk=pk), request.user
            ),
        )

    @extend_schema(
        request=schema.RegistrationPatch,
        responses=envelope("RegistrationUpdateResponse", schema.Registration),
    )
    def patch(self, request, pk):
        item = services.update_registration(
            request.user, pk, validated(schema.RegistrationPatch, request)
        )
        return success(request, services.serialize_registration(item, request.user))


class RegistrationSubmitView(BaseView):
    action = "submit"

    @extend_schema(
        request=VersionSerializer,
        responses=envelope("RegistrationSubmitResponse", schema.Registration),
    )
    def post(self, request, pk):
        data = validated(VersionSerializer, request)
        item = services.submit_registration(
            request.user,
            pk,
            data["version"],
            request.headers.get("Idempotency-Key"),
            action=self.action,
        )
        return success(request, services.serialize_registration(item, request.user))


class RegistrationCancelView(BaseView):
    action = "cancel_review"

    @extend_schema(
        request=VersionSerializer,
        responses=envelope("RegistrationCancelResponse", schema.Registration),
    )
    def post(self, request, pk):
        data = validated(VersionSerializer, request)
        item = services.cancel_or_withdraw(
            request.user, pk, data["version"], self.action
        )
        return success(request, services.serialize_registration(item, request.user))


class RegistrationApprovalView(BaseView):
    @extend_schema(
        request=schema.RegistrationReview,
        responses=envelope("RegistrationApprovalResponse", schema.Registration),
    )
    def post(self, request, pk):
        item = services.review_registration(
            request.user, pk, validated(schema.RegistrationReview, request)
        )
        return success(request, services.serialize_registration(item, request.user))


class BulkRegistrationApprovalView(BaseView):
    required_perm = "approval:review_single"

    @extend_schema(
        request=schema.BulkRegistrationReview,
        responses=envelope(
            "BulkRegistrationApprovalResponse", schema.BulkReviewResult, many=True
        ),
    )
    def post(self, request):
        results = services.bulk_review_registrations(
            request.user, validated(schema.BulkRegistrationReview, request)
        )
        return success(request, schema.BulkReviewResult(results, many=True).data)


class ApprovalRecordListView(BaseView):
    @extend_schema(responses=listing("ApprovalRecords", schema.ApprovalRecord))
    def get(self, request, pk):
        item = services.visible_registrations(request.user).get(pk=pk)
        require_perm(
            request.user,
            "approval:read_records",
            org_id=item.org_id,
            edition=item.edition,
        )
        return success(
            request,
            page(request, item.approval_records.order_by("id"), services.approval_data),
        )


class SubmissionListView(BaseView):
    @extend_schema(
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
        responses=listing("Submissions", schema.Submission),
    )
    def get(self, request, pk):
        item = services.visible_registrations(request.user).get(pk=pk)
        result = page(
            request, services.submission_history(item), lambda submission: submission
        )
        services.attach_submitted_members(item, result["items"])
        result["items"] = schema.Submission(result["items"], many=True).data
        return success(request, result)


class SubmissionDetailView(BaseView):
    @extend_schema(
        operation_id="registrations_submission_retrieve",
        responses=envelope("SubmissionResponse", schema.Submission),
    )
    def get(self, request, pk, number):
        item = services.visible_registrations(request.user).get(pk=pk)
        submission = services.submission_history(item).get(submission_no=number)
        services.attach_submitted_members(item, [submission])
        return success(request, schema.Submission(submission).data)
