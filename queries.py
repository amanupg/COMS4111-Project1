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
    cuisines = conn.execute(text("SELECT DISTINCT Cuisine FROM Restaruant ORDER BY Cuisine"))
    return [row[0] for row in cuisines]


def search_restaurants(conn, cuisine=None, max_price=None, zip_code=None, open_now=False):
    """Restaurants matching the filters, each with its average rating.

    Arguments (any of them may be None / False, meaning "no filter"):
      cuisine    exact cuisine, e.g. "Italian"
      max_price  integer; keep restaurants whose Max_price is <= this
      zip_code   integer NYC zip; keep restaurants in exactly this zip
      open_now   if True, keep restaurants with Open_now = TRUE

    Return: list of dicts with keys restaurant_id, name, cuisine, min_price,
    max_price, restaurant_zip, open_now, avg_rating (None if no reviews),
    num_reviews. Best-rated first, then by name.

    Hints
      * Average rating needs a join to the review table plus GROUP BY. Use an
        OUTER join so restaurants with no reviews still appear.
      * Optional filters WITHOUT string-building: write each condition like
        (:cuisine IS NULL OR r.Cuisine = :cuisine) and pass None for "no
        filter". Or build the WHERE clause from a fixed list of condition
        strings you wrote yourself and bind only the values. Never splice a
        user-supplied value into the SQL text.
    Course idea: joins, outer joins, aggregation (GROUP BY / AVG / COUNT).
    """
    todo("search_restaurants")


def get_restaurant(conn, restaurant_id):
    """One restaurant with its average rating, or None.

    Return: dict with keys restaurant_id, name, cuisine, min_price, max_price,
    open_time, close_time, open_now, restaurant_zip, avg_rating, num_reviews.
    """
    "Writes_and_Receives_Review (Review_ID, User_ID, Restaurant_ID, Review_Date, Rating, Rating_text)"
    restaurant_search = conn.execute(text("""SELECT R.Restaurant_ID, R.name, R.cuisine, R.min_price, R.max_price,
    R.open_time, R.close_time, R.open_now, R.restaurant_zip, AVG(W.Rating) AS avg_rating, COUNT (W.Rating AS num_reviews)
    FROM Restaurant R 
    JOIN Writes_and_Receives_Review W ON R.RestaurantID = W.RestaurantID WHERE restaurant_id = :search_restaurant
    GROUP BY R.RestaurantID, R.name, R.cuisine, R.min_price, R.max_price,
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
     R.Rating_text, R.Review_Date AS date_added
     FROM Writes_and_Receives_Review R
     JOIN User U ON U.User_ID = R.User_ID WHERE R.Restaurant_ID = :reviewed_restaurant_id 
     ORDER BY R.Review_Date DESC"""), 
     {"reviewed_restaurant_id": restaurant_id})
    review_rows = rows_to_dicts(user_reviews)
    return review_rows


# ---------------------------------------------------------------------------
# Availability  (proposal feature 2)
# ---------------------------------------------------------------------------

def find_available_tables(conn, res_date, res_time, party_size, cuisine=None):
    """Tables that are free at the requested date and time and big enough.

    Arguments: res_date (datetime.date), res_time (datetime.time),
    party_size (int), cuisine (optional string, None = any).

    Return: list of dicts with keys restaurant_id, name, cuisine, min_price,
    max_price, table_no, capacity, seating_type. Order by restaurant name,
    then table_no.

    Rules to think about
      * Capacity must be at least party_size.
      * A table is "taken" if a reservation for that same table, date and time
        exists and its status is not 'cancelled' (this mirrors your
        No_Double_Booking unique index).
      * Optional extra: the time should fall inside the restaurant's
        Open_time..Close_time. Careful: some restaurants close after midnight
        (Close_time < Open_time), so a simple BETWEEN is wrong for those.
    Course idea: NOT EXISTS subquery (your Part 2 query 2 is the starting
    point), joins, parameters.
    """
    #Left join used: if table is not occupied in a left outer join, then Table_No is null
    available_tables = conn.execute(text("""WITH Taken_Tables AS (SELECT R.Restaurant_ID, R.Table_No FROM Reservation R
     WHERE R.Res_Date = :res_date AND R.Res_Time = :res_time AND R.Status != 'cancelled')
     SELECT R.Restaurant_ID, R.Name, R.Cuisine, R.Min_price, R.Max_price, T.Table_No, T.Capacity, T.Seating_type
     FROM Restaurant R
     JOIN RestaurantTable T ON R.Restaurant_ID = T.Restaurant_ID
     LEFT JOIN Taken_Tables as TB ON R.Restaurant_ID = TB.Restaurant_ID AND T.Table_No = TB.Table_No
     WHERE T.Capacity >= :party_size AND R.Open_time <= :res_time AND :res_time < R.Close_time AND (:cuisine is NULL OR R.Cuisine = :cuisine) AND TB.Table_No IS NULL 
     ORDER BY R.Name, T.Table_No"""),
     {"party_size": party_size, "cuisine": cuisine, "res_date": res_date, "res_time": res_time})
    found_available_tables = rows_to_dicts(available_tables)
    return found_available_tables

# ---------------------------------------------------------------------------
# Booking and payment  (proposal feature 3)
# ---------------------------------------------------------------------------

def create_reservation(conn, user_id, restaurant_id, table_no, res_date, res_time,
                       party_size, special_requests, payment_method, amount):
    """Book a table AND record its payment, as ONE transaction.

    Arguments: user_id, restaurant_id, table_no (ints), res_date
    (datetime.date), res_time (datetime.time), party_size (int),
    special_requests (str or None), payment_method (str), amount (Decimal).

    Return: the new reservation_id (int).

    Things you must decide and handle
      * Your primary keys are plain INTEGER, not auto-numbered. You can either
        compute the next id yourself (SELECT COALESCE(MAX(...), 0) + 1 ...
        inside the same transaction) or make a small schema change to
        GENERATED ALWAYS AS IDENTITY. Think about what goes wrong when two
        people book at the same moment, and write down your choice for the
        README.
      * Insert the Reservation first, then the Payment (Payment has a foreign
        key to Reservation). Commit once at the end so you never get a
        reservation without its payment.
      * New reservations should have status 'booked'.
      * The table must exist, be big enough (capacity >= party_size) and not
        already be booked at that date/time. The database will reject a
        double booking (unique index), which shows up as an IntegrityError:
        catch it and raise BookingError("That table is already booked ...").
      * Any rule you cannot express in the schema (party size vs capacity,
        opening hours) can be checked here with a SELECT before inserting.
    Course idea: INSERT, foreign keys, constraints doing the enforcement,
    transactions.
    """
    todo("create_reservation")


# ---------------------------------------------------------------------------
# A user's reservations  (proposal overview: view and cancel)
# ---------------------------------------------------------------------------

def list_reservations(conn, user_id):
    """All reservations of one user with restaurant and payment details.

    Return: list of dicts with keys reservation_id, restaurant_id,
    restaurant_name, table_no, res_date, res_time, party_size, status,
    special_requests, payment_amount, payment_method. Newest date first.
    Hint: join Reservation, Restaurant and Payment. Use an OUTER join to
    Payment in case a reservation has none.
    """
    todo("list_reservations")


def cancel_reservation(conn, user_id, reservation_id):
    """Cancel an upcoming reservation that belongs to this user.

    Return: True if a reservation was cancelled, False if nothing matched.

    Rule from your Part 1 constraints: only the user who made the reservation
    may cancel it, and only before it starts, and only if it is still
    'booked'. Put all of those conditions in the WHERE clause of one UPDATE
    (no separate read) and check how many rows it changed (result.rowcount).
    Remember conn.commit().
    Course idea: UPDATE with a WHERE clause.
    """
    todo("cancel_reservation")


# ---------------------------------------------------------------------------
# Reviews  (proposal feature 4)
# ---------------------------------------------------------------------------

def add_review(conn, user_id, restaurant_id, rating, rating_text):
    """Add a review by this user for this restaurant.

    Arguments: rating is an int 1..5, rating_text a str (may be empty).
    Return: the new review_id.

    Rules from your Part 1 constraints
      * At most one review per user per restaurant (your table has a UNIQUE
        constraint; catch IntegrityError and raise BookingError with a
        readable message).
      * A user may review a restaurant only after a COMPLETED reservation
        there. The schema cannot express that, so check it here (an EXISTS
        query), and raise BookingError if the user has none.
      * Use today's date for review_date (CURRENT_DATE).
      * Same primary-key-numbering decision as create_reservation.
    """
    todo("add_review")


# ---------------------------------------------------------------------------
# Favorites  (proposal feature 5)
# ---------------------------------------------------------------------------

def list_favorites(conn, user_id):
    """The restaurants this user has favorited.

    Return: list of dicts with keys restaurant_id, name, cuisine,
    restaurant_zip, date_added. Newest first.
    """
    todo("list_favorites")


def add_favorite(conn, user_id, restaurant_id):
    """Favorite a restaurant. Adding one that is already a favorite must not
    crash (check first, or use ON CONFLICT DO NOTHING on the primary key).
    Return None. Remember conn.commit()."""
    todo("add_favorite")


def remove_favorite(conn, user_id, restaurant_id):
    """Un-favorite a restaurant. Return None. Remember conn.commit()."""
    todo("remove_favorite")


# ---------------------------------------------------------------------------
# Recommendations  (proposal feature 6)
# ---------------------------------------------------------------------------

def recommend_restaurants(conn, user_id):
    """Restaurants this user might like, based on users with similar taste.

    Return: list of dicts with keys restaurant_id, name, cuisine,
    similar_users_who_favorited. Most-recommended first, then by name.

    This is your Part 2 query 3 with the hard-coded 1 replaced by a bound
    parameter (:uid). It uses a self-join on Favorites, NOT EXISTS, GROUP BY.
    """
    todo("recommend_restaurants")
