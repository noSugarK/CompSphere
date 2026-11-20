from django.http import JsonResponse
from django.urls import path
from drf_spectacular.views import SpectacularAPIView

from apps.accounts import views as accounts
from apps.audit import views as audit
from apps.awards import views as awards
from apps.competitions import views as competitions
from apps.events import views as events
from apps.groups import views as groups
from apps.notifications import views as notifications
from apps.profiles import views as profiles
from apps.registrations import views as registrations
from apps.stats import views as stats
from apps.teams import views as teams


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz/", health),
    path("api/v1/schema", SpectacularAPIView.as_view()),
    path("api/v1/auth/csrf", accounts.CsrfView.as_view()),
    path("api/v1/auth/login", accounts.LoginView.as_view()),
    path("api/v1/auth/verify-code/send", accounts.VerificationRequestView.as_view()),
    path("api/v1/auth/register", accounts.RegisterView.as_view()),
    path("api/v1/auth/password/reset", accounts.PasswordResetView.as_view()),
    path("api/v1/auth/refresh", accounts.RefreshView.as_view()),
    path("api/v1/auth/logout", accounts.LogoutView.as_view()),
    path("api/v1/auth/password/change", accounts.PasswordChangeView.as_view()),
    path("api/v1/me", accounts.MeView.as_view()),
    path("api/v1/me/preferences", accounts.PreferencesView.as_view()),
    path("api/v1/competitions", competitions.CompetitionRegistryView.as_view()),
    path(
        "api/v1/competitions/<int:pk>/publish",
        competitions.CompetitionPublishView.as_view(),
    ),
    path(
        "api/v1/competitions/<int:pk>/edition-seasons",
        competitions.EditionSeasonListView.as_view(),
    ),
    path(
        "api/v1/competitions/<int:pk>/editions",
        competitions.EditionRegistryView.as_view(),
    ),
    path("api/v1/me/notifications", notifications.InboxView.as_view()),
    path(
        "api/v1/me/notifications/<int:pk>/read", notifications.ReadNoticeView.as_view()
    ),
    path("api/v1/seasons/current", competitions.CurrentSeasonView.as_view()),
    path(
        "api/v1/editions/<int:pk>/event-types",
        events.EditionEventTypeListView.as_view(),
    ),
    path("api/v1/editions/<int:pk>/events", events.EditionEventListView.as_view()),
    path("api/v1/events/<int:pk>", events.EventDetailView.as_view()),
    path(
        "api/v1/events/<int:pk>/enable", events.EventStateView.as_view(action="enable")
    ),
    path(
        "api/v1/events/<int:pk>/disable",
        events.EventStateView.as_view(action="disable"),
    ),
    path("api/v1/editions/<int:pk>/groups", groups.GroupListView.as_view()),
    path(
        "api/v1/editions/<int:pk>/offerings", events.EditionOfferingListView.as_view()
    ),
    path("api/v1/offerings/<int:pk>", events.OfferingDetailView.as_view()),
    path(
        "api/v1/offerings/<int:pk>/enable",
        events.OfferingStateView.as_view(action="enable"),
    ),
    path(
        "api/v1/offerings/<int:pk>/disable",
        events.OfferingStateView.as_view(action="disable"),
    ),
    path("api/v1/groups/<int:pk>", groups.GroupDetailView.as_view()),
    path(
        "api/v1/groups/<int:pk>/enable", groups.GroupStateView.as_view(action="enable")
    ),
    path(
        "api/v1/groups/<int:pk>/disable",
        groups.GroupStateView.as_view(action="disable"),
    ),
    path("api/v1/editions/<int:pk>", competitions.ManagedEditionDetailView.as_view()),
    path(
        "api/v1/editions/<int:pk>/publication-checks",
        competitions.EditionPublicationChecksView.as_view(),
    ),
    path("api/v1/editions/<int:pk>/publish", competitions.EditionPublishView.as_view()),
    path("api/v1/seasons", competitions.SeasonRegistryView.as_view()),
    path("api/v1/seasons/<int:pk>", competitions.SeasonDetailView.as_view()),
    path(
        "api/v1/seasons/<int:pk>/archive",
        competitions.SeasonArchiveView.as_view(),
    ),
    path("api/v1/seasons/<int:pk>/activate", competitions.SeasonActivateView.as_view()),
    path(
        "api/v1/seasons/<int:pk>/set-current",
        competitions.SeasonSetCurrentView.as_view(),
    ),
    path(
        "api/v1/public/competitions", competitions.PublicCompetitionListView.as_view()
    ),
    path("api/v1/public/editions/<int:pk>", competitions.PublicEditionView.as_view()),
    path("api/v1/orgs", competitions.OrganizationListView.as_view()),
    path(
        "api/v1/orgs/<int:pk>/members",
        competitions.OrganizationMemberListView.as_view(),
    ),
    path("api/v1/teams", teams.TeamListView.as_view()),
    path("api/v1/teams/<int:pk>", teams.TeamDetailView.as_view()),
    path("api/v1/team-change-requests", teams.TeamRequestListView.as_view()),
    path("api/v1/team-change-requests/<int:pk>", teams.TeamRequestDetailView.as_view()),
    path(
        "api/v1/team-change-requests/<int:pk>/submit",
        teams.TeamRequestSubmitView.as_view(),
    ),
    path(
        "api/v1/team-change-requests/<int:pk>/review",
        teams.TeamRequestReviewView.as_view(),
    ),
    path("api/v1/team-season-registrations", teams.SeasonRequestListView.as_view()),
    path(
        "api/v1/team-season-registrations/<int:pk>/submit",
        teams.SeasonRequestSubmitView.as_view(),
    ),
    path(
        "api/v1/team-season-registrations/<int:pk>/review",
        teams.SeasonRequestReviewView.as_view(),
    ),
    path(
        "api/v1/editions/<int:pk>/registrations",
        registrations.EditionRegistrationListView.as_view(),
    ),
    path("api/v1/registrations", registrations.RegistrationListView.as_view()),
    path(
        "api/v1/registrations/bulk-approval",
        registrations.BulkRegistrationApprovalView.as_view(),
    ),
    path(
        "api/v1/registrations/filter-options",
        registrations.ReviewQueueOptionsView.as_view(),
    ),
    path(
        "api/v1/editions/<int:pk>/available-offerings",
        registrations.AvailableOfferingListView.as_view(),
    ),
    path(
        "api/v1/registrations/<int:pk>", registrations.RegistrationDetailView.as_view()
    ),
    path(
        "api/v1/registrations/<int:pk>/submit",
        registrations.RegistrationSubmitView.as_view(),
    ),
    path(
        "api/v1/registrations/<int:pk>/resubmit",
        registrations.RegistrationSubmitView.as_view(action="resubmit"),
    ),
    path(
        "api/v1/registrations/<int:pk>/cancel-review",
        registrations.RegistrationCancelView.as_view(),
    ),
    path(
        "api/v1/registrations/<int:pk>/withdraw",
        registrations.RegistrationCancelView.as_view(action="withdraw"),
    ),
    path(
        "api/v1/registrations/<int:pk>/approval",
        registrations.RegistrationApprovalView.as_view(),
    ),
    path(
        "api/v1/registrations/<int:pk>/approval-records",
        registrations.ApprovalRecordListView.as_view(),
    ),
    path(
        "api/v1/registrations/<int:pk>/submissions",
        registrations.SubmissionListView.as_view(),
    ),
    path(
        "api/v1/registrations/<int:pk>/submissions/<int:number>",
        registrations.SubmissionDetailView.as_view(),
    ),
    path("api/v1/editions/<int:pk>/awards", awards.EditionAwardListView.as_view()),
    path("api/v1/awards/<int:pk>", awards.AwardDetailView.as_view()),
    path("api/v1/editions/<int:pk>/rosters", awards.EditionRosterListView.as_view()),
    path("api/v1/editions/<int:pk>/roster/records", awards.RosterRecordsView.as_view()),
    path(
        "api/v1/editions/<int:pk>/roster/submit",
        awards.RosterDecisionView.as_view(action="submit"),
    ),
    path(
        "api/v1/editions/<int:pk>/roster/approve",
        awards.RosterDecisionView.as_view(action="approve"),
    ),
    path(
        "api/v1/editions/<int:pk>/roster/reject",
        awards.RosterDecisionView.as_view(action="reject"),
    ),
    path(
        "api/v1/editions/<int:pk>/roster/unlock",
        awards.RosterDecisionView.as_view(action="unlock"),
    ),
    path(
        "api/v1/editions/<int:pk>/roster-publication",
        awards.RosterPublicationView.as_view(),
    ),
    path(
        "api/v1/editions/<int:pk>/roster/publish",
        awards.RosterPublishView.as_view(action="publish"),
    ),
    path(
        "api/v1/editions/<int:pk>/roster/unpublish",
        awards.RosterPublishView.as_view(action="unpublish"),
    ),
    path("api/v1/public/editions/<int:pk>/roster", awards.PublicRosterView.as_view()),
    path("api/v1/stats/dashboard", stats.DashboardView.as_view()),
    path("api/v1/audit-logs", audit.AuditLogListView.as_view()),
    path(
        "api/v1/orgs/<int:pk>/student-accounts",
        profiles.StudentAccountListView.as_view(),
    ),
    path(
        "api/v1/users/<int:pk>/reset-student-password",
        profiles.StudentPasswordResetView.as_view(),
    ),
    path(
        "api/v1/identity-change-requests",
        profiles.IdentityChangeRequestView.as_view(),
    ),
    path(
        "api/v1/identity-change-requests/<int:pk>",
        profiles.IdentityChangeRequestDetailView.as_view(),
    ),
    path(
        "api/v1/identity-change-requests/<int:pk>/submit",
        profiles.IdentityChangeSubmitView.as_view(),
    ),
    path(
        "api/v1/identity-change-requests/<int:pk>/cancel-and-edit",
        profiles.IdentityChangeCancelView.as_view(),
    ),
    path(
        "api/v1/identity-change-requests/<int:pk>/review",
        profiles.IdentityChangeReviewView.as_view(),
    ),
]
