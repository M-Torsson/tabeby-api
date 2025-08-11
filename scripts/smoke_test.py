import os
from fastapi.testclient import TestClient

# تأكد من ضبط قاعدة البيانات للاختبار إن لزم
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", "sqlite:///./local.db"))

from app.main import app

client = TestClient(app)


def main():
    print("GET /health ->", client.get("/health").status_code)
    # افحص /admins/_diagnose مع وبدون توكن
    r = client.get("/admins/_diagnose")
    print("GET /admins/_diagnose (no auth) ->", r.status_code, r.text[:200])


if __name__ == "__main__":
    main()
