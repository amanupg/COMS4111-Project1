"""Tests for the web layer. They replace the functions in queries.py with fakes,
so no database is needed: they check that pages render, that bad input is
rejected BEFORE it reaches any query, and that user input is passed through as
plain values."""

import datetime
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
            r = self.client.get("/restaurants?cuisine=Cafe&max_price=30&zip=10027&open_now=on")
        self.assertEqual(r.status_code, 200)
        kwargs = search.call_args.kwargs
        self.assertEqual((kwargs["cuisine"], kwargs["max_price"], kwargs["zip_code"], kwargs["open_now"]),
                         ("Cafe", 30, 10027, True))

    def test_injection_text_is_not_executed_or_altered(self):
        evil = "x'; DROP TABLE Users; --"
        p1, _ = self.fake("list_cuisines", [])
        p2, search = self.fake("search_restaurants", [])
        with p1, p2:
            self.client.get("/restaurants", query_string={"cuisine": evil})
        self.assertEqual(search.call_args.kwargs["cuisine"], evil)  # passed as a plain value

    def test_search_rejects_bad_numbers(self):
        for query in ("max_price=abc", "zip=5", "zip=99999", "max_price=-1"):
            r = self.client.get("/restaurants?" + query)
            self.assertEqual(r.status_code, 400, query)

    def test_availability_validates(self):
        p1, _ = self.fake("list_cuisines", [])
        with p1:
            self.assertEqual(self.client.get("/availability?date=nope&time=19:00&party_size=2").status_code, 400)
            self.assertEqual(self.client.get("/availability?date=2026-12-01&time=25:99&party_size=2").status_code, 400)
            self.assertEqual(self.client.get("/availability?date=2026-12-01&time=19:00&party_size=0").status_code, 400)

    def test_availability_results(self):
        p1, _ = self.fake("list_cuisines", ["Cafe"])
        row = {"restaurant_id": 101, "name": "Morningside Cafe", "cuisine": "Cafe", "min_price": 5,
               "max_price": 20, "table_no": 1, "capacity": 2, "seating_type": "Cafe Table"}
        p2, find = self.fake("find_available_tables", [row])
        with p1, p2:
            r = self.client.get("/availability?date=2026-12-01&time=09:00&party_size=2")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Book this table", r.data)
        args = find.call_args.args
        self.assertEqual(args[1:4], (datetime.date(2026, 12, 1), datetime.time(9, 0), 2))

    def book_form(self, **overrides):
        data = {"restaurant_id": "101", "table_no": "1", "date": "2099-01-01", "time": "19:00",
                "party_size": "2", "special_requests": "", "payment_method": "Cash", "amount": "20"}
        data.update(overrides)
        return data

    def test_booking_requires_user(self):
        r = self.client.post("/book", data=self.book_form())
        self.assertEqual(r.status_code, 302)  # sent to the home page to pick a user

    def test_booking_validation(self):
        self.login()
        p, create = self.fake("create_reservation", 5001)
        with p:
            for bad in ({"date": "2020-01-01"}, {"payment_method": "Bitcoin"}, {"amount": "-5"},
                        {"amount": "abc"}, {"party_size": "100"}, {"special_requests": "x" * 501}):
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
