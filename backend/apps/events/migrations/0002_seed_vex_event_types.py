from django.db import migrations


def seed_vex_event_types(apps, schema_editor):
    event_types = apps.get_model("events", "EventType").objects.using(
        schema_editor.connection.alias
    )
    for code, name in (
        ("VURC", "VEX U Robotics Competition"),
        ("V5RC", "VEX V5 Robotics Competition"),
        ("VIQRC", "VEX IQ Robotics Competition"),
        ("VAIMRC", "VEX AI Robotics Competition"),
        ("VGORC", "VEX GO Robotics Competition"),
    ):
        event_types.get_or_create(code=code, defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("events", "0001_initial")]
    operations = [migrations.RunPython(seed_vex_event_types, migrations.RunPython.noop)]
