from __future__ import annotations

from .forms import AuthorSignupForm


def admin_signup_form(request):
    # Só injeta no login do admin (pra não poluir o restante)
    path = (getattr(request, "path", "") or "").lower().rstrip('/')
    if path == "/admin/login" and not getattr(request, "user", None).is_authenticated:
        return {"signup_form": AuthorSignupForm()}
    return {}
