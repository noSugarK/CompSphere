import hashlib
import json

from drf_spectacular.utils import extend_schema

from apps.orgs.models import OrganizationMember
from apps.profiles import serializers as schema
from apps.profiles.models import Profile
from apps.profiles.services import (
    create_change_request,
    edit_change_request,
    get_change_request,
    list_change_requests,
    provision_student,
    reset_student_password,
    review_change_request,
    submit_change_request,
    withdraw_change_request,
)
from core.api import BaseView, success, validated
from core.schema import envelope
from core.serializers import EmptySerializer


def _account(user, password=None):
    profile = Profile.objects.get(user=user)
    membership = OrganizationMember.objects.filter(
        user=user, is_primary=True, left_at__isnull=True
    ).first()
    data = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "status": user.status,
        "must_change_password": user.must_change_password,
        "initial_password_expires_at": user.initial_password_expires_at,
        "document_type": profile.document_type,
        "document_country": profile.document_country,
        "document_last4": profile.document_last4,
        "real_name": profile.real_name,
        "org_id": membership.org_id if membership else None,
    }
    if password is not None:
        # 06：临时密码只交付一次；重复请求走 result 缓存且不再包含密码。
        data["temporary_password"] = password
    return schema.StudentAccount(data).data


def _no_store(response):
    # success() 已设 no-store；密码响应禁止任何缓存。
    response["Cache-Control"] = "no-store"
    return response


class StudentAccountListView(BaseView):
    @extend_schema(
        request=schema.StudentAccountDraft,
        responses={201: envelope("StudentAccountResponse", schema.StudentAccount)},
    )
    def post(self, request, pk):
        payload = validated(schema.StudentAccountDraft, request)
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        # 幂等记录与账号同事务，失败不留半成品键（registrations 同模式）。
        user, password = provision_student(
            request.user, pk, payload, request.headers.get("Idempotency-Key"), digest
        )
        # 重放已成功的请求时不再交付临时密码。
        return _no_store(success(request, _account(user, password), 201))


class StudentPasswordResetView(BaseView):
    @extend_schema(
        request=schema.StudentPasswordReset,
        responses=envelope(
            "StudentPasswordResetResponse", schema.StudentPasswordResetResult
        ),
    )
    def post(self, request, pk):
        data = validated(schema.StudentPasswordReset, request)
        user, password = reset_student_password(request.user, pk, data)
        return _no_store(
            success(
                request,
                schema.StudentPasswordResetResult(
                    {
                        "id": user.id,
                        "username": user.username,
                        "must_change_password": user.must_change_password,
                        "initial_password_expires_at": user.initial_password_expires_at,
                        "temporary_password": password,
                    }
                ).data,
            )
        )


class IdentityChangeRequestView(BaseView):
    @extend_schema(
        operation_id="identity_change_requests_list",
        responses=envelope(
            "IdentityChangeListResponse", schema.IdentityChangeRequest, many=True
        ),
    )
    def get(self, request):
        return success(request, list_change_requests(request.user))

    @extend_schema(
        operation_id="identity_change_requests_create",
        request=schema.IdentityChangeDraft,
        responses={
            201: envelope("IdentityChangeCreateResponse", schema.IdentityChangeRequest)
        },
    )
    def post(self, request):
        data = validated(schema.IdentityChangeDraft, request)
        user_id = data.pop("user_id", None) or request.user.id
        return success(request, create_change_request(request.user, user_id, data), 201)


class IdentityChangeRequestDetailView(BaseView):
    @extend_schema(
        operation_id="identity_change_requests_retrieve",
        responses=envelope(
            "IdentityChangeDetailResponse", schema.IdentityChangeRequest
        ),
    )
    def get(self, request, pk):
        return success(request, get_change_request(request.user, pk))

    @extend_schema(
        operation_id="identity_change_requests_update",
        request=schema.IdentityChangeDraft,
        responses=envelope(
            "IdentityChangeUpdateResponse", schema.IdentityChangeRequest
        ),
    )
    def patch(self, request, pk):
        data = validated(schema.IdentityChangeDraft, request)
        data.pop("user_id", None)
        return success(request, edit_change_request(request.user, pk, data))


class IdentityChangeSubmitView(BaseView):
    @extend_schema(
        operation_id="identity_change_requests_submit",
        request=EmptySerializer,
        responses=envelope(
            "IdentityChangeSubmitResponse", schema.IdentityChangeRequest
        ),
    )
    def post(self, request, pk):
        validated(EmptySerializer, request)
        return success(request, submit_change_request(request.user, pk))


class IdentityChangeCancelView(BaseView):
    @extend_schema(
        operation_id="identity_change_requests_cancel",
        request=EmptySerializer,
        responses=envelope(
            "IdentityChangeCancelResponse", schema.IdentityChangeRequest
        ),
    )
    def post(self, request, pk):
        validated(EmptySerializer, request)
        copy_draft = request.query_params.get("copy_draft") == "true"
        return success(request, withdraw_change_request(request.user, pk, copy_draft))


class IdentityChangeReviewView(BaseView):
    @extend_schema(
        operation_id="identity_change_requests_review",
        request=schema.IdentityChangeReview,
        responses=envelope(
            "IdentityChangeReviewResponse", schema.IdentityChangeRequest
        ),
    )
    def post(self, request, pk):
        data = validated(schema.IdentityChangeReview, request)
        return success(
            request,
            review_change_request(
                request.user, pk, data["action"], data["comment"], data["version"]
            ),
        )
