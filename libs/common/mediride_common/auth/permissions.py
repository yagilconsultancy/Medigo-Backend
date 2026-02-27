from mediride_common.schemas.enums import UserRole

# Role hierarchy: admin > business > driver > rider
ROLE_HIERARCHY = {
    UserRole.ADMIN: 4,
    UserRole.BUSINESS: 3,
    UserRole.DRIVER: 2,
    UserRole.RIDER: 1,
}


def has_higher_or_equal_role(user_role: UserRole, required_role: UserRole) -> bool:
    return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(required_role, 0)
