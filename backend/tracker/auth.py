from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.throttling import SimpleRateThrottle

from .models import Assignment, User


class IsClient(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) == User.Role.CLIENT)


class IsContractor(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "role", None) == User.Role.CONTRACTOR
            and hasattr(user, "contractor_profile")
        )


class ContractorRateThrottle(SimpleRateThrottle):
    scope = "contractor"

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": user.pk}


def get_contractor(request):
    return request.user.contractor_profile


def get_owned_assignment(request, pk) -> Assignment:
    from django.shortcuts import get_object_or_404

    return get_object_or_404(Assignment, pk=pk, contractor=get_contractor(request))


def assert_assignment_accepted(assignment: Assignment):
    if assignment.status != Assignment.Status.ACCEPTED:
        raise PermissionDenied("Assignment must be accepted before performing this action.")
