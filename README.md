# COMS W4111 Project 1, Part 3: Table Finder (restaurant reservations)

A Flask web app on top of the PostgreSQL database from Part 2. Team: Aman Upganlawar (au2327) and Grace Chun (gbc2115).

**Division of labor.** The web layer is done: routes, form validation, sessions, templates, error pages and tests
(`server.py`, `templates/`, `tests/`). **The database layer is ours to write:** every SQL operation lives in
[`queries.py`](queries.py) as a documented stub. Until a function is written, its page shows a friendly
"not written yet" message instead of crashing.

## Checklist: functions to write in `queries.py`

| Done | Function | Page that uses it | Course idea |
|---|---|---|---|
| [ ] | `list_users`, `get_user` | home (pick a user) | SELECT, ORDER BY |
| [ ] | `list_cuisines` | search, availability | SELECT DISTINCT |
| [ ] | `search_restaurants` | /restaurants | outer join, GROUP BY, AVG, optional filters with bound params |
| [ ] | `get_restaurant`, `list_tables`, `list_reviews` | /restaurant/<id> | joins, aggregation, weak entity |
| [ ] | `find_available_tables` | /availability | NOT EXISTS, overnight opening hours |
| [ ] | `create_reservation` | /book | transaction, foreign keys, id numbering, unique-index errors |
| [ ] | `list_reservations` | /reservations | 3-table join, outer join |
| [ ] | `cancel_reservation` | cancel button | UPDATE with a guarded WHERE |
| [ ] | `add_review` | review form | constraints, EXISTS check, UNIQUE |
| [ ] | `list_favorites`, `add_favorite`, `remove_favorite` | /favorites | many-to-many table, INSERT/DELETE |
| [ ] | `recommend_restaurants` | /recommendations | self-join, NOT EXISTS, GROUP BY (Part 2 query 3) |

## Rules (from the assignment)
* **No ORM.** Write SQL strings wrapped in `text()`.
* **No SQL injection.** Never put user input into the SQL text. Always bind parameters (`:name`).
* Never commit `.env`, `.venv/`, `proxy-key.json` or any password (`.gitignore` already excludes them).
* Keep `requirements.txt`, `Procfile` and `.python-version` at the repo root (Cloud Run needs them there).

## Run it locally

Option A, practice database (no class server needed):
```bash
scripts/local_db.sh start          # throwaway Postgres loaded with db/schema.sql and db/data.sql
cp .env.example .env               # then set: DB_USER=dev DB_PASSWORD=dev DB_PORT=55440
python3.14 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python server.py                   # open http://127.0.0.1:8111/
scripts/local_db.sh reset          # put the data back after experiments
```

Option B, the class database (needs the Cloud SQL Auth Proxy running on your laptop, see the Part 3 handout):
put your real PostgreSQL username and password in `.env` (port 5454).

Run the tests (they need no database): `python -m unittest discover -s tests -v`

## Files
* `server.py`: routes and validation (no SQL).
* `queries.py`: all SQL (you write this).
* `templates/`, `static/`: plain HTML pages.
* `tests/test_pages.py`: checks pages render, bad input is rejected before any query, input is passed as plain values.
* `db/`: the Part 2 schema and data (used by the local practice database).
* `docs/SUBMISSION_README_TEMPLATE.md`: skeleton for the README you submit on Gradescope.
* `docs/DEMO_SCRIPT.md`: plan for the 15-minute mentor meeting.
* `docs/cloud-run-setup.html`: the course's Cloud Run setup guide.

## Submit (Thu Nov 19, 5 p.m. ET)
From the folder that contains this project (rename it `proj1-3` or copy the files into one), without `.env`, `.venv/`, `.tools/`:
```bash
tar --exclude='.env' --exclude='.venv' --exclude='.tools' --exclude='.git' -cvf proj1-3.tar proj1-3 && gzip proj1-3.tar
```
Then upload `proj1-3.tar.gz` and a separate plain-text README (use the template) to Gradescope, once per team.
