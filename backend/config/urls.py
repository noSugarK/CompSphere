from django.http import JsonResponse
from django.urls import path
from drf_spectacular.views import SpectacularAPIView

from apps.accounts import views as accounts
from apps.competitions import views as competitions
from apps.registrations import views as registrations
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
    path("api/v1/seasons/current", competitions.CurrentSeasonView.as_view()),
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
]
