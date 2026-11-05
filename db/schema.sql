-- COMS W4111 Project 1, Part 2: Restaurant Reservation System
-- Aman Upganlawar (au2327) and Grace Chun (gbc2115)
-- Run top to bottom. Tables are created in dependency order.

CREATE TABLE Users (
    User_ID    INTEGER,
    Name       VARCHAR(100) NOT NULL,
    Email      VARCHAR(254) NOT NULL UNIQUE,
    Phone      VARCHAR(20),
    User_zip   INTEGER CHECK (User_zip BETWEEN 10001 AND 11697),   -- NYC zip codes
    PRIMARY KEY (User_ID)
);

CREATE TABLE Restaurant (
    Restaurant_ID   INTEGER,
    Name            VARCHAR(100) NOT NULL,
    Min_price       INTEGER CHECK (Min_price >= 0),
    Max_price       INTEGER CHECK (Max_price >= 0),
    Open_time       TIME NOT NULL,
    Close_time      TIME NOT NULL,
    Cuisine         VARCHAR(50),
    Open_now        BOOLEAN,
    Restaurant_zip  INTEGER NOT NULL CHECK (Restaurant_zip BETWEEN 10001 AND 11697),   -- NYC zip codes
    PRIMARY KEY (Restaurant_ID),
    CHECK (Min_price <= Max_price),
    CHECK (Open_time <> Close_time)
);

-- Review is a weak entity of both User and Restaurant; Writes and Receives
-- are folded into this table.
CREATE TABLE Writes_and_Receives_Review (
    Review_ID      INTEGER,
    User_ID        INTEGER,
    Restaurant_ID  INTEGER,
    Review_Date    DATE NOT NULL,
    Rating         INTEGER NOT NULL CHECK (Rating BETWEEN 1 AND 5),
    Rating_text    VARCHAR(500),
    PRIMARY KEY (Review_ID, User_ID, Restaurant_ID),
    UNIQUE (User_ID, Restaurant_ID),   -- at most one review per user per restaurant
    FOREIGN KEY (User_ID) REFERENCES Users ON DELETE CASCADE,
    FOREIGN KEY (Restaurant_ID) REFERENCES Restaurant ON DELETE CASCADE
);

-- Favorites is many-to-many, so it gets its own table.
CREATE TABLE Favorites (
    User_ID        INTEGER,
    Restaurant_ID  INTEGER,
    Date_Added     DATE NOT NULL,
    PRIMARY KEY (User_ID, Restaurant_ID),
    FOREIGN KEY (User_ID) REFERENCES Users ON DELETE CASCADE,
    FOREIGN KEY (Restaurant_ID) REFERENCES Restaurant ON DELETE CASCADE
);

-- Weak entity of Restaurant; the Has relationship is folded in.
CREATE TABLE RestaurantTable (
    Restaurant_ID  INTEGER,
    Table_No       INTEGER,
    Capacity       INTEGER NOT NULL CHECK (Capacity > 0),
    Seating_type   VARCHAR(30) CHECK (Seating_type IN ('Standard Table', 'Booth', 'Large Booth',
                       'Window Seat', 'Cafe Table', 'High Top', 'Round Table', 'Counter',
                       'Bar', 'Sushi Bar', 'Lounge', 'Outdoor', 'Private Room')),
    PRIMARY KEY (Restaurant_ID, Table_No),
    FOREIGN KEY (Restaurant_ID) REFERENCES Restaurant ON DELETE CASCADE
);

-- Makes (User) and Selects (RestaurantTable) are folded in: each reservation
-- has exactly one user and exactly one table.
CREATE TABLE Reservation (
    Reservation_ID    INTEGER,
    Res_Date          DATE NOT NULL,
    Res_Time          TIME NOT NULL,
    Party_size        INTEGER NOT NULL CHECK (Party_size > 0),
    Status            VARCHAR(20) NOT NULL
                      CHECK (Status IN ('booked', 'cancelled', 'completed', 'no-show')),
    Special_requests  VARCHAR(500),
    User_ID           INTEGER NOT NULL,
    Restaurant_ID     INTEGER NOT NULL,
    Table_No          INTEGER NOT NULL,
    PRIMARY KEY (Reservation_ID),
    FOREIGN KEY (User_ID) REFERENCES Users,
    FOREIGN KEY (Restaurant_ID, Table_No) REFERENCES RestaurantTable
);

-- A table cannot hold two active reservations at the same date and time.
CREATE UNIQUE INDEX No_Double_Booking
    ON Reservation (Restaurant_ID, Table_No, Res_Date, Res_Time)
    WHERE Status <> 'cancelled';

-- Pays: one-to-one, total on Payment (every payment belongs to exactly one
-- reservation), so the foreign key lives in Payment.
CREATE TABLE Payment (
    Payment_ID      INTEGER,
    Amount          DECIMAL(10,2) NOT NULL CHECK (Amount > 0),
    Method          VARCHAR(30) NOT NULL,
    Paid_at         TIMESTAMP NOT NULL,
    Reservation_ID  INTEGER NOT NULL UNIQUE,
    PRIMARY KEY (Payment_ID),
    FOREIGN KEY (Reservation_ID) REFERENCES Reservation
);
