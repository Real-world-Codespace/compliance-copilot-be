from .schemas import UserView

def access_decision(user: UserView, document) -> tuple[bool, str]:
    if document.organization_id != user.organization_id: return False, "TENANT_MISMATCH"
    if "all" not in document.allowed_departments and user.department not in document.allowed_departments: return False, "DEPARTMENT_MISMATCH"
    if not set(user.roles).intersection(document.allowed_roles): return False, "ROLE_MISMATCH"
    return True, "POLICY_MATCH"

def approval_path(amount: float, contract_months: int) -> list[dict]:
    steps = [{"role":"Budget Owner", "reason":"Budget availability and business need"}]
    if amount >= 20_000_000: steps.append({"role":"Procurement Manager", "reason":"Competitive sourcing and supplier review"})
    if amount >= 100_000_000: steps.append({"role":"Finance Manager", "reason":"Spend control threshold"})
    if amount >= 500_000_000: steps.append({"role":"CFO", "reason":"Executive spend approval"})
    if contract_months >= 12: steps.append({"role":"Legal", "reason":"Contract term is 12 months or more"})
    return steps
