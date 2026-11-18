-- Replace the contents of the class database with the current sample data (all in one transaction:
-- if anything fails, nothing changes). Run from a folder that contains data.sql, extra_tables.sql
-- and demo_rows.sql:   psql -h 127.0.0.1 -p 5454 -U au2327 -d proj1part2 -v ON_ERROR_STOP=1 -f reload_class_db.sql
-- The schema (tables, constraints, No_Double_Booking index) is NOT touched.
BEGIN;
TRUNCATE Payment, Reservation, RestaurantTable, Favorites, Writes_and_Receives_Review, Restaurant, Users CASCADE;
\i data.sql
\i extra_tables.sql
\i demo_rows.sql
SELECT (SELECT COUNT(*) FROM Users) AS users, (SELECT COUNT(*) FROM Restaurant) AS restaurants,
       (SELECT COUNT(*) FROM RestaurantTable) AS tables, (SELECT COUNT(*) FROM Reservation) AS reservations,
       (SELECT COUNT(*) FROM Payment) AS payments, (SELECT COUNT(*) FROM Writes_and_Receives_Review) AS reviews,
       (SELECT COUNT(*) FROM Favorites) AS favorites;
COMMIT;
