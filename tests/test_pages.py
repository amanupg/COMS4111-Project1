"""Tests for the web layer. They replace the functions in queries.py with fakes,
so no database is needed: they check that pages render, that bad input is
rejected BEFORE it reaches any query, and that user input is passed through as
plain values."""

import datetime
from decimal import Decimal
import os
import unittest
from unittest.mock import MagicMock, patch

import queries
import server

FAKE_USER = {"user_id": 1, "name": "Elena Rostova", "email": "e@x", "phone": "1", "user_zip": 10027}
FAKE_RESTAURANT = {"restaurant_id": 101, "name": "Morningside Cafe", "cuisine": "Cafe", "min_price": 5,
                   "max_price": 20, "open_time": "06:30", "close_time": "16:00", "open_now": True,
                   "restaurant_zip": 10027, "avg_rating": 4.5, "num_reviews": 2}


class PageTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"DB_USER": "u", "DB_PASSWORD": "p"}, clear=True)
        self.env.start()
        server.get_engine.cache_clear()
        engine = MagicMock()
        self.engine_patch = patch.object(server, "get_engine", return_value=engine)
        self.engine_patch.start()
        self.client = server.app.test_client()

    def tearDown(self):
        self.engine_patch.stop()
        self.env.stop()

    def fake(self, name, value=None, **kwargs):
        mock = MagicMock(return_value=value, **kwargs)
        return patch.object(queries, name, mock), mock

    def login(self):
        with self.client.session_transaction() as s:
            s["user_id"], s["user_name"] = 1, "Elena Rostova"

    def test_home_lists_users(self):
        p, _ = self.fake("list_users", [FAKE_USER])
        with p:
            r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Elena Rostova", r.data)

    def test_unwritten_function_does_not_crash_home(self):
        p, _ = self.fake("list_users", side_effect=NotImplementedError("queries.list_users has not been written yet"))
        with p:
            r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Not written yet", r.data)

    def test_unwritten_function_gives_501_page_not_traceback(self):
        p, _ = self.fake("get_restaurant", side_effect=NotImplementedError("queries.get_restaurant has not been written yet"))
        with p:
            r = self.client.get("/restaurant/101")
        self.assertEqual(r.status_code, 501)
        self.assertIn(b"has not been written yet", r.data)

    def test_choose_user_sets_session(self):
        p, _ = self.fake("get_user", FAKE_USER)
        with p:
            r = self.client.post("/choose-user", data={"user_id": "1"})
        self.assertEqual(r.status_code, 302)
        with self.client.session_transaction() as s:
            self.assertEqual(s["user_id"], 1)

    def test_search_passes_values_as_parameters(self):
        p1, _ = self.fake("list_cuisines", ["Cafe"])
        p2, search = self.fake("search_restaurants", [])
        with p1, p2:
            r = self.client.get("/restaurants?name=cafe&cuisine=Cafe&max_price=30"
                                "&zip_min=10001&zip_max=10010&open_now=on")
        self.assertEqual(r.status_code, 200)
        kwargs = search.call_args.kwargs
        self.assertEqual((kwargs["name"], kwargs["cuisine"], kwargs["max_price"], kwargs["zip_min"],
                          kwargs["zip_max"], kwargs["open_now"]), ("cafe", "Cafe", 30, 10001, 10010, True))

    def test_zip_range_may_have_only_one_end(self):
        p1, _ = self.fake("list_cuisines", [])
        p2, search = self.fake("search_restaurants", [])
        with p1, p2:
            self.client.get("/restaurants?zip_min=10020")
        self.assertEqual((search.call_args.kwargs["zip_min"], search.call_args.kwargs["zip_max"]), (10020, None))

    def test_injection_text_is_not_executed_or_altered(self):
        evil = "x'; DROP TABLE Users; --"
        p1, _ = self.fake("list_cuisines", [])
        p2, search = self.fake("search_restaurants", [])
        with p1, p2:
            self.client.get("/restaurants", query_string={"cuisine": evil, "name": evil})
        self.assertEqual(search.call_args.kwargs["cuisine"], evil)  # passed as a plain value
        self.assertEqual(search.call_args.kwargs["name"], evil)

    def test_search_rejects_bad_numbers(self):
        for query in ("max_price=abc", "zip_min=5", "zip_max=99999", "max_price=-1",
                      "zip_min=10010&zip_max=10001"):
            r = self.client.get("/restaurants?" + query)
            self.assertEqual(r.status_code, 400, query)

    def test_availability_validates(self):
        p1, _ = self.fake("list_cuisines", [])
        with p1:
            for query in ("date=nope&time=19:00&party_size=2", "date=2099-12-01&time=25:99&party_size=2",
                          "date=2099-12-01&time=19:00&party_size=0", "date=2099-12-01&time=19:00",
                          "date=2020-01-01&time=19:00&party_size=2"):
                self.assertEqual(self.client.get("/restaurants?" + query).status_code, 400, query)

    def test_availability_page_is_gone(self):
        self.assertEqual(self.client.get("/availability").status_code, 404)

    def test_search_and_availability_on_one_page(self):
        restaurant = {"restaurant_id": 101, "name": "Morningside Cafe", "cuisine": "Cafe", "min_price": 5,
                      "max_price": 20, "restaurant_zip": 10027, "open_now": True, "avg_rating": None,
                      "num_reviews": 0}
        other = {**restaurant, "restaurant_id": 102, "name": "Fully Booked Place", "min_price": 10}
        free = [{"restaurant_id": 101, "table_no": 1, "capacity": 2, "seating_type": "Cafe Table"},
                {"restaurant_id": 101, "table_no": 2, "capacity": 4, "seating_type": "Bar"}]
        p1, _ = self.fake("list_cuisines", ["Cafe"])
        p2, _ = self.fake("search_restaurants", [restaurant, other])
        p3, find = self.fake("find_available_tables", free)
        with p1, p2, p3:
            r = self.client.get("/restaurants?date=2099-12-01&time=09:00&party_size=3")
        self.assertEqual(r.status_code, 200)
        args = find.call_args
        self.assertEqual(args.args[1:4], (datetime.date(2099, 12, 1), datetime.time(9, 0), 3))
        self.assertEqual(args.kwargs["restaurant_ids"], [101, 102])  # one call for all shown restaurants
        self.assertIn(b"Cafe Table, seats 2", r.data)
        self.assertIn(b"Bar, seats 4", r.data)          # several table types for one restaurant
        self.assertIn(b"No table free then", r.data)    # restaurant 102 has none
        self.assertIn(b"deposit $7.50", r.data)         # half of $5 x 3 people
        self.assertIn(b"deposit", r.data)

    def test_unwritten_availability_does_not_claim_fully_booked(self):
        restaurant = {"restaurant_id": 101, "name": "Morningside Cafe", "cuisine": "Cafe", "min_price": 5,
                      "max_price": 20, "restaurant_zip": 10027, "open_now": True, "avg_rating": None,
                      "num_reviews": 0}
        p1, _ = self.fake("list_cuisines", [])
        p2, _ = self.fake("search_restaurants", [restaurant])
        p3, _ = self.fake("find_available_tables", side_effect=NotImplementedError("queries.find_available_tables"))
        with p1, p2, p3:
            r = self.client.get("/restaurants?date=2099-12-01&time=09:00&party_size=2")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b"No table free then", r.data)

    def test_deposit_is_half_min_price_times_party(self):
        from decimal import Decimal
        self.assertEqual(queries.deposit_amount(30, 4), Decimal("60.00"))
        self.assertEqual(queries.deposit_amount(15, 1), Decimal("7.50"))
        self.assertEqual(queries.deposit_amount(5, 3), Decimal("7.50"))
        self.assertEqual(queries.deposit_amount(7, 1), Decimal("3.50"))

    def book_form(self, **overrides):
        data = {"restaurant_id": "101", "table_no": "1", "date": "2099-01-01", "time": "19:00",
                "party_size": "2", "special_requests": "", "payment_method": "Cash"}
        data.update(overrides)
        return data

    def test_booking_requires_user(self):
        r = self.client.post("/book", data=self.book_form())
        self.assertEqual(r.status_code, 302)  # sent to the home page to pick a user

    def test_booking_validation(self):
        self.login()
        p, create = self.fake("create_reservation", 5001)
        with p:
            for bad in ({"date": "2020-01-01"}, {"payment_method": "Bitcoin"},
                        {"party_size": "100"}, {"special_requests": "x" * 501}):
                r = self.client.post("/book", data=self.book_form(**bad))
                self.assertEqual(r.status_code, 400, bad)
            create.assert_not_called()

    def test_booking_success(self):
        self.login()
        p, create = self.fake("create_reservation", 5001)
        with p:
            r = self.client.post("/book", data=self.book_form())
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/reservations"))
        self.assertEqual(create.call_args.args[1:3], (1, 101))
        self.assertEqual(len(create.call_args.args), 9)  # no amount: the deposit is computed by the query

    def test_user_cannot_set_the_deposit(self):
        self.login()
        p, create = self.fake("create_reservation", 5001)
        with p:
            self.client.post("/book", data=self.book_form(amount="0.01"))
        self.assertNotIn(Decimal("0.01"), create.call_args.args)

    def test_booking_error_is_shown_not_crashed(self):
        self.login()
        p, _ = self.fake("create_reservation", side_effect=queries.BookingError("That table is already booked."))
        with p:
            r = self.client.post("/book", data=self.book_form(), follow_redirects=True)
        self.assertIn(b"That table is already booked.", r.data)

    def test_review_validation(self):
        self.login()
        p, add = self.fake("add_review", 801)
        with p:
            for bad in ({"rating": "0"}, {"rating": "6"}, {"rating": "x"}):
                r = self.client.post("/review", data={"restaurant_id": "101", "rating": "5", **bad})
                self.assertEqual(r.status_code, 400)
            add.assert_not_called()
            ok = self.client.post("/review", data={"restaurant_id": "101", "rating": "5", "rating_text": "Great"})
        self.assertEqual(ok.status_code, 302)

    def test_favorites_redirect_stays_on_site(self):
        self.login()
        p, _ = self.fake("add_favorite")
        with p:
            r = self.client.post("/favorites/add", data={"restaurant_id": "101", "next": "https://evil.example/"})
        self.assertTrue(r.headers["Location"].endswith("/favorites"))

    def test_cancel(self):
        self.login()
        p, cancel = self.fake("cancel_reservation", True)
        with p:
            r = self.client.post("/reservations/5001/cancel")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(cancel.call_args.args[1:], (1, 5001))

    def test_restaurant_page_renders(self):
        self.login()
        parts = [self.fake("get_restaurant", FAKE_RESTAURANT), self.fake("list_tables", [
            {"table_no": 1, "capacity": 2, "seating_type": "Cafe Table"}]),
            self.fake("list_reviews", []), self.fake("list_favorites", [])]
        for p, _ in parts:
            p.start()
        try:
            r = self.client.get("/restaurant/101")
        finally:
            for p, _ in parts:
                p.stop()
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Morningside Cafe", r.data)
        self.assertNotIn(b'name="amount"', r.data)          # nobody types a deposit any more
        self.assertIn(b"half of this restaurant", r.data)

    def test_unknown_restaurant_is_404(self):
        p, _ = self.fake("get_restaurant", None)
        with p:
            self.assertEqual(self.client.get("/restaurant/999").status_code, 404)

    def test_html_in_data_is_escaped(self):
        p, _ = self.fake("list_users", [{**FAKE_USER, "name": "<script>alert(1)</script>"}])
        with p:
            r = self.client.get("/")
        self.assertNotIn(b"<script>alert(1)</script>", r.data)

    def test_no_database_configured_shows_message_not_crash(self):
        with patch.dict(os.environ, {}, clear=True):
            r = self.client.get("/")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
