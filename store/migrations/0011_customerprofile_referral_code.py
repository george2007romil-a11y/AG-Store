import uuid
from django.db import migrations, models


def populate_referral_codes(apps, schema_editor):
    Profile = apps.get_model('store', 'CustomerProfile')
    db = schema_editor.connection.alias
    used_codes = set(
        Profile.objects.using(db)
        .exclude(referral_code='')
        .values_list('referral_code', flat=True)
    )

    for profile in Profile.objects.using(db).filter(referral_code='').iterator():
        while True:
            code = uuid.uuid4().hex[:8].upper()
            if code not in used_codes:
                used_codes.add(code)
                profile.referral_code = code
                profile.save(using=db, update_fields=['referral_code'])
                break


class Migration(migrations.Migration):
    dependencies = [
        ('store', '0010_order_shipping_fee'),
    ]

    operations = [
        migrations.AddField(
            model_name='customerprofile',
            name='referral_code',
            field=models.CharField(
                max_length=12, blank=True, default=''
            ),
            preserve_default=False,
        ),
        migrations.RunPython(
            populate_referral_codes,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='customerprofile',
            name='referral_code',
            field=models.CharField(
                max_length=12, unique=True, blank=True
            ),
        ),
    ]
