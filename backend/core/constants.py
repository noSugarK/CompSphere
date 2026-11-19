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
REVIEW_ACTIONS = ("approve", "reject", "return")
SCHOOL_LEVELS = ("ES", "MS", "HS", "U")
CONFIGURATION_STATES = ("enabled", "disabled")
CONFIGURATION_TRANSITIONS = {
    ("enabled", "disable"): "disabled",
    ("disabled", "enable"): "enabled",
}
