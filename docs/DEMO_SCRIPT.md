# Demo script for the 15-minute mentor meeting (Fri Nov 20 or Mon Nov 23)

Before the meeting: open the Cloud Run URL in a private window (no Google sign-in), confirm every page loads, and have
the code open in an editor in case your mentor asks to see it. Share your screen in Chrome.

1. **Home.** Pick a user (shows the "who are you" step).
2. **Find restaurants.** Filter by cuisine, then by max price and open now. Point out the average rating column. Open one restaurant: tables, reviews.
3. **Check availability.** Pick a date/time/party size with some results; then one with none. Mention double booking is prevented by the database.
4. **Book and pay.** Book a table from the results, then show it under "My reservations" with its payment.
5. **Try to double book** the same table and time: show the friendly error.
6. **Cancel** the reservation. Show it no longer blocks the table.
7. **Review.** Add a review as a user who has a completed reservation. Try as one without: show the rule.
8. **Favorites** then **Recommendations.** Show the recommendations change after favoriting something shared with other users.
9. **Code tour (if asked):** the query behind one page, and where parameters are bound (SQL injection safety).

Prepare data so each step has something to show (for example future dates, one user with no reservation yet).
