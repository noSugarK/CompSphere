from rest_framework import serializers

from core.serializers import StrictSerializer


class AuditLog(StrictSerializer):
    id = serializers.IntegerField()
    actor_id = serializers.IntegerField(allow_null=True)
    action = serializers.CharField()
    resource = serializers.CharField()
    resource_id = serializers.CharField()
    created_at = serializers.DateTimeField()


class AuditFilters(serializers.Serializer):
    # 查询参数序列化器：page/page_size 同 URL 出现，不能拒绝未知字段。
    actor = serializers.IntegerField(min_value=1, required=False)
    resource = serializers.CharField(max_length=32, required=False)
    date_from = serializers.CharField(max_length=10, required=False)
    date_to = serializers.CharField(max_length=10, required=False)
