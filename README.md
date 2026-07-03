# Inventory Management System

A Flask REST API for a small retail company's admin portal. Employees can
create, view, update, and delete inventory items, and can pull real product
data (name, category, description, image) from the **OpenFoodFacts** public
API by barcode or product name — either just to preview it, or to import it
straight into the inventory database. A command-line client is included so
the API can be exercised without a browser or Postman.

## Table of Contents
- [Task 1: The Problem](#task-1-the-problem)
- [Task 2: The Design](#task-2-the-design)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Running the API](#running-the-api)
- [API Reference](#api-reference)
- [Using the CLI](#using-the-cli)
- [Testing](#testing)
- [Git Workflow](#git-workflow)

## Task 1: The Problem

Retail staff need a single tool to:
1. Keep an accurate, centralized record of inventory (name, quantity, price,
   category, barcode).
2. Avoid re-typing product details by hand — instead pull real product data
   (name, category, description, photo) from a public product database by
   barcode or name.
3. Interact with that system from a script or terminal, not just a browser,
   so it can be automated or scripted later.
4. Trust that the system behaves correctly, verified by an automated test
   suite rather than manual clicking.

## Task 2: The Design

- **Storage:** SQLite (`inventory.db`), accessed through a small
  `database.py` data-access layer — no ORM, so the SQL is transparent and
  easy to read for a lab setting. Swapping this for Postgres later would only
  mean changing `database.get_connection`.
- **API layer:** Flask, exposing a REST-ish JSON API under `/api/*`. Standard
  CRUD verbs map to HTTP methods (`GET`, `POST`, `PATCH`, `DELETE`).
- **External data:** `external_api.py` wraps the OpenFoodFacts REST API and
  normalizes its response shape into our own item schema, so the rest of the
  app never has to know OpenFoodFacts' JSON format.
- **Client:** `cli.py` is a plain `requests`-based terminal client — it talks
  to the Flask API over HTTP, the same way any other client (a future React
  front end, Postman, etc.) would.
- **Tests:** `unittest` (run via `pytest`) covering the database layer, the
  external API wrapper (mocked — no live network calls in CI), and the full
  Flask route layer via Flask's test client.

### Data model (`items` table)

| Field       | Type    | Notes                                   |
|-------------|---------|------------------------------------------|
| id          | int     | primary key, auto-increment              |
| name        | text    | required                                 |
| barcode     | text    | optional                                 |
| category    | text    | optional                                 |
| quantity    | int     | default 0                                |
| price       | real    | default 0.0                              |
| description | text    | optional                                 |
| image_url   | text    | optional                                 |
| source      | text    | `manual` or `openfoodfacts`              |
| created_at  | text    | ISO-8601 UTC timestamp                   |
| updated_at  | text    | ISO-8601 UTC timestamp                   |

## Project Structure

```
inventory-management-system/
├── app.py                  # Flask application + all routes
├── database.py              # SQLite data-access layer
├── external_api.py          # OpenFoodFacts integration
├── cli.py                   # Command-line client
├── requirements.txt
├── README.md
├── .gitignore
└── tests/
    ├── test_app.py           # Route / CRUD tests (Flask test client)
    └── test_external_api.py  # Database + external API unit tests (mocked)
```

## Setup

Requires Python 3.9+.

```bash
git clone <your-repo-url>
cd inventory-management-system
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running the API

```bash
python app.py
```

The server starts at `http://127.0.0.1:5000`. It creates `inventory.db` in
the project folder automatically on first run.

## API Reference

All request/response bodies are JSON.

### Health
| Method | Route         | Description        |
|--------|---------------|---------------------|
| GET    | `/api/health` | Service status check |

### Inventory CRUD
| Method | Route                | Description                                              |
|--------|-----------------------|------------------------------------------------------------|
| GET    | `/api/items`          | List all items. Optional `?name=` / `?category=` filters. |
| GET    | `/api/items/<id>`     | Fetch a single item.                                       |
| POST   | `/api/items`          | Create an item. Requires `name`; other fields optional.   |
| PATCH  | `/api/items/<id>`     | Partially update an item.                                  |
| DELETE | `/api/items/<id>`     | Delete an item.                                             |

Example — create an item:
```bash
curl -X POST http://127.0.0.1:5000/api/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Blue Widget", "category": "Hardware", "quantity": 50, "price": 9.99}'
```

### External product lookup (OpenFoodFacts)
| Method | Route                              | Description                                   |
|--------|--------------------------------------|-------------------------------------------------|
| GET    | `/api/external/barcode/<barcode>`  | Look up one product by barcode (no DB write).  |
| GET    | `/api/external/search?name=<name>` | Search products by name (no DB write).         |
| POST   | `/api/items/import`                | Look up a product externally **and** save it into inventory. |

`POST /api/items/import` body options:
```jsonc
// by barcode
{ "barcode": "3017620422003", "price": 3.49, "quantity": 20 }

// by name (uses the first search result unless "index" is given)
{ "name": "peanut butter", "index": 0, "price": 4.25, "quantity": 15 }
```
Any of `price`, `quantity`, `category`, `description`, `name` passed in the
body override the values pulled from OpenFoodFacts before the item is saved.

## Using the CLI

With the API running in one terminal, in another terminal:

```bash
python cli.py
```

You'll get a numbered menu to list, view, add, update, and delete items,
plus options to search OpenFoodFacts and import a result directly into the
inventory database.

## Testing

```bash
pytest tests/ -v
```

The suite covers:
- Every CRUD route (success and not-found/validation-error paths)
- Search/filter behavior
- The external API wrapper, with `requests.get` mocked so tests are fast and
  don't depend on network access
- The `POST /api/items/import` flow end-to-end (mocked fetch → real DB write)
- The `database.py` layer directly (create/read/update/delete/search)

## Git Workflow

This project was developed using feature branches merged into `main`:
- `feature/database-layer` — SQLite schema and CRUD helpers
- `feature/flask-api` — Flask routes and CRUD endpoints
- `feature/external-api` — OpenFoodFacts integration + import route
- `feature/cli` — command-line client
- `feature/tests` — unit test suite

Each feature branch was merged into `main` via a pull request and deleted
after merge to keep the branch list clean.
