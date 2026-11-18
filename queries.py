"""All database access for the restaurant reservation app lives in this file.
THIS FILE IS FOR YOU AND YOUR TEAMMATE TO WRITE. The web pages (server.py and
templates/) already call every function below; each one is a stub that raises
NotImplementedError until you replace it with real SQL. While a stub is
unimplemented, its page shows a friendly "not implemented yet" message instead
of crashing, so you can build and test one function at a time.

Ground rules (from the Part 3 assignment)
-----------------------------------------
* No ORM. Write SQL as strings, wrapped in text(), and run it with conn.execute.
* NEVER put user input into the SQL string (no f-strings, no +, no %).
  Use bound parameters instead:

      conn.execute(text("SELECT name FROM Restaurant WHERE restaurant_id = :rid"),
                   {"rid": restaurant_id})

  This is what prevents SQL injection, and it is part of your grade.
* Queries that change data must be followed by conn.commit(). For several
  statements that must succeed or fail together (see create_reservation),
  commit ONCE at the end. If anything raises, server.py rolls back for you.
* Return plain Python data (lists of dicts) so the templates stay simple.
  rows_to_dicts() below turns a SQLAlchemy result into that format.
* Table names come from your Part 2 schema: Users, Restaurant, RestaurantTable,
  Reservation, Payment, Writes_and_Receives_Review, Favorites.

Relationship to the course: each function says which lecture idea it uses.
"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text  # noqa: F401  (you will use this in every function)
from sqlalchemy.exc import IntegrityError  # noqa: F401  (useful in the write functions)


class BookingError(Exception):
    """Raise this for a rule violation you want shown to the user, e.g.
    "That table is already booked at that time." The page displays str(error)
    as a normal message instead of an error screen."""


def rows_to_dicts(result):
    """Convert a SQLAlchemy result into a list of dicts keyed by column name."""
    return [dict(row._mapping) for row in result]


def todo(name):
    raise NotImplementedError(f"queries.{name} has not been written yet")


# ---------------------------------------------------------------------------
# Who is using the app
# ---------------------------------------------------------------------------

def list_users(conn):
    """All users, for the "who are you?" dropdown on the home page.

    Return: list of dicts with keys user_id, name, user_zip. Order by name.
    Course idea: a basic SELECT with ORDER BY.
    """
    result = conn.execute(text("SELECT user_id, name, user_zip FROM Users " \
    "ORDER BY name"))
    return rows_to_dicts(result)


def get_user(conn, user_id):
    """One user, or None if there is no such user.

    Return: dict with keys user_id, name, email, phone, user_zip, or None.
    """
    user_result = conn.execute(text("SELECT * FROM Users WHERE user_id = :search_user"), 
                          {"search_user": user_id})
    rows = rows_to_dicts(user_result)
    return rows[0] if rows else None

# ---------------------------------------------------------------------------
# Finding restaurants  (proposal feature 1)
# ---------------------------------------------------------------------------

def list_cuisines(conn):
    """Distinct cuisines, for the search dropdown. Return a list of strings,
    sorted. Course idea: SELECT DISTINCT."""
    cuisines = conn.execute(text("SELECT DISTINCT Cuisine FROM Restaurant ORDER BY Cuisine"))
    return [row[0] for row in cuisines]


def search_restaurants(conn, name=None, cuisine=None, max_price=None, zip_min=None, zip_max=None, open_now=False):
    """PLACEHOLDER (changed after our team meeting; the old version is in git history, commit 34adfb2).

    Restaurants matching the filters, each with its average rating.

    Arguments (None / False means "no filter"):
      name      part of the restaurant name, case-insensitive ("pizza" finds "Joe's Pizza")  <- NEW
      cuisine   exact cuisine, e.g. "Italian"
      max_price integer; keep restaurants whose Max_price is <= this
      zip_min   integer; keep restaurants with Restaurant_zip >= this                       <- NEW
      zip_max   integer; keep restaurants with Restaurant_zip <= this                       <- NEW
                (either may be None: only a lower or only an upper bound)
      open_now  if True, keep restaurants with Open_now = TRUE

    Return: list of dicts with keys restaurant_id, name, cuisine, min_price, max_price,
    restaurant_zip, open_now, avg_rating (None if no reviews), num_reviews.
    Best-rated first, then by name. """

    filter_search = conn.execute(text("""SELECT R.Restaurant_ID, R.Name, R.Cuisine, R.Min_price, R.Max_price,
      R.Restaurant_zip, R.Open_now, AVG(W.Rating) AS avg_rating, COUNT(W.Rating) AS num_reviews
      FROM Restaurant R
      LEFT JOIN Writes_and_Receives_Review W ON W.Restaurant_ID = R.Restaurant_ID 
      WHERE (:name is NULL OR R.Name ILIKE '%' || :name || '%') AND ():cuisine is NULL OR R.Cuisine = :cuisine)
      AND (:max_price is NULL OR R.Max_price <= :max_price) AND (:zip_min is NULL OR R.Restaurant_zip >= :zip_min) 
      AND (:zip_max is NULL OR R.Restaurant_zip <= :zip_max) AND (NOT :open_now OR R.Open_now = 1)
      GROUP BY R.Restaurant_ID, R.Name, R.Cuisine, R.Min_price, R.Max_price, R.Open_now, R.Restaurant_zip
      ORDER BY avg_rating DESC NULLS LAST, R.Name ASC"""), 
      {"cuisine": cuisine, "max_price": max_price, "zip_min": zip_min, "zip_max": zip_max, "open_now": open_now})
    return rows_to_dicts(filter_search)


def get_restaurant(conn, restaurant_id):
    """One restaurant with its average rating, or None.

    Return: dict with keys restaurant_id, name, cuisine, min_price, max_price,
    open_time, close_time, open_now, restaurant_zip, avg_rating, num_reviews.
    """
    "Writes_and_Receives_Review (Review_ID, User_ID, Restaurant_ID, Review_Date, Rating, Rating_text)"
    restaurant_search = conn.execute(text("""SELECT R.Restaurant_ID, R.name, R.cuisine, R.min_price, R.max_price,
    R.open_time, R.close_time, R.open_now, R.restaurant_zip, AVG(W.Rating) AS avg_rating, COUNT(W.Rating) AS num_reviews
    FROM Restaurant R 
    LEFT JOIN Writes_and_Receives_Review W ON R.Restaurant_ID = W.Restaurant_ID 
    WHERE R.Restaurant_ID = :search_restaurant
    GROUP BY R.Restaurant_ID, R.name, R.cuisine, R.min_price, R.max_price,
    R.open_time, R.close_time, R.open_now, R.restaurant_zip"""),
    {"search_restaurant": restaurant_id})
    restaurant_rows = rows_to_dicts(restaurant_search)
    return restaurant_rows[0] if restaurant_rows else None


def list_tables(conn, restaurant_id):
    """The tables of one restaurant (the weak entity RestaurantTable).

    Return: list of dicts with keys table_no, capacity, seating_type, ordered
    by table_no.
    """
    restaurant_tables = conn.execute(text("""SELECT * FROM RestaurantTable T 
    WHERE T.Restaurant_ID = :given_restaurant_id ORDER BY T.Table_no"""), 
    {"given_restaurant_id": restaurant_id})
    table_rows = rows_to_dicts(restaurant_tables)
    return table_rows


def list_reviews(conn, restaurant_id):
    """Reviews written about one restaurant, newest first.

    Return: list of dicts with keys reviewer_name, rating, rating_text,
    review_date. Hint: join the review table to Users to show the name.
    """
    user_reviews = conn.execute(text("""SELECT U.Name AS reviewer_name, R.Rating AS rating, 
     R.Rating_text, R.Review_Date AS review_date
     FROM Writes_and_Receives_Review R
     JOIN Users U ON U.User_ID = R.User_ID WHERE R.Restaurant_ID = :reviewed_restaurant_id 
     ORDER BY R.Review_Date DESC"""), 
     {"reviewed_restaurant_id": restaurant_id})
    review_rows = rows_to_dicts(user_reviews)
    return review_rows


# ---------------------------------------------------------------------------
# Availability  (proposal feature 2)
# ---------------------------------------------------------------------------

def find_available_tables(conn, res_date, res_time, party_size, restaurant_ids=None):
    """Tables that are free at the requested date and time and big enough. The Find restaurants page
    calls this ONCE with the ids of the restaurants it is showing, then displays each restaurant's
    free tables under it. A restaurant can now have several kinds of table (Booth, Bar, Window Seat...).

    Arguments: res_date (datetime.date), res_time (datetime.time), party_size (int),
    restaurant_ids (list of ints, or None = all restaurants).                                  <- CHANGED (was cuisine)

    Return: list of dicts with keys restaurant_id, restaurant_name, table_no, capacity, seating_type.
    Order by restaurant_id, then capacity, then table_no.

    Rules
      * Capacity must be at least party_size.
      * The restaurant must be open at res_time (some close after midnight: Close_time < Open_time).
      * NEW 10-MINUTE BUFFER: a table is NOT available if it has a reservation (status not 'cancelled')
        on the same date whose time is less than BOOKING_BUFFER_MINUTES away from res_time. So with a
        booking at 12:00, a request for 12:01 is refused and 12:10 is fine.
    """
    buffer_time_seconds = BOOKING_BUFFER_MINUTES * 60 #10 minutes buffer time 
    available_tables = conn.execute(text("""WITH Taken_Tables AS (SELECT R.Restaurant_ID, R.Table_No FROM Reservation R
     WHERE R.Res_Date = :res_date AND R.Status != 'cancelled' AND ABS(EXTRACT(EPOCH FROM(R.Res_Time - :res_time))) < :buffer_time)
     SELECT R.Restaurant_ID, R.Name as restaurant_name, T.Table_No, T.Capacity, T.Seating_type
     FROM Restaurant R
     JOIN RestaurantTable T ON R.Restaurant_ID = T.Restaurant_ID
     LEFT JOIN Taken_Tables as TB ON R.Restaurant_ID = TB.Restaurant_ID AND T.Table_No = TB.Table_No
     WHERE T.Capacity >= :party_size AND ((R.Open_time <= R.Close_time AND R.Open_time <= :res_time AND :res_time < R.Close_time)
     OR (R.Open_time > R.Close_time AND (:res_time >= R.Open_time OR :res_time < R.Close_time))) 
     AND (:restaurant_ids is NULL OR R.Restaurant_ID IN :restaurant_ids) AND TB.Table_No IS NULL 
     ORDER BY R.Name, T.Capacity, T.Table_No"""),
     {"restaurant_ids": tuple(restaurant_ids) if restaurant_ids else None, "party_size": party_size, "cuisine": cuisine, "res_date": res_date, "res_time": res_time})
    found_available_tables = rows_to_dicts(available_tables)
    return found_available_tables


# ---------------------------------------------------------------------------
# Small helpers used by the write functions below
# ---------------------------------------------------------------------------

BOOKING_BUFFER_MINUTES = 10   # two reservations for one table must be at least this far apart
DEPOSIT_RATE = Decimal("0.5")  # deposit = DEPOSIT_RATE x the restaurant's Min_price x party size


def deposit_amount(min_price, party_size):
    """The fixed deposit: half of the restaurant's minimum price, times the party size, in dollars."""
    return (Decimal(min_price) * DEPOSIT_RATE * party_size).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


NYC_NOW = "(NOW() AT TIME ZONE 'America/New_York')"  # Cloud Run and Postgres may run in UTC; restaurants are in NYC


def _constraint_name(error):
    """Name of the database constraint behind an IntegrityError, or None."""
    return getattr(getattr(error.orig, "diag", None), "constraint_name", None)


def _next_id(conn, table, column):
    """Next free integer id for a table whose primary key is a plain INTEGER.

    MAX+1 is safe here only because two people booking at the same instant would
    compute the same id and the PRIMARY KEY would reject the second insert
    (an IntegrityError). The callers catch that and retry with a fresh id.
    """
    # table and column are fixed strings from this file, never user input.
    return conn.execute(text(f"SELECT COALESCE(MAX({column}), 0) + 1 FROM {table}")).scalar_one()


# ---------------------------------------------------------------------------
# Booking and payment  (proposal feature 3)
# ---------------------------------------------------------------------------

def create_reservation(conn, user_id, restaurant_id, table_no, res_date, res_time,
                       party_size, special_requests, payment_method):
    """Book a table AND record its deposit payment, as ONE transaction.

    Arguments: user_id, restaurant_id, table_no (ints), res_date (datetime.date), res_time (datetime.time),
    party_size (int), special_requests (str or None), payment_method (str).
    There is NO amount argument any more (<- CHANGED): the user no longer types a deposit.

    Return: the new reservation_id (int).

    Rules
      * DEPOSIT: read the restaurant's Min_price and insert the Payment with
        deposit_amount(min_price, party_size) (defined above: half of Min_price x party size).
      * Keep the old checks: table exists, capacity >= party_size, restaurant open at res_time.
      * NEW 10-MINUTE BUFFER: refuse (raise BookingError) if the same table has a non-cancelled
        reservation on the same date less than BOOKING_BUFFER_MINUTES away from res_time.
        The unique index No_Double_Booking only catches the EXACT same time, so this needs its own check.
        Two people clicking at once could both pass a plain check, so lock the table row first inside the
        transaction:  SELECT ... FROM RestaurantTable WHERE Restaurant_ID = :r AND Table_No = :t FOR UPDATE
        and then run the buffer check.
      * Insert Reservation then Payment in the same transaction, commit once, retry on a primary-key clash.
    """
    table = conn.execute(text(""" SELECT T.Capacity, R.Min_price,
    ((R.Open_time <= R.Close_time AND :res_time >= R.Open_time AND :res_time < R.Close_time)
    OR (R.Open_time > R.Close_time AND (:res_time >= R.Open_time OR :res_time < R.Close_time))) AS is_open
    FROM RestaurantTable T
    JOIN Restaurant R ON R.Restaurant_ID = T.Restaurant_ID
    WHERE T.Restaurant_ID = :restaurant_id AND T.Table_No = :table_no
    FOR UPDATE"""), {"restaurant_id": restaurant_id, "table_no": table_no, "res_time": res_time}).mappings().first()
    
    if table is None:
      raise BookingError("That table does not exist.")
    if table["capacity"] < party_size:
      raise BookingError(f"That table seats {table['capacity']}, but your party has {party_size}.")
    if not table["is_open"]:
      raise BookingError("The restaurant is not open at that time.")

    buffer_time = 60 * BOOKING_BUFFER_MINUTES
    time_conflict = conn.execute(text("""SELECT 1 FROM RESERVATION WHERE Restaurant_ID = :restaurant_id
    AND table_no = :table_no AND Res_date = :res_date AND Status != cancelled AND 
    ABS(EXTRACT(EPOCH FROM(R.Res_Time - :res_time))) < :buffer_time"""), 
    {"restaurant_id": restaurant_id, "table_no": table_no, "res_date": res_date, "res_time": res_time, "buffer_time": buffer_time}).first()

    if time_conflict: 
      raise BookingError("The table is not available at this time.")

    deposited_money = deposit_amount(table["min_price"], party_size)
    for attempt in range(3):  # retry only if another booking took our id a split second earlier
      try:
        reservation_id = _next_id(conn, "Reservation", "Reservation_ID")
        conn.execute(text("""INSERT INTO Reservation (Reservation_ID, Res_Date, Res_Time, Party_size, Status,
        Special_requests, User_ID, Restaurant_ID, Table_No)
        VALUES (:rid, :res_date, :res_time, :party_size, 'booked',
        :special_requests, :user_id, :restaurant_id, :table_no)"""),
        {"rid": reservation_id, "res_date": res_date, "res_time": res_time,
        "party_size": party_size, "special_requests": special_requests,
        "user_id": user_id, "restaurant_id": restaurant_id, "table_no": table_no})

        payment_id = _next_id(conn, "Payment", "Payment_ID")
        conn.execute(text("""INSERT INTO Payment (Payment_ID, Amount, Method, Paid_at, Reservation_ID)
        VALUES (:pid, :amount, :method, """ + NYC_NOW + """, :rid)"""),
        {"pid": payment_id, "amount": amount, "method": payment_method, "rid": reservation_id})
        conn.commit()
        return reservation_id

      except IntegrityError as error:
        conn.rollback()
        name = _constraint_name(error)
        if name == "no_double_booking":
          raise BookingError("That table is already booked at that date and time.")
        if name in ("reservation_pkey", "payment_pkey") and attempt < 2:
          continue  # someone else just used our id; pick the next one
        if name == "reservation_user_id_fkey":
          raise BookingError("That user does not exist.")
        raise BookingError("The booking could not be saved. Please try again.")
    raise BookingError("The booking could not be saved. Please try again.")

# ---------------------------------------------------------------------------
# A user's reservations  (proposal overview: view and cancel)
# ---------------------------------------------------------------------------

def list_reservations(conn, user_id):
    """All reservations of one user with restaurant and payment details,
    newest first. The payment is an outer join in case a reservation has none."""
    result = conn.execute(text("""
        SELECT V.Reservation_ID AS reservation_id, V.Restaurant_ID AS restaurant_id,
               R.Name AS restaurant_name, V.Table_No AS table_no, V.Res_Date AS res_date,
               V.Res_Time AS res_time, V.Party_size AS party_size, V.Status AS status,
               V.Special_requests AS special_requests,
               P.Amount AS payment_amount, P.Method AS payment_method
        FROM Reservation V
        JOIN Restaurant R ON R.Restaurant_ID = V.Restaurant_ID
        LEFT JOIN Payment P ON P.Reservation_ID = V.Reservation_ID
        WHERE V.User_ID = :user_id
        ORDER BY V.Res_Date DESC, V.Res_Time DESC, V.Reservation_ID DESC"""),
        {"user_id": user_id})
    return rows_to_dicts(result)


def cancel_reservation(conn, user_id, reservation_id):
    """Cancel an upcoming reservation that belongs to this user.

    Return True if a reservation was cancelled, False if nothing matched.
    All the rules sit in the WHERE clause of ONE statement, so there is no
    gap between checking and changing: it must be this user's, still 'booked',
    and not yet started (compared in New York time).
    """
    result = conn.execute(text("""
        UPDATE Reservation
        SET Status = 'cancelled'
        WHERE Reservation_ID = :reservation_id
          AND User_ID = :user_id
          AND Status = 'booked'
          AND (Res_Date + Res_Time) > """ + NYC_NOW),
        {"reservation_id": reservation_id, "user_id": user_id})
    conn.commit()
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Reviews  (proposal feature 4)
# ---------------------------------------------------------------------------

def add_review(conn, user_id, restaurant_id, rating, rating_text):
    """Add a review by this user for this restaurant; return the new review_id.

    Rules: only after a COMPLETED reservation at that restaurant (a rule the
    schema cannot express, so it is checked here), and at most one review per
    user per restaurant (the UNIQUE constraint enforces it).
    """
    visited = conn.execute(text("""
        SELECT EXISTS (SELECT 1 FROM Reservation
                       WHERE User_ID = :user_id AND Restaurant_ID = :restaurant_id
                         AND Status = 'completed')"""),
        {"user_id": user_id, "restaurant_id": restaurant_id}).scalar_one()
    if not visited:
        raise BookingError("You can review a restaurant only after a completed reservation there.")

    for attempt in range(3):
        try:
            review_id = _next_id(conn, "Writes_and_Receives_Review", "Review_ID")
            conn.execute(text("""
                INSERT INTO Writes_and_Receives_Review
                    (Review_ID, User_ID, Restaurant_ID, Review_Date, Rating, Rating_text)
                VALUES (:review_id, :user_id, :restaurant_id, """ + NYC_NOW + """::date, :rating, :rating_text)"""),
                {"review_id": review_id, "user_id": user_id, "restaurant_id": restaurant_id,
                 "rating": rating, "rating_text": rating_text})
            conn.commit()
            return review_id
        except IntegrityError as error:
            conn.rollback()
            name = _constraint_name(error)
            if name == "writes_and_receives_review_user_id_restaurant_id_key":
                raise BookingError("You have already reviewed this restaurant.")
            if name == "writes_and_receives_review_pkey" and attempt < 2:
                continue
            raise BookingError("The review could not be saved. Please try again.")
    raise BookingError("The review could not be saved. Please try again.")


# ---------------------------------------------------------------------------
# Favorites  (proposal feature 5)
# ---------------------------------------------------------------------------

def list_favorites(conn, user_id):
    """The restaurants this user has favorited, newest first."""
    result = conn.execute(text("""
        SELECT R.Restaurant_ID AS restaurant_id, R.Name AS name, R.Cuisine AS cuisine,
               R.Restaurant_zip AS restaurant_zip, F.Date_Added AS date_added
        FROM Favorites F
        JOIN Restaurant R ON R.Restaurant_ID = F.Restaurant_ID
        WHERE F.User_ID = :user_id
        ORDER BY F.Date_Added DESC, R.Name"""),
        {"user_id": user_id})
    return rows_to_dicts(result)


def add_favorite(conn, user_id, restaurant_id):
    """Favorite a restaurant. Adding one that is already a favorite does
    nothing (ON CONFLICT on the primary key), so it never crashes."""
    try:
        conn.execute(text("""
            INSERT INTO Favorites (User_ID, Restaurant_ID, Date_Added)
            VALUES (:user_id, :restaurant_id, """ + NYC_NOW + """::date)
            ON CONFLICT (User_ID, Restaurant_ID) DO NOTHING"""),
            {"user_id": user_id, "restaurant_id": restaurant_id})
        conn.commit()
    except IntegrityError:
        conn.rollback()
        raise BookingError("That restaurant does not exist.")


def remove_favorite(conn, user_id, restaurant_id):
    """Un-favorite a restaurant (nothing happens if it was not a favorite)."""
    conn.execute(text("""
        DELETE FROM Favorites WHERE User_ID = :user_id AND Restaurant_ID = :restaurant_id"""),
        {"user_id": user_id, "restaurant_id": restaurant_id})
    conn.commit()


# ---------------------------------------------------------------------------
# Recommendations  (proposal feature 6)
# ---------------------------------------------------------------------------

def recommend_restaurants(conn, user_id):
    """Restaurants this user might like, based on users with similar taste.

    Your Part 2 query 3 with the user id as a bound parameter: other users who
    share a favorite with this user (fb), and their other favorites (fr),
    excluding restaurants this user already visited or favorited.
    """
    result = conn.execute(text("""
        SELECT r.Restaurant_ID AS restaurant_id, r.Name AS name, r.Cuisine AS cuisine,
               COUNT(DISTINCT fb.User_ID) AS similar_users_who_favorited
        FROM Favorites fa
        JOIN Favorites fb ON fb.Restaurant_ID = fa.Restaurant_ID AND fb.User_ID <> fa.User_ID
        JOIN Favorites fr ON fr.User_ID = fb.User_ID AND fr.Restaurant_ID <> fa.Restaurant_ID
        JOIN Restaurant r ON r.Restaurant_ID = fr.Restaurant_ID
        WHERE fa.User_ID = :user_id
          AND NOT EXISTS (SELECT 1 FROM Reservation res
                          WHERE res.User_ID = fa.User_ID
                            AND res.Restaurant_ID = r.Restaurant_ID
                            AND res.Status = 'completed')
          AND NOT EXISTS (SELECT 1 FROM Favorites mine
                          WHERE mine.User_ID = fa.User_ID
                            AND mine.Restaurant_ID = r.Restaurant_ID)
        GROUP BY r.Restaurant_ID, r.Name, r.Cuisine
        ORDER BY similar_users_who_favorited DESC, r.Name"""),
        {"user_id": user_id})
    return rows_to_dicts(result)
