from django.contrib import admin

from .models import Assignment, Contractor, Job, Photo, Project, User, Visit

admin.site.register(User)
admin.site.register(Project)
admin.site.register(Contractor)
admin.site.register(Assignment)
admin.site.register(Visit)
admin.site.register(Job)
admin.site.register(Photo)
