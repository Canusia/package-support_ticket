from rest_framework.permissions import BasePermission
from cis.utils import (
    user_has_student_role, user_has_instructor_role, user_has_highschool_admin_role,
)


class _RolePermission(BasePermission):
    check = None

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and type(self).check(request.user))


class IsStudent(_RolePermission):
    check = staticmethod(user_has_student_role)


class IsInstructor(_RolePermission):
    check = staticmethod(user_has_instructor_role)


class IsHSAdmin(_RolePermission):
    check = staticmethod(user_has_highschool_admin_role)
