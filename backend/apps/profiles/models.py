from django.conf import settings
from django.db import models

from core.models import BusinessModel


class Profile(BusinessModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="profile"
    )
    real_name = models.CharField(max_length=64)
    gender = models.CharField(max_length=10, null=True)
    birth_date = models.DateField(null=True)
    document_type = models.CharField(max_length=16, null=True)
    document_country = models.CharField(max_length=2, null=True)
    document_number_enc = models.BinaryField(null=True)
    document_hash = models.CharField(max_length=64, null=True, unique=True)
    document_last4 = models.CharField(max_length=4, null=True)
    identity_version = models.PositiveIntegerField(default=0)
    photo_storage_key = models.CharField(max_length=512, null=True)
    person_type = models.CharField(max_length=16, default="participant")
    school_level = models.CharField(max_length=8, null=True)
    grade = models.CharField(max_length=32, null=True)
    student_no = models.CharField(max_length=64, null=True)
    staff_no = models.CharField(max_length=64, null=True)
    title = models.CharField(max_length=64, null=True)

    class Meta:
        db_table = "user_profiles"
