from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CrashReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("level", models.CharField(default="fatal", max_length=24)),
                ("error_name", models.CharField(blank=True, max_length=120)),
                ("message", models.TextField(blank=True)),
                ("stack", models.TextField(blank=True)),
                ("source", models.CharField(default="js", max_length=32)),
                ("is_fatal", models.BooleanField(default=True)),
                ("platform", models.CharField(blank=True, max_length=32)),
                ("os_version", models.CharField(blank=True, max_length=64)),
                ("app_version", models.CharField(blank=True, max_length=64)),
                ("app_build", models.CharField(blank=True, max_length=64)),
                ("app_environment", models.CharField(blank=True, max_length=64)),
                ("session_id", models.CharField(blank=True, max_length=128)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("occurred_at", models.DateTimeField(blank=True, null=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="crash_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-received_at"],
            },
        ),
        migrations.AddIndex(
            model_name="crashreport",
            index=models.Index(fields=["received_at"], name="core_crashr_receive_6720f0_idx"),
        ),
        migrations.AddIndex(
            model_name="crashreport",
            index=models.Index(fields=["platform"], name="core_crashr_platfor_f2f0dc_idx"),
        ),
        migrations.AddIndex(
            model_name="crashreport",
            index=models.Index(fields=["source"], name="core_crashr_source_b1f1d2_idx"),
        ),
        migrations.AddIndex(
            model_name="crashreport",
            index=models.Index(fields=["is_fatal"], name="core_crashr_is_fata_2c4cc1_idx"),
        ),
    ]
