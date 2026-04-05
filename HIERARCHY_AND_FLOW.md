# Hierarchy and Data Visibility Flow

## Role hierarchy (location-based)

```
Platform Admin          → sees everything (all orgs, countries, states, cities, users, tickets)
    │
Organization Admin      → sees their organization only (all users in org, all tickets for org)
    │
Country Admin           → sees their country (all states in country, all cities in those states, users in country, tickets in those cities for org)
    │
State Admin             → sees their state only (cities in that state, users in that state, tickets in those cities for org)
    │
City Admin              → sees their city only (users in that city, tickets in that city for org)
    │
Support Engineer         → assigned tickets and their city
Customer                 → own tickets only
```

## Visibility matrix

| Role                | Users list              | States list        | Cities list           | Tickets / Dashboard      |
|---------------------|-------------------------|--------------------|------------------------|--------------------------|
| Platform Admin      | All                     | All (by country)   | All (by state)        | All                      |
| Organization Admin  | Same `organization_id`  | N/A (org scope)    | N/A                    | Org tickets              |
| Country Admin       | Same `country_id`       | All in country     | All in country (via states) | Tickets in country (org-scoped) |
| State Admin        | Same `state_id`         | N/A (one state)    | Cities in state        | Tickets in state (org-scoped) |
| City Admin         | Same `city_id`          | N/A                | N/A (one city)         | Tickets in city (org-scoped) |

## API endpoints and scope

- **GET /api/v1/users/**  
  - **Organization Admin:** `User.organization_id == current_user.organization_id`  
  - **Country Admin:** `User.country_id == current_user.country_id`  
  - **State Admin:** `User.state_id == current_user.state_id`  
  - **City Admin:** `User.city_id == current_user.city_id`  
  - **Platform Admin:** no filter  

- **GET /api/v1/country-admin/dashboard**  
  - Country admin only. Uses `current_user.country_id` → all states in that country → all cities in those states → tickets in those cities (and org).

- **GET /api/v1/country-admin/states**  
  - Returns all states in `current_user.country_id`.

- **GET /api/v1/state-admin/dashboard**  
  - State admin only. Uses `current_user.state_id` → cities in that state → tickets in those cities (and org).

- **GET /api/v1/state-admin/cities**  
  - Returns cities in `current_user.state_id` only.

- **GET /api/v1/state-admin/cities/{city_id}/tickets**  
  - Allowed only if `city.state_id == current_user.state_id`.

- **GET /api/v1/city-admin/dashboard**  
  - City admin only. Uses `current_user.city_id` → tickets and engineers in that city.

- **GET /api/v1/city-admin/tickets**  
  - Tickets where `Ticket.city_id == current_user.city_id`.

- **GET /api/v1/org-admin/...**  
  - All scoped to `current_user.organization_id`.

## Test data shape (for hierarchy tests)

- **1 Country** (e.g. India)
- **2–3 States** (e.g. Karnataka, Maharashtra, Tamil Nadu)
- **2–3 Cities per state**
- **1 Organization** (same for all hierarchy users)
- **Users:**
  - 1 Organization Admin (org_id set, country/state/city can be any or null for “org-wide”)
  - 1 Country Admin (country_id = India, org_id = org)
  - 1 State Admin per state (state_id = that state, org_id = org)
  - 1 City Admin per city (city_id = that city, org_id = org)
  - 1 Support Engineer per city (city_id, org_id)
  - 1–2 Customers (city_id set, org_id = org for tickets)

All hierarchy users share the same `organization_id` so that country/state/city admins see the same org’s tickets within their geographic scope.

## Inventory (hierarchy-based)

Inventory is scoped by **organization** and **location**: each inventory row has `organization_id`, `country_id`, `state_id`, `city_id`. Stock is per org and per city (optionally warehouse).

### Visibility by role

| Role                | Inventory scope |
|---------------------|-----------------|
| Organization Admin  | All org inventory; can filter by city_id, state_id (GET /org-admin/inventory/stock) |
| Country Admin       | Inventory where country_id = current_user.country_id (GET /inventory/stock) |
| State Admin         | Inventory in cities in their state (GET /state-admin/cities/{city_id}/inventory) |
| City Admin          | Inventory where city_id = current_user.city_id (GET /city-admin/inventory) |
| Support Engineer    | Inventory in their city (GET /inventory/stock?city_id=...) for ticket parts |

### Use part (consume from inventory)

**Path A — Engineer requests parts before finishing the job**

1. Engineer: **POST /api/v1/tickets/{id}/parts/request** with `{ "parts": [{ "part_id", "quantity" }] }` → ticket often moves to `waiting_parts`.
2. City Admin: **POST /api/v1/city-admin/tickets/{id}/approve-parts-request** — authorizes the request (no stock deduction); ticket typically returns to `in_progress` so work / ordering can continue.
3. Optional: engineer or admin marks **parts ordered** / **parts received** (`/tickets/{id}/parts/ordered`, `/parts/received`).
4. Engineer resolves the ticket with **POST /api/v1/tickets/{id}/resolve** including **`parts_used`** (same part lines as actually consumed).
5. City Admin: **POST /api/v1/city-admin/tickets/{id}/approve-parts** — deducts city inventory, `InventoryTransaction` type **out**.

**Path B — Parts only declared at resolution**

1. Engineer: **POST /api/v1/tickets/{id}/resolve** with **`parts_used`**.
2. City Admin: **POST /api/v1/city-admin/tickets/{id}/approve-parts** — deducts stock (same city + org as inventory row).

**UI:** City Admin dashboard → tab **Parts approval** — **Authorize parts request** (path A, before resolve) vs **Review & deduct stock** (after resolve).

### Return part (add back to inventory)

- **City Admin:** **POST /city-admin/inventory/returns** — body: inventory_id, quantity, optional ticket_id, notes. Adds quantity back to city inventory; creates InventoryTransaction type "return".
