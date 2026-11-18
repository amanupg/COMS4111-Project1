"""Integration tests for queries.py against a REAL local PostgreSQL.

They create a scratch database (proj1_test) from db/schema.sql and db/data.sql,
so your class database is never touched. Start the local server first:

    scripts/local_db.sh start
    python -m unittest tests.test_queries_db -v

If the local server is not running, these tests are skipped.
"""

import datetime
import decimal
import os
import subprocess
import unittest
from pathlib import Path

from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import OperationalError

import queries

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("LOCAL_DB_PORT", "55440"))
PGBIN = next(iter(sorted(Path("/opt/homebrew/opt").glob("postgresql@*/bin"))), None)
FUTURE = datetime.date(2099, 6, 15)


def url(database):
    return URL.create("postgresql+psycopg2", username="dev", password="dev",
                      host="127.0.0.1", port=PORT, database=database)


def psql_file(path):
    psql = str(PGBIN / "psql") if PGBIN else "psql"
    subprocess.run([psql, "-h", "127.0.0.1", "-p", str(PORT), "-U", "dev", "-d", "proj1_test",
                    "-v", "ON_ERROR_STOP=1", "-q", "-f", str(path)], check=True)


def rebuild_database():
    admin = create_engine(url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text("DROP DATABASE IF EXISTS proj1_test"))
        c.execute(text("CREATE DATABASE proj1_test"))
    admin.dispose()
    psql_file(ROOT / "db" / "schema.sql")
    psql_file(ROOT / "db" / "data.sql")
    psql_file(ROOT / "db" / "extra_tables.sql")


class DatabaseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            rebuild_database()
        except (OperationalError, subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise unittest.SkipTest(f"local database not available ({type(exc).__name__}); run scripts/local_db.sh start")
        cls.engine = create_engine(url("proj1_test"))

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        # Fresh data for every test, so tests do not depend on each other.
        self.engine.dispose()
        admin = create_engine(url("proj1_test"), isolation_level="AUTOCOMMIT")
        with admin.connect() as c:
            c.execute(text("TRUNCATE Payment, Reservation, RestaurantTable, Favorites, "
                           "Writes_and_Receives_Review, Restaurant, Users CASCADE"))
        admin.dispose()
        psql_file(ROOT / "db" / "data.sql")
        psql_file(ROOT / "db" / "extra_tables.sql")
        self.conn = self.engine.connect()
        self.users_at_start = self.scalar("SELECT COUNT(*) FROM Users")

    def tearDown(self):
        self.conn.close()

    def _callTestMethod(self, method):
        # Functions that are still PLACEHOLDERS (raise NotImplementedError) make their tests skip, not fail.
        # Once you write the function, its tests start running and tell you if it is right.
        try:
            method()
        except NotImplementedError as exc:
            self.skipTest(f"placeholder not written yet: {exc}")

    def scalar(self, sql, **params):
        return self.conn.execute(text(sql), params).scalar_one()


class WriteSideTests(DatabaseTestCase):
    """create_reservation, list_reservations, cancel_reservation, add_review, favorites, recommendations."""

    def book(self, **overrides):
        args = dict(user_id=1, restaurant_id=101, table_no=1, res_date=FUTURE, res_time=datetime.time(9, 0),
                    party_size=2, special_requests="Window", payment_method="Cash")
        args.update(overrides)
        return queries.create_reservation(self.conn, **args)

    # -- create_reservation ------------------------------------------------
    def test_booking_creates_reservation_and_payment_together(self):
        expected_id = self.scalar("SELECT MAX(Reservation_ID) FROM Reservation") + 1
        rid = self.book()
        self.assertEqual(rid, expected_id)
        row = self.conn.execute(text("SELECT status, user_id, table_no FROM Reservation WHERE reservation_id = :r"),
                                {"r": rid}).one()
        self.assertEqual(tuple(row), ("booked", 1, 1))
        pay = self.conn.execute(text("SELECT amount, method, reservation_id FROM Payment WHERE reservation_id = :r"),
                                {"r": rid}).one()
        self.assertEqual((pay.amount, pay.method), (decimal.Decimal("5.00"), "Cash"))  # 0.5 x $5 x 2 people

    def test_deposit_is_half_the_minimum_price_times_party_size(self):
        # Soho Pizzeria (107): Min_price 10, table 1 seats 8.
        rid = self.book(restaurant_id=107, table_no=1, res_time=datetime.time(12, 0), party_size=5)
        amount = self.scalar("SELECT amount FROM Payment WHERE reservation_id = :r", r=rid)
        self.assertEqual(amount, decimal.Decimal("25.00"))  # 0.5 x 10 x 5

    def test_buffer_of_ten_minutes_between_bookings_of_one_table(self):
        self.book(res_time=datetime.time(12, 0))
        for minute in (0, 1, 5, 9):  # inside the 10-minute buffer after the first booking
            with self.assertRaises(queries.BookingError, msg=f"12:{minute:02d}"):
                self.book(user_id=2, res_time=datetime.time(12, minute))
        with self.assertRaises(queries.BookingError):  # and before it
            self.book(user_id=2, res_time=datetime.time(11, 55))
        self.book(user_id=2, res_time=datetime.time(12, 10))  # exactly 10 minutes later is fine
        self.book(user_id=3, res_time=datetime.time(11, 50))  # exactly 10 minutes earlier is fine

    def test_buffer_only_applies_to_the_same_table_and_day_and_active_bookings(self):
        rid = self.book(res_time=datetime.time(12, 0))
        self.book(user_id=2, table_no=2, res_time=datetime.time(12, 1))                  # other table (restaurant 101 has 4)
        self.book(user_id=3, res_date=FUTURE + datetime.timedelta(days=1), res_time=datetime.time(12, 1))  # other day
        queries.cancel_reservation(self.conn, 1, rid)
        self.book(user_id=4, res_time=datetime.time(12, 1))                               # cancelled booking holds nothing

    def test_double_booking_is_refused_and_leaves_no_trace(self):
        self.book()
        before = (self.scalar("SELECT COUNT(*) FROM Reservation"), self.scalar("SELECT COUNT(*) FROM Payment"))
        with self.assertRaises(queries.BookingError) as ctx:
            self.book(user_id=2)
        self.assertIn("already booked", str(ctx.exception))
        after = (self.scalar("SELECT COUNT(*) FROM Reservation"), self.scalar("SELECT COUNT(*) FROM Payment"))
        self.assertEqual(before, after)

    def test_cancelled_booking_frees_the_table(self):
        rid = self.book()
        self.assertTrue(queries.cancel_reservation(self.conn, 1, rid))
        self.assertEqual(self.book(user_id=2), rid + 1)

    def test_party_too_large_closed_and_missing_table(self):
        with self.assertRaises(queries.BookingError):
            self.book(party_size=3)  # table 1 at restaurant 101 seats 2
        with self.assertRaises(queries.BookingError):
            self.book(res_time=datetime.time(23, 0))  # closes at 16:00
        with self.assertRaises(queries.BookingError):
            self.book(table_no=99)

    def test_overnight_restaurant_hours(self):
        # Restaurant 107 is open 11:30 to 01:00 (past midnight), table 1 seats 8.
        self.book(restaurant_id=107, table_no=1, res_time=datetime.time(0, 30), party_size=4)
        with self.assertRaises(queries.BookingError):
            self.book(restaurant_id=107, table_no=1, res_time=datetime.time(3, 0), party_size=4)

    def test_unknown_user_is_a_friendly_error(self):
        with self.assertRaises(queries.BookingError):
            self.book(user_id=9999)

    def test_hostile_text_is_stored_as_plain_text(self):
        evil = "x'); DROP TABLE Users; --"
        rid = self.book(special_requests=evil)
        stored = self.scalar("SELECT special_requests FROM Reservation WHERE reservation_id = :r", r=rid)
        self.assertEqual(stored, evil)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM Users"), self.users_at_start)

    # -- list_reservations -------------------------------------------------
    def test_list_reservations_includes_payment(self):
        before = len(queries.list_reservations(self.conn, 1))
        rid = self.book()
        rows = queries.list_reservations(self.conn, 1)
        self.assertEqual(rows[0]["reservation_id"], rid)  # newest date first
        self.assertEqual(rows[0]["restaurant_name"], "Morningside Cafe")
        self.assertEqual(rows[0]["payment_amount"], decimal.Decimal("5.00"))
        self.assertEqual(len(rows), before + 1)  # the new one plus the sample ones
        self.assertEqual(queries.list_reservations(self.conn, 9999), [])

    # -- cancel_reservation ------------------------------------------------
    def test_cancel_rules(self):
        rid = self.book()
        self.assertFalse(queries.cancel_reservation(self.conn, 2, rid))   # someone else's
        self.assertTrue(queries.cancel_reservation(self.conn, 1, rid))    # the owner
        self.assertFalse(queries.cancel_reservation(self.conn, 1, rid))   # already cancelled
        self.assertFalse(queries.cancel_reservation(self.conn, 1, 5001))  # completed and in the past
        self.assertFalse(queries.cancel_reservation(self.conn, 1, 999999))
        self.assertEqual(self.scalar("SELECT status FROM Reservation WHERE reservation_id = 5001"), "completed")

    # -- add_review --------------------------------------------------------
    def test_review_needs_a_completed_reservation(self):
        with self.assertRaises(queries.BookingError) as ctx:
            queries.add_review(self.conn, 2, 101, 5, "Never been")
        self.assertIn("completed reservation", str(ctx.exception))

    def test_review_once_per_restaurant(self):
        # User 1 already reviewed restaurant 101 in the sample data.
        with self.assertRaises(queries.BookingError) as ctx:
            queries.add_review(self.conn, 1, 101, 4, "Again")
        self.assertIn("already reviewed", str(ctx.exception))

    def test_review_success(self):
        self.conn.execute(text("""
            INSERT INTO Reservation VALUES (6000, '2026-10-01', '12:00', 2, 'completed', NULL, 1, 103, 1)"""))
        self.conn.commit()
        expected_id = self.scalar("SELECT MAX(Review_ID) FROM Writes_and_Receives_Review") + 1
        review_id = queries.add_review(self.conn, 1, 103, 4, "Nice")
        self.assertEqual(review_id, expected_id)
        row = self.conn.execute(text("SELECT rating, rating_text, user_id FROM Writes_and_Receives_Review "
                                     "WHERE review_id = " + str(expected_id))).one()
        self.assertEqual(tuple(row), (4, "Nice", 1))
        with self.assertRaises(queries.BookingError):
            queries.add_review(self.conn, 1, 103, 5, "Twice")

    # -- favorites ---------------------------------------------------------
    def test_favorites_add_list_remove(self):
        before = len(queries.list_favorites(self.conn, 1))
        new = self.scalar("SELECT MIN(Restaurant_ID) FROM Restaurant WHERE Restaurant_ID NOT IN "
                          "(SELECT Restaurant_ID FROM Favorites WHERE User_ID = 1)")
        queries.add_favorite(self.conn, 1, new)
        queries.add_favorite(self.conn, 1, new)  # twice: no crash, no duplicate
        rows = queries.list_favorites(self.conn, 1)
        self.assertEqual(len(rows), before + 1)
        self.assertEqual({"restaurant_id", "name", "cuisine", "restaurant_zip", "date_added"}, set(rows[0]))
        queries.remove_favorite(self.conn, 1, new)
        queries.remove_favorite(self.conn, 1, new)  # removing twice is fine
        self.assertEqual(len(queries.list_favorites(self.conn, 1)), before)

    def test_favorite_of_missing_restaurant(self):
        with self.assertRaises(queries.BookingError):
            queries.add_favorite(self.conn, 1, 9999)

    # -- recommend_restaurants ---------------------------------------------
    def test_recommendations_match_part2_query3(self):
        rows = queries.recommend_restaurants(self.conn, 1)
        self.assertTrue(rows)
        counts = [r["similar_users_who_favorited"] for r in rows]
        self.assertEqual(counts, sorted(counts, reverse=True))          # best match first
        mine = {r["restaurant_id"] for r in queries.list_favorites(self.conn, 1)}
        self.assertFalse(mine & {r["restaurant_id"] for r in rows})      # never recommend what I already favorited
        self.assertEqual(queries.recommend_restaurants(self.conn, 9999), [])


class ReadSideTests(DatabaseTestCase):
    """The read functions (written by Grace): users, cuisines, search, restaurant, tables, reviews, availability."""

    def test_list_users_and_get_user(self):
        users = queries.list_users(self.conn)
        self.assertEqual(len(users), self.users_at_start)
        self.assertEqual({"user_id", "name", "user_zip"}, set(users[0]))
        self.assertEqual([u["name"] for u in users], sorted(u["name"] for u in users))
        self.assertEqual(queries.get_user(self.conn, 1)["name"], "Elena Rostova")
        self.assertIsNone(queries.get_user(self.conn, 9999))

    def test_list_cuisines(self):
        cuisines = queries.list_cuisines(self.conn)
        self.assertEqual(cuisines, sorted(set(cuisines)))
        self.assertIn("Cafe", cuisines)

    def test_search_restaurants(self):
        every = queries.search_restaurants(self.conn)
        self.assertEqual(len(every), self.scalar("SELECT COUNT(*) FROM Restaurant"))
        self.assertTrue({"restaurant_id", "name", "cuisine", "min_price", "max_price", "restaurant_zip",
                         "open_now", "avg_rating", "num_reviews"} <= set(every[0]))
        cafes = queries.search_restaurants(self.conn, cuisine="Cafe")
        self.assertEqual({r["cuisine"] for r in cafes}, {"Cafe"})
        cheap = queries.search_restaurants(self.conn, max_price=20)
        self.assertTrue(all(r["max_price"] <= 20 for r in cheap))
        in_range = queries.search_restaurants(self.conn, zip_min=10001, zip_max=10010)
        self.assertTrue(in_range and all(10001 <= r["restaurant_zip"] <= 10010 for r in in_range))
        only_low = queries.search_restaurants(self.conn, zip_min=10025)
        self.assertTrue(only_low and all(r["restaurant_zip"] >= 10025 for r in only_low))
        only_high = queries.search_restaurants(self.conn, zip_max=10002)
        self.assertTrue(only_high and all(r["restaurant_zip"] <= 10002 for r in only_high))
        pizza = [r["name"] for r in queries.search_restaurants(self.conn, name="PIZZERIA")]  # case-insensitive
        self.assertIn("Soho Pizzeria", pizza)
        self.assertTrue(all("pizzeria" in n.lower() for n in pizza))
        self.assertEqual(len(queries.search_restaurants(self.conn, name="no such place")), 0)
        # user text is a value, not SQL
        self.assertEqual(queries.search_restaurants(self.conn, name="x'; DROP TABLE Users; --"), [])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM Users"), self.users_at_start)
        open_now = queries.search_restaurants(self.conn, open_now=True)
        self.assertTrue(open_now and all(r["open_now"] for r in open_now))

    def test_get_restaurant(self):
        r = queries.get_restaurant(self.conn, 101)
        self.assertEqual((r["name"], r["num_reviews"]), ("Morningside Cafe", 1))
        self.assertEqual(float(r["avg_rating"]), 5.0)
        self.assertIsNone(queries.get_restaurant(self.conn, 9999))

    def test_restaurant_without_reviews_still_shows(self):
        self.conn.execute(text("DELETE FROM Writes_and_Receives_Review WHERE restaurant_id = 101"))
        self.conn.commit()
        r = queries.get_restaurant(self.conn, 101)
        self.assertEqual(r["num_reviews"], 0)
        self.assertIsNone(r["avg_rating"])

    def test_list_tables_and_reviews(self):
        tables = queries.list_tables(self.conn, 101)
        self.assertGreaterEqual(len(tables), 3)                                    # several kinds of table
        self.assertGreaterEqual(len({t["seating_type"] for t in tables}), 3)
        reviews = queries.list_reviews(self.conn, 101)
        self.assertEqual({"reviewer_name", "rating", "rating_text", "review_date"}, set(reviews[0]))

    def test_find_available_tables(self):
        rows = queries.find_available_tables(self.conn, FUTURE, datetime.time(12, 0), 4)
        self.assertTrue(rows and all(r["capacity"] >= 4 for r in rows))
        self.assertTrue({"restaurant_id", "table_no", "capacity", "seating_type"} <= set(rows[0]))
        # A restaurant can offer several kinds of table at once.
        by_restaurant = {}
        for r in rows:
            by_restaurant.setdefault(r["restaurant_id"], set()).add(r["seating_type"])
        self.assertTrue(any(len(types) >= 2 for types in by_restaurant.values()))
        # Taken tables disappear: book one, and it must vanish from the list.
        first = rows[0]
        queries.create_reservation(self.conn, 1, first["restaurant_id"], first["table_no"], FUTURE,
                                   datetime.time(12, 0), 4, None, "Cash")
        again = queries.find_available_tables(self.conn, FUTURE, datetime.time(12, 0), 4)
        self.assertNotIn((first["restaurant_id"], first["table_no"]),
                         [(r["restaurant_id"], r["table_no"]) for r in again])

    def test_find_available_tables_only_for_the_restaurants_asked_about(self):
        rows = queries.find_available_tables(self.conn, FUTURE, datetime.time(12, 0), 2, restaurant_ids=[103, 104])
        self.assertTrue(rows and {r["restaurant_id"] for r in rows} <= {103, 104})
        self.assertEqual(queries.find_available_tables(self.conn, FUTURE, datetime.time(12, 0), 2, restaurant_ids=[]), [])

    def test_find_available_tables_respects_the_ten_minute_buffer(self):
        queries.create_reservation(self.conn, 1, 103, 1, FUTURE, datetime.time(12, 0), 4, None, "Cash")
        def table1_free_at(hour, minute):
            rows = queries.find_available_tables(self.conn, FUTURE, datetime.time(hour, minute), 4, restaurant_ids=[103])
            return any(r["table_no"] == 1 for r in rows)
        self.assertFalse(table1_free_at(12, 1))
        self.assertFalse(table1_free_at(12, 9))
        self.assertFalse(table1_free_at(11, 55))
        self.assertTrue(table1_free_at(12, 10))
        self.assertTrue(table1_free_at(11, 50))

    def test_find_available_tables_overnight_and_closed_hours(self):
        late = queries.find_available_tables(self.conn, FUTURE, datetime.time(0, 30), 4, restaurant_ids=[107])
        self.assertTrue(late)                       # Soho Pizzeria is open until 01:00
        closed = queries.find_available_tables(self.conn, FUTURE, datetime.time(3, 0), 4, restaurant_ids=[107])
        self.assertEqual(closed, [])


if __name__ == "__main__":
    unittest.main()
