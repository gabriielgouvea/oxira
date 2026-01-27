from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0012_post_title_blank_slug_nullable"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="avatar_crop_x",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="avatar_crop_y",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="avatar_crop_w",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="avatar_crop_h",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="post",
            name="image_crop_x",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="post",
            name="image_crop_y",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="post",
            name="image_crop_w",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="post",
            name="image_crop_h",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
    ]
