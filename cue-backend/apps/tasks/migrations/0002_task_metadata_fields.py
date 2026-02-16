from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="metadata_html",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="task",
            name="metadata_json",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
