from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response

from core.constants import ErrorCode


class BusinessError(APIException):
    def __init__(self, code, message, status=409):
        self.code = int(code)
        self.status_code = status
        super().__init__(message)


CHINESE_MESSAGES = {
    40001: "请求格式不正确，请检查输入后重试。",
    40101: "登录状态已失效，请重新登录。",
    40105: "登录凭据无效，请核对后重试。",
    40301: "你没有执行此操作的权限。",
    40303: "不能审核本人提交或本人参赛的资料。",
    40304: "请先修改初始或重置密码。",
    40401: "记录不存在或无权查看。",
    40901: "已存在冲突记录，请刷新列表后重试。",
    40902: "当前状态不能执行此操作。",
    40905: "该幂等键已用于其他内容，请核对操作。",
    40906: "资料版本已更新，请刷新后重新确认。",
    40907: "队号及赛项身份已登记或属于其他单位。",
    40908: "成员已有当前队伍，请先处理原归属。",
    40909: "成员存在其他队伍的有效赛季绑定。",
    40910: "队伍尚未取得本赛季的有效注册许可。",
    40911: "当前赛季未开放，请联系平台管理员。",
    42201: "参赛成员人数不符合本赛项要求。",
    42202: "必需资料、材料或同意记录尚未齐全。",
    42203: "当前不在有效报名时间窗内。",
    42204: "成员年级不符合本组别要求。",
    42205: "声明学段与所选组别不一致。",
    42206: "参赛成员证件或必需资料不完整。",
    42207: "所选赛项与组别组合不可用。",
    42208: "请配置本单位有效的指导教练。",
    42211: "队伍尚未通过资料审核。",
    42213: "单位或成员归属不符合要求。",
    42901: "操作过于频繁，请稍后重试。",
}


def exception_handler(exc, context):
    from rest_framework.views import exception_handler as drf_handler

    request = context.get("request")
    if isinstance(exc, IntegrityError):
        exc = BusinessError(
            40901, "This operation conflicts with an existing record", 409
        )
    if isinstance(exc, ObjectDoesNotExist):
        exc = NotFound()
    response = drf_handler(exc, context)
    if response is None:
        return None
    code = getattr(exc, "code", None)
    if code is None:
        code = (
            ErrorCode.UNAUTHENTICATED
            if isinstance(exc, (AuthenticationFailed, NotAuthenticated))
            else ErrorCode.FORBIDDEN
            if isinstance(exc, PermissionDenied)
            else ErrorCode.NOT_FOUND
            if isinstance(exc, NotFound)
            else ErrorCode.INVALID
        )
    english = request and request.headers.get("Accept-Language", "").startswith("en")
    message = (
        (str(exc.detail) if isinstance(exc, BusinessError) else "Request rejected")
        if english
        else CHINESE_MESSAGES.get(int(code), "请求未通过校验或无权执行")
    )
    body = {
        "code": int(code),
        "message": message,
        "data": None,
        "request_id": getattr(request, "request_id", ""),
    }
    if isinstance(exc, ValidationError):
        detail = exc.detail
        body["errors"] = (
            {
                str(k): [str(x) for x in v] if isinstance(v, list) else [str(v)]
                for k, v in detail.items()
            }
            if isinstance(detail, dict)
            else {"non_field_errors": [str(x) for x in detail]}
        )
    return Response(body, status=response.status_code, headers=response.headers)
