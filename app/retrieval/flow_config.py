"""
PCC/CVR flow configuration: purpose lists, verification modes, and branch rules.
"""

PCC_PURPOSES_INDIVIDUAL = [
    "Emigration",
    "Licensing",
    "Employment/Employees of Private Firms",
    "Directors/Board Members",
    "Journalists/PIB",
    "Registration of Commercial Vehicles/PSV Badges",
    "Adoption of Child",
    "Agents Engaged for Post Office and Any Other Services to the Government",
    "Semi-Government or PSUs",
    "Director/Employees of Security Agencies Applying for Licenses Under PSARA",
    "Miscellaneous",
]

# Same as Individual but without "Adoption of Child"
PCC_PURPOSES_ORGANIZATION = [
    "Emigration",
    "Licensing",
    "Employment/Employees of Private Firms",
    "Directors/Board Members",
    "Journalists/PIB",
    "Registration of Commercial Vehicles/PSV Badges",
    "Agents Engaged for Post Office and Any Other Services to the Government",
    "Semi-Government or PSUs",
    "Director/Employees of Security Agencies Applying for Licenses Under PSARA",
    "Miscellaneous",
]

VERIFICATION_MODES = [
    "Address and Antecedent Verification",
    "Antecedent Verification Only",
]

# Purposes (lowercase) that mandate Address + Antecedent Verification — no choice given to user
MANDATORY_ADDR_ANTECEDENT_PURPOSES = {"emigration"}

# ─── MV Theft flow config ──────────────────────────────────────────────────

MV_THEFT_ROLES = ["Citizen / Complainant", "Duty Officer / Police Official"]

# ─── Lost Report flow config ───────────────────────────────────────────────

LOST_REPORT_TYPES = ["Lost", "Found"]
