# README for Gradescope: Table Finder (restaurant reservations)

Team: Aman Upganlawar (au2327) and Grace Bokyung Chun (gbc2115)

## Database account
PostgreSQL account holding our database on the class server: au2327 (database proj1part2). This is the same database as Part 2 (7 tables: Users, Restaurant, RestaurantTable, Reservation, Payment, Writes_and_Receives_Review, Favorites).

## Web application URL
https://project1-web-731893459985.us-east1.run.app

Cloud Run service `project1-web` (us-east1), min 0 / max 1 instances. The first request after idle can take a few seconds (cold start). Health check: `/db-check`.

## What we implemented from the Part 1 proposal
* Search restaurants with optional filters (name, cuisine, maximum price, a zip code range, open now); results show the average review rating (`/restaurants`).
* Restaurant page with details, tables and reviews (`/restaurant/<id>`).
* Availability by date, time and party size, on the same page as the search: under each restaurant it lists the tables that fit the party, are open at that time (including hours past midnight) and are not already booked or within 10 minutes of another booking. Restaurants have several kinds of table (Booth, Bar, Window Seat, ...).
* Booking a table with a fixed advance deposit (half of the restaurant's minimum price times the party size), stored as a Reservation row plus a Payment row (`/book`).
* View and cancel your own reservations; a reservation can only be cancelled while it is still booked and has not started (`/reservations`).
* Reviews, allowed only for a completed reservation and only once per user per restaurant.
* Favorites: add, remove and list (`/favorites`).
* Recommendations based on what similar users booked (`/recommendations`).
* "Login" is a user picker stored in the session (the project does not require real authentication).

## What we did not implement (and why)
* Real authentication and real payment processing. Users are picked from a list, and a Payment row only records the advance amount and status. Both were out of scope for the course.

## New features beyond the proposal
* Server-side validation of every form with friendly error pages (400, 404, 405, 500, and 503 when the database is unreachable).
* Automated tests: page tests with mocked queries plus integration tests of every query against a throwaway local PostgreSQL.
* `/db-check` endpoint used to verify the Cloud Run to Cloud SQL connection.

## Two interesting pages
1. **Find restaurants with availability, then book (`/restaurants`, then `/book`).** The user filters by name, cuisine, price and zip range and optionally gives a date, time and party size. The availability query joins Restaurant and RestaurantTable, filters by capacity and opening hours (handling restaurants that close after midnight), and uses `NOT EXISTS` against Reservation to drop tables that are already booked for an overlapping slot. Booking then runs one transaction that inserts the Reservation and its Payment together, so either both exist or neither does. We find it interesting because correctness depends on the database: a unique index (`No_Double_Booking`) is the final guard against two people taking the same table.
2. **Recommendations (`/recommendations`).** For the current user, it finds other users who booked the same restaurants and suggests restaurants they booked that the current user has not (self-join on Reservation, `NOT EXISTS`, `GROUP BY` with `COUNT` to rank). No input beyond the logged-in user is needed. It is interesting because it turns the booking data into a useful result with one aggregate query, and it is the "interesting query" from Part 2, now parameterized.

## Design decisions worth mentioning
* **SQL injection:** all SQL is in `queries.py` as `text()` strings with bound parameters (`:name`). User input is never concatenated into SQL. No ORM.
* **Primary keys:** new ids are `MAX(id)+1` inside the booking transaction; if two requests collide on the primary key, the transaction retries (up to 3 times).
* **Double booking:** a table cannot be booked within 10 minutes of another booking (checked in the booking transaction while the table row is locked), and the `No_Double_Booking` unique index is the last guard for the exact same time. Violations are shown as "that table is already booked".
* **Deposit:** fixed by the database layer, not typed by the user: half of the restaurant's Min_price times the party size.
* **Cancellation:** a single guarded `UPDATE` (right owner, status booked, not started, compared in New York time), so it is atomic and cannot cancel someone else's reservation.
* **Reviews:** an `EXISTS` check that the user has a completed reservation at that restaurant, plus a UNIQUE (User_ID, Restaurant_ID) constraint so a user reviews a restaurant once.
* **Separation:** `server.py` has no SQL; `queries.py` has all SQL.
* **Deployment:** the Flask container and a Cloud SQL Auth Proxy sidecar run in one Cloud Run service; the database user, password and proxy key come from Secret Manager, never from the repo (`deploy/service.yaml` has no secrets).

## AI tools
We used Claude Code (Anthropic) during Part 3.
* Claude Code generated the project scaffold: the Flask routes in `server.py`, form validation, session handling, the HTML templates and CSS, the error handlers, the tests, the local-database script, and the Cloud Run deployment configuration. It also explained the deployment steps.
* Grace wrote the read-side queries in `queries.py` (user/cuisine lists, restaurant search, restaurant details, tables, reviews, availability). Aman asked Claude Code to review them, and it fixed typos and bugs in them (misspelled table and column names, a stray parenthesis, a wrong join, overnight opening hours).
* Aman wrote the remaining queries in `queries.py` (booking transaction, reservations, cancellation, reviews, favorites, recommendations). Aman reviewed them and ran the tests.
* The schema, the sample data and the Part 2 SQL queries were written by us (Claude Code was used for earlier Part 1/2 guidance and the VM setup, not for the queries themselves).
* We tested the application ourselves and are responsible for its contents.
