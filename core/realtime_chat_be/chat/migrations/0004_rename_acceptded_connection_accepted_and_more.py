# Generated by Django 4.1.13 on 2024-04-01 09:49

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_message'),
    ]

    operations = [
        migrations.RenameField(
            model_name='connection',
            old_name='acceptded',
            new_name='accepted',
        ),
        migrations.RenameField(
            model_name='message',
            old_name='conenction',
            new_name='connection',
        ),
    ]