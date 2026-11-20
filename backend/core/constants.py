from enum import IntEnum


class ErrorCode(IntEnum):
    INVALID = 40001
    UNAUTHENTICATED = 40101
    VERIFICATION_CODE = 40102
    LOGIN_FAILED = 40105
    FORBIDDEN = 40301
    SELF_REVIEW = 40303
    CHANGE_PASSWORD = 40304
    NOT_FOUND = 40401
    DUPLICATE = 40901
    STATE = 40902
    IDEMPOTENCY = 40905
    VERSION = 40906
    TEAM_IDENTITY = 40907
    CURRENT_TEAM = 40908
    SEASON_BINDING = 40909
    LICENSE = 40910
    SEASON = 40911
    MEMBERS = 42201
    MATERIALS = 42202
    WINDOW = 42203
    GRADE = 42204
    LEVEL = 42205
    DOCUMENT = 42206
    OFFERING = 42207
    COACH = 42208
    TEAM_REVIEW = 42211
    ORG = 42213
    RATE_LIMIT = 42901
    UNAVAILABLE = 50301


EDITABLE_STATES = ("draft", "returned", "rejected")
REGISTRATION_STATES = (*EDITABLE_STATES, "pending_review", "approved", "withdrawn")
REVIEW_ACTIONS = ("approve", "reject", "return")
SCHOOL_LEVELS = ("ES", "MS", "HS", "U")
RANK_LEVELS = ("first", "second", "third", "excellence", "custom")
ROSTER_STATES = ("editing", "under_approval", "confirmed")
# 02 §4.7 PUBLIC_ALLOWED：公示字段服务端常量上限，不含证件与联系方式。
ROSTER_PUBLISH_FIELDS = frozenset(
    {"team_code", "org_name", "member_names", "event", "group", "award"}
)


def default_roster_publish_fields():
    # 04 §competition_editions 白名单默认值；服务端仍与 PUBLIC_ALLOWED 求交集。
    return sorted(ROSTER_PUBLISH_FIELDS)


# 06 §成员字段分级:公开输出仅允许这些 public_info 键,任何新键默认被过滤。
MEMBER_PUBLIC_FIELDS = frozenset({"real_name", "role", "school_level", "grade"})
# 仅 registration:read 作用域内可追加,且只到末四位为止。
MEMBER_DOCUMENT_FIELDS = ("document_type", "document_country", "document_last4")
CONFIGURATION_STATES = ("enabled", "disabled")
CONFIGURATION_TRANSITIONS = {
    ("enabled", "disable"): "disabled",
    ("disabled", "enable"): "enabled",
}
