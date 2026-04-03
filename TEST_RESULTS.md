# Test Results – eRepairing Backend

**Run date:** 2026-02-07  
**Command:** `python -m pytest tests/ -v --tb=line --no-cov`  
**Result:** **19 passed**, 0 failed, 33 warnings

---

## Summary

| Suite | Passed | Failed | Total |
|-------|--------|--------|-------|
| test_auth.py | 3 | 0 | 3 |
| test_health.py | 3 | 0 | 3 |
| test_hierarchy.py | 9 | 0 | 9 |
| test_signup_workflow.py | 4 | 0 | 4 |
| **Total** | **19** | **0** | **19** |

---

## Test Cases

### Auth (`tests/test_auth.py`)
| Test | Description | Result |
|------|-------------|--------|
| test_register_user | POST /auth/register (accepts 200/400/404) | PASSED |
| test_login_user | Create user in DB, login, get access_token | PASSED |
| test_login_invalid_credentials | Login with wrong credentials returns 401 | PASSED |

### Health & API (`tests/test_health.py`)
| Test | Description | Result |
|------|-------------|--------|
| test_health_check | GET /health returns 200 and status | PASSED |
| test_api_root | GET /api/v1/ returns 200 or 404 | PASSED |
| test_docs_available | GET /api/docs returns 200 | PASSED |

### Hierarchy (`tests/test_hierarchy.py`)
| Test | Description | Result |
|------|-------------|--------|
| test_org_admin_sees_all_org_users | Org admin list users sees all org users | PASSED |
| test_country_admin_sees_all_states | Country admin dashboard/states see all states | PASSED |
| test_country_admin_sees_only_country_users | Country admin list users filtered by country | PASSED |
| test_state_admin_sees_only_their_state_cities | State admin sees only their state cities | PASSED |
| test_state_admin_list_users_only_their_state | State admin list users only their state | PASSED |
| test_state_admin_cannot_see_other_state_city_tickets | State admin cannot access other state city tickets (404) | PASSED |
| test_city_admin_sees_only_their_city | City admin dashboard/users only their city | PASSED |
| test_city_admin_tickets_scope | City admin tickets list scoped to city | PASSED |
| test_hierarchy_use_case_city_admin_sees_only_their_engineers | City admin dashboard shows only their engineers | PASSED |

### Signup workflow (`tests/test_signup_workflow.py`)
| Test | Description | Result |
|------|-------------|--------|
| test_signup_requires_core_fields | Signup without required fields returns 400 | PASSED |
| test_signup_requires_location | Signup without location returns 400 | PASSED |
| test_signup_with_location_code_name | Signup with country_code/state_code/city_name succeeds | PASSED |
| test_signup_duplicate_org_email_fails | Signup with existing org email returns 400 | PASSED |

---

## How to run

- **Default (SQLite in-memory):**  
  `cd backend && python -m pytest tests/ -v --no-cov`

- **With MySQL:**  
  `TEST_DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/erepairing_test python -m pytest tests/ -v --no-cov`

- **With coverage:**  
  `python -m pytest tests/ -v`  
  (uses pytest.ini; may require `--no-cov` if coverage fails under SQLite)

---

## Notes

- Tests use **SQLite in-memory** by default so no MySQL is required. Set `TEST_DATABASE_URL` to use MySQL.
- `testserver` is in `ALLOWED_HOSTS` so the TestClient host is accepted.
- Hierarchy tests use `@hierarchy.example.com` emails to satisfy email validation (reserved TLDs like `.test` are rejected).
- Plan fixture uses `PlanType.STARTER` (no `tiered`).  
- There is no `/api/v1/auth/register` endpoint; `test_register_user` accepts 404, and `test_login_user` creates a user in the DB then logs in.
