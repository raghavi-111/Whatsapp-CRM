from django.contrib import admin

from .models import Lead, Service

admin.site.register(Service)
admin.site.register(Lead)
