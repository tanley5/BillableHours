from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.throttling import SimpleRateThrottle

from .models import Assignment


class ContractorTokenAuthentication(BaseAuthentication):
    """Authenticate contractor requests via the token path segment (set by the view)."""

    keyword = "token"

    def authenticate(self, request):
        token = getattr(request, "contractor_token", None) or request.META.get("HTTP_X_CONTRACTOR_TOKEN")
        if not token:
            return None
        try:
            assignment = Assignment.objects.select_related("project", "contractor").get(token=token)
        except Assignment.DoesNotExist as exc:
            raise AuthenticationFailed("Invalid token.") from exc
        if assignment.revoked:
            raise PermissionDenied("This link has been revoked.")
        return (assignment.contractor, assignment)


class IsClient(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) == "client")


class IsContractorAssignment(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.auth, Assignment) and not request.auth.revoked


class ContractorRateThrottle(SimpleRateThrottle):
    scope = "contractor"

    def get_cache_key(self, request, view):
        if not isinstance(request.auth, Assignment):
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.auth.token}
