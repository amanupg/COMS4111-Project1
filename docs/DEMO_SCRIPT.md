# Demo script for the 15-minute mentor meeting (Fri Nov 20 or Mon Nov 23)

Before the meeting: open the Cloud Run URL in a private window (no Google sign-in), confirm every page loads, and have
the code open in an editor in case your mentor asks to see it. Share your screen in Chrome.

1. **Home.** Pick a user (shows the "who are you" step).
2. **Find restaurants.** Search by name, then filter by cuisine, max price, a zip code range (for example 10001 to 10030) and open now. Point out the average rating column. Open one restaurant: its several table types, reviews.
3. **Check availability on the same page.** Fill in date, time and party size and search again: each restaurant lists its free tables (different seating types). Try one with no results. Mention the 10-minute buffer and that double booking is prevented by the database.
4. **Book and pay.** Click Book next to a table. Point out that the deposit is fixed (half the minimum price times the party size), nobody types it. Then show the booking under "My reservations" with its payment.
5. **Try to double book** the same table at the same time, and then 5 minutes later: show the friendly error both times.
6. **Cancel** the reservation. Show it no longer blocks the table.
7. **Review.** Add a review as a user who has a completed reservation. Try as one without: show the rule.
8. **Favorites** then **Recommendations.** Show the recommendations change after favoriting something shared with other users.
9. **Code tour (if asked):** the query behind one page, and where parameters are bound (SQL injection safety).

Prepare data so each step has something to show (for example future dates, one user with no reservation yet).
