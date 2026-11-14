-- More than one kind of table per restaurant.
-- Part 2 gave every restaurant a single table (Table_No 1). This file gives each restaurant
-- three or four more tables of DIFFERENT seating types and sizes. It works for ANY restaurants in
-- the database (including ones added later), skips a seating type a restaurant already has,
-- and is safe to run more than once.
--   local:  loaded automatically by scripts/local_db.sh
--   class:  psql -h 127.0.0.1 -p 5454 -U au2327 -d proj1part2 -f extra_tables.sql
INSERT INTO RestaurantTable (Restaurant_ID, Table_No, Capacity, Seating_type)
SELECT r.Restaurant_ID, c.Table_No, c.Capacity, c.Seating_type
FROM Restaurant r
CROSS JOIN LATERAL (
    -- Table 2: a two-top, Table 3: a four-top, Table 4: a six-top.
    -- The type rotates with the restaurant id so restaurants differ from each other.
    SELECT n AS Table_No,
           CASE n WHEN 2 THEN 2 WHEN 3 THEN 4 ELSE 6 END AS Capacity,
           (ARRAY['Bar','Window Seat','Booth','Outdoor','High Top','Round Table',
                  'Counter','Lounge','Large Booth','Standard Table','Cafe Table'])
                 [1 + (r.Restaurant_ID + n * 3) % 11] AS Seating_type
    FROM generate_series(2, 4) AS n
) c
WHERE NOT EXISTS (SELECT 1 FROM RestaurantTable t
                  WHERE t.Restaurant_ID = r.Restaurant_ID AND t.Seating_type = c.Seating_type)
ON CONFLICT (Restaurant_ID, Table_No) DO NOTHING;
-- Every fourth restaurant also has a private room for 10 (Table 5).
INSERT INTO RestaurantTable (Restaurant_ID, Table_No, Capacity, Seating_type)
SELECT r.Restaurant_ID, 5, 10, 'Private Room' FROM Restaurant r
WHERE r.Restaurant_ID % 4 = 0
ON CONFLICT (Restaurant_ID, Table_No) DO NOTHING;
