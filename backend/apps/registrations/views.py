from drf_spectacular.utils import extend_schema

from apps.competitions.models import Edition
from apps.rbac.services import require_perm
from apps.registrations import serializers as schema
from apps.registrations import services
from apps.registrations.models import RegistrationMember
from core.api import BaseView, page, success, validated
from core.schema import envelope, listing
from core.serializers import VersionSerializer


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
        responses=listing("Registrations", schema.Registration),
    )
    def get(self, request):
        queryset = services.visible_registrations(request.user, managed=True)
        for name in ("edition", "org"):
            if name in request.query_params:
                raw = request.query_params[name]
                if not raw.isdigit() or int(raw) < 1:
                    from core.exceptions import BusinessError

                    raise BusinessError(40001, "Invalid filter", 400)
                queryset = queryset.filter(**{name + "_id": int(raw)})
        if request.query_params.get("status"):
            queryset = queryset.filter(status=request.query_params["status"])
        return success(
            request,
            page(
                request,
                queryset.order_by("-id"),
                lambda x: services.serialize_registration(x, request.user),
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
    @extend_schema(responses=listing("Submissions", schema.Submission))
    def get(self, request, pk):
        item = services.visible_registrations(request.user).get(pk=pk)

        def serialize(x):
            return {
                "submission_no": x.submission_no,
                "selected_school_level": x.selected_school_level,
                "submitted_at": x.submitted_at.isoformat(),
                "cancelled_at": x.cancelled_at.isoformat() if x.cancelled_at else None,
                "members": [
                    dict(m.public_info, user_id=m.user_id)
                    for m in RegistrationMember.objects.filter(
                        registration=item, submission_no=x.submission_no
                    ).order_by("sort_order", "id")
                ],
            }

        return success(
            request,
            page(request, item.submissions.order_by("submission_no"), serialize),
        )
