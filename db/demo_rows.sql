-- Demo rows for the mentor meeting: two completed visits that have NOT been reviewed yet,
-- so the review form can be demonstrated. Safe to run more than once.
-- Elena Rostova (user 1) ate at Community Food & Juice (102); Marcus Chen (user 2) at Chelsea Market Eats (103).
INSERT INTO Reservation (Reservation_ID, User_ID, Restaurant_ID, Table_No, Res_Date, Res_Time, Party_size, Status, Special_requests) VALUES
(5101, 1, 102, 1, '2026-10-22', '12:00:00', 2, 'completed', NULL),
(5102, 2, 103, 1, '2026-10-22', '13:00:00', 3, 'completed', NULL)
ON CONFLICT (Reservation_ID) DO NOTHING;

INSERT INTO Payment (Payment_ID, Reservation_ID, Amount, Method, Paid_at) VALUES
(9101, 5101, 24.00, 'Credit Card', '2026-10-22 13:30:00'),
(9102, 5102, 36.00, 'Apple Pay', '2026-10-22 14:30:00')
ON CONFLICT (Payment_ID) DO NOTHING;
