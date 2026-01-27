# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.


from typing import Dict, List

PERMISSIONS: List[str] = [
    "staff.read",
    "staff.create",
    "staff.update",
    "staff.delete",
    "staff.invite",
    "staff.activate",
    "appointments.read",
    "appointments.create",
    "appointments.update",
    "appointments.delete",
]


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
            "staff.invite",
            "staff.activate",
        ],
    },
    "staff": {
        "name": "Staff",
        "description": "General staff",
        "permissions": [
            "staff.read",
            "staff.create",
            "staff.update",
            "staff.invite",
            "staff.activate",
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
    "doctor": {
        "name": "Doctor",
        "description": "Medical doctor",
        "permissions": [
            "staff.read",
            "appointments.read",
            "appointments.update",
        ],
    },
    "manager": {
        "name": "Manager",
        "description": "Manage staff and schedules",
        "permissions": [
            "staff.read",
            "staff.create",
            "staff.update",
            "staff.activate",
        ],
    },
}


def all_permissions() -> List[str]:
    return PERMISSIONS[:]


def default_roles() -> Dict[str, Dict]:
    return DEFAULT_ROLES.copy()
