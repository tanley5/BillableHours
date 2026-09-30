from django.contrib import admin

from .models import (
    Assignment,
    ClientContractor,
    Contractor,
    Escrow,
    Job,
    PasswordInvite,
    Photo,
    Project,
    SubJob,
    SubJobPhoto,
    Submission,
    SubmissionPhoto,
    User,
    Visit,
)

admin.site.register(User)
admin.site.register(Project)
admin.site.register(Contractor)
admin.site.register(ClientContractor)
admin.site.register(PasswordInvite)
admin.site.register(Assignment)
admin.site.register(Visit)
admin.site.register(Job)
admin.site.register(Photo)
admin.site.register(SubJob)
admin.site.register(SubJobPhoto)
admin.site.register(Submission)
admin.site.register(SubmissionPhoto)
admin.site.register(Escrow)
