from apps.profiles.models import Profile


def create_participant_profile(user, real_name):
    """Registration never sets identity documents or administrative person types."""
    return Profile.objects.create(
        user=user, real_name=real_name, person_type="participant"
    )
