from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.competitions.services import configuration_edition
from apps.groups import serializers as schema
from apps.groups.models import Group
from apps.groups.services import (
    change_group_state,
    create_group,
    delete_group,
    update_group,
)
from core.api import BaseView, page, success, validated
from core.schema import envelope, listing
from core.serializers import EmptySerializer


class GroupListView(BaseView):
    @extend_schema(
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
        responses=listing("ManagedGroups", schema.ManagedGroup),
    )
    def get(self, request, pk):
        edition = configuration_edition(request.user, pk, "group:read")
        groups = Group.objects.filter(edition=edition, is_deleted=False).order_by("id")
        return success(
            request,
            page(request, groups, lambda group: schema.ManagedGroup(group).data),
        )

    @extend_schema(
        request=schema.GroupDraft,
        responses={201: envelope("GroupDraftResponse", schema.ManagedGroup)},
    )
    def post(self, request, pk):
        group = create_group(request.user, pk, validated(schema.GroupDraft, request))
        return success(request, schema.ManagedGroup(group).data, status=201)


class GroupDetailView(BaseView):
    @extend_schema(
        request=schema.GroupDraft,
        responses=envelope("GroupUpdateResponse", schema.ManagedGroup),
    )
    def patch(self, request, pk):
        form = schema.GroupDraft(data=request.data, partial=True)
        form.is_valid(raise_exception=True)
        group = update_group(request.user, pk, form.validated_data)
        return success(request, schema.ManagedGroup(group).data)

    @extend_schema(
        responses=envelope("GroupDeleteResponse", EmptySerializer, nullable=True)
    )
    def delete(self, request, pk):
        delete_group(request.user, pk)
        return success(request)


class GroupStateView(BaseView):
    action = ""

    @extend_schema(
        request=EmptySerializer,
        responses=envelope("GroupStateResponse", schema.ManagedGroup),
    )
    def post(self, request, pk):
        validated(EmptySerializer, request)
        group = change_group_state(request.user, pk, self.action)
        return success(request, schema.ManagedGroup(group).data)
