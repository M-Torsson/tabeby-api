from typing import Dict, List

# Canonical permission list used by the system
PERMISSIONS: List[str] = [
    # Staff management
    "staff.read",
    "staff.create",
    "staff.update",
    "staff.delete",
    "staff.invite",
    "staff.activate",
    # Appointments examples (reserved for future use)
    "appointments.read",
    "appointments.create",
    "appointments.update",
    "appointments.delete",
]


# Default roles and their permissions
DEFAULT_ROLES: Dict[str, Dict] = {
    "super-admin": {
        "name": "Super Admin",
        "description": "Full system access",
        "permissions": PERMISSIONS[:],
    },
    "admin": {
        "name": "Administrator",
        "description": "Administrative access",
        "permissions": [
            "staff.read",
            "staff.create",
            "staff.update",
            "staff.delete",
            "staff.invite",
        ],
    },
    "staff": {
        "name": "Staff",
        "description": "General staff",
        "permissions": [
            "staff.read",
        ],
    },
    "receptionist": {
        "name": "Receptionist",
        "description": "Front desk staff",
        "permissions": [
            "staff.read",
            "appointments.read",
            "appointments.create",
        ],
    },
    "nurse": {
        "name": "Nurse",
        "description": "Nursing staff",
        "permissions": [
            "staff.read",
            "appointments.read",
        ],
    },
}


def all_permissions() -> List[str]:
    return PERMISSIONS[:]


def default_roles() -> Dict[str, Dict]:
    return DEFAULT_ROLES.copy()
