-- seed (Trak). Run after schema.sql.
-- @seed_mode lets the historical votes into windows that already ended.
-- The vote trigger blocks that for normal app traffic.
SET @seed_mode = 1;

USE CS61_Project;
SET @seed_now = UTC_TIMESTAMP();
START TRANSACTION;


-- 1. Buildings: INSERT only if a seed building name is absent.


INSERT INTO Buildings (building_name, building_type, min_temp, max_temp)
SELECT 'SEED - North Park', 'DORM', 66.0, 74.0
WHERE NOT EXISTS (SELECT 1 FROM Buildings WHERE building_name = 'SEED - North Park');

INSERT INTO Buildings (building_name, building_type, min_temp, max_temp)
SELECT 'SEED - South House', 'DORM', 65.0, 75.0
WHERE NOT EXISTS (SELECT 1 FROM Buildings WHERE building_name = 'SEED - South House');

INSERT INTO Buildings (building_name, building_type, min_temp, max_temp)
SELECT 'SEED - West House', 'DORM', 66.0, 76.0
WHERE NOT EXISTS (SELECT 1 FROM Buildings WHERE building_name = 'SEED - West House');

INSERT INTO Buildings (building_name, building_type, min_temp, max_temp)
SELECT 'SEED - Library', 'PUBLIC', 67.0, 73.0
WHERE NOT EXISTS (SELECT 1 FROM Buildings WHERE building_name = 'SEED - Library');

INSERT INTO Buildings (building_name, building_type, min_temp, max_temp)
SELECT 'SEED - Allen House', 'DORM', 66.0, 76.0
WHERE NOT EXISTS (SELECT 1 FROM Buildings WHERE building_name = 'SEED - Allen House');

INSERT INTO Buildings (building_name, building_type, min_temp, max_temp)
SELECT 'SEED - School House', 'DORM', 66.0, 76.0
WHERE NOT EXISTS (SELECT 1 FROM Buildings WHERE building_name = 'SEED - School House');

SET @north_id = (SELECT building_id FROM Buildings WHERE building_name = 'SEED - North Park');
SET @south_id = (SELECT building_id FROM Buildings WHERE building_name = 'SEED - South House');
SET @west_id = (SELECT building_id FROM Buildings WHERE building_name = 'SEED - West House');
SET @library_id = (SELECT building_id FROM Buildings WHERE building_name = 'SEED - Library');
SET @allen_id = (SELECT building_id FROM Buildings WHERE building_name = 'SEED - Allen House');
SET @schoolhouse_id = (SELECT building_id FROM Buildings WHERE building_name = 'SEED - School House');

-- 2. Students: dorm assignments reference only DORM buildings.

INSERT INTO Students (email, is_active, dorm_building_id)
SELECT 'seed.trak@example.test', 1, @north_id
WHERE NOT EXISTS (SELECT 1 FROM Students WHERE email = 'seed.trak@example.test');

INSERT INTO Students (email, is_active, dorm_building_id)
SELECT 'seed.jace@example.test', 1, @north_id
WHERE NOT EXISTS (SELECT 1 FROM Students WHERE email = 'seed.jace@example.test');

INSERT INTO Students (email, is_active, dorm_building_id)
SELECT 'seed.baila@example.test', 1, @north_id
WHERE NOT EXISTS (SELECT 1 FROM Students WHERE email = 'seed.baila@example.test');

INSERT INTO Students (email, is_active, dorm_building_id)
SELECT 'seed.phoom@example.test', 1, @south_id
WHERE NOT EXISTS (SELECT 1 FROM Students WHERE email = 'seed.phoom@example.test');

INSERT INTO Students (email, is_active, dorm_building_id)
SELECT 'seed.james@example.test', 1, @west_id
WHERE NOT EXISTS (SELECT 1 FROM Students WHERE email = 'seed.james@example.test');

INSERT INTO Students (email, is_active, dorm_building_id)
SELECT 'seed.patrick@example.test', 0, @south_id
WHERE NOT EXISTS (SELECT 1 FROM Students WHERE email = 'seed.patrick@example.test');

INSERT INTO Students (email, is_active, dorm_building_id)
SELECT 'seed.john@example.test', 1, @south_id
WHERE NOT EXISTS (SELECT 1 FROM Students WHERE email = 'seed.john@example.test');

SET @trak_id = (SELECT student_id FROM Students WHERE email = 'seed.trak@example.test');
SET @jace_id = (SELECT student_id FROM Students WHERE email = 'seed.jace@example.test');
SET @baila_id = (SELECT student_id FROM Students WHERE email = 'seed.baila@example.test');
SET @phoom_id = (SELECT student_id FROM Students WHERE email = 'seed.phoom@example.test');
SET @james_id = (SELECT student_id FROM Students WHERE email = 'seed.james@example.test');
SET @patrick_id = (SELECT student_id FROM Students WHERE email = 'seed.patrick@example.test');
SET @john_id = (SELECT student_id FROM Students WHERE email = 'seed.john@example.test');


-- 3. Extra access only:
-- Trak can access the Library, Jace can access Allen House,
-- Baila can access the Library.

INSERT INTO Student_Access (student_id, building_id)
SELECT @trak_id, @library_id
WHERE NOT EXISTS (SELECT 1 FROM Student_Access
                  WHERE student_id = @trak_id AND building_id = @library_id);

INSERT INTO Student_Access (student_id, building_id)
SELECT @jace_id, @allen_id
WHERE NOT EXISTS (SELECT 1 FROM Student_Access
                  WHERE student_id = @jace_id AND building_id = @allen_id);

INSERT INTO Student_Access (student_id, building_id)
SELECT @baila_id, @library_id
WHERE NOT EXISTS (SELECT 1 FROM Student_Access
                  WHERE student_id = @baila_id AND building_id = @library_id);

-- 4. Voting windows:
-- North: OPEN on first seed (started 1 hour ago. ends in 1 day just for test purpose).
-- South: ENDED with votes, no recommendation yet --> test admin close.
-- West: ENDED + historical recommendation saved.
-- Library: SCHEDULED future window. --> Test early-close rejection.
-- Allen House: OPEN, w/ one vote.
-- School House: NO window --> admin creation tests.
-- Each created once per dedicated seed building.

INSERT INTO Voting_Windows (building_id, start_time, end_time)
SELECT @north_id, DATE_ADD(@seed_now, INTERVAL -1 HOUR),
       DATE_ADD(@seed_now, INTERVAL 1 DAY)
WHERE NOT EXISTS (SELECT 1 FROM Voting_Windows WHERE building_id = @north_id);
SET @north_window = (SELECT window_id FROM Voting_Windows WHERE building_id = @north_id ORDER BY start_time LIMIT 1);

INSERT INTO Voting_Windows (building_id, start_time, end_time)
SELECT @south_id, DATE_ADD(@seed_now, INTERVAL -3 DAY),
       DATE_ADD(@seed_now, INTERVAL -2 DAY)
WHERE NOT EXISTS (SELECT 1 FROM Voting_Windows WHERE building_id = @south_id);
SET @south_window = (SELECT window_id FROM Voting_Windows WHERE building_id = @south_id ORDER BY start_time LIMIT 1);

INSERT INTO Voting_Windows (building_id, start_time, end_time)
SELECT @west_id, DATE_ADD(@seed_now, INTERVAL -6 DAY),
       DATE_ADD(@seed_now, INTERVAL -5 DAY)
WHERE NOT EXISTS (SELECT 1 FROM Voting_Windows WHERE building_id = @west_id);
SET @west_window = (SELECT window_id FROM Voting_Windows WHERE building_id = @west_id ORDER BY start_time LIMIT 1);

INSERT INTO Voting_Windows (building_id, start_time, end_time)
SELECT @library_id, DATE_ADD(@seed_now, INTERVAL 1 DAY),
       DATE_ADD(@seed_now, INTERVAL 2 DAY)
WHERE NOT EXISTS (SELECT 1 FROM Voting_Windows WHERE building_id = @library_id);
SET @library_window = (SELECT window_id FROM Voting_Windows WHERE building_id = @library_id ORDER BY start_time LIMIT 1);

INSERT INTO Voting_Windows (building_id, start_time, end_time)
SELECT @allen_id, DATE_ADD(@seed_now, INTERVAL -2 HOUR),
       DATE_ADD(@seed_now, INTERVAL 2 DAY)
WHERE NOT EXISTS (SELECT 1 FROM Voting_Windows WHERE building_id = @allen_id);
SET @allen_window = (SELECT window_id FROM Voting_Windows WHERE building_id = @allen_id ORDER BY start_time LIMIT 1);

-- 5. Temperature readings which is tied to each window's saved start/end times.
-- (completed) West house window has a 70 F log that its historical recommendation uses. 
-- North park's newest seeded reading is 71 F.
-- No dup building/timestamp pairs on rerun.

INSERT INTO Temp_Logs (building_id, recorded_at, temperature_f)
SELECT w.building_id, DATE_ADD(w.start_time, INTERVAL 10 MINUTE), 70.0
FROM Voting_Windows AS w
WHERE w.window_id = @north_window
  AND NOT EXISTS (
      SELECT 1 FROM Temp_Logs t
      WHERE t.building_id = w.building_id
        AND t.recorded_at = DATE_ADD(w.start_time, INTERVAL 10 MINUTE)
  );

INSERT INTO Temp_Logs (building_id, recorded_at, temperature_f)
SELECT w.building_id, DATE_ADD(w.start_time, INTERVAL 20 MINUTE), 71.0
FROM Voting_Windows AS w
WHERE w.window_id = @north_window
  AND NOT EXISTS (
      SELECT 1 FROM Temp_Logs t
      WHERE t.building_id = w.building_id
        AND t.recorded_at = DATE_ADD(w.start_time, INTERVAL 20 MINUTE)
  );

INSERT INTO Temp_Logs (building_id, recorded_at, temperature_f)
SELECT w.building_id, DATE_ADD(w.start_time, INTERVAL 60 MINUTE), 68.0
FROM Voting_Windows AS w
WHERE w.window_id = @south_window
  AND NOT EXISTS (
      SELECT 1 FROM Temp_Logs t
      WHERE t.building_id = w.building_id
        AND t.recorded_at = DATE_ADD(w.start_time, INTERVAL 60 MINUTE)
  );

INSERT INTO Temp_Logs (building_id, recorded_at, temperature_f)
SELECT w.building_id, DATE_ADD(w.start_time, INTERVAL 60 MINUTE), 70.0
FROM Voting_Windows AS w
WHERE w.window_id = @west_window
  AND NOT EXISTS (
      SELECT 1 FROM Temp_Logs t
      WHERE t.building_id = w.building_id
        AND t.recorded_at = DATE_ADD(w.start_time, INTERVAL 60 MINUTE)
  );

INSERT INTO Temp_Logs (building_id, recorded_at, temperature_f)
SELECT w.building_id, DATE_ADD(w.start_time, INTERVAL -2 HOUR), 69.0
FROM Voting_Windows AS w
WHERE w.window_id = @library_window
  AND NOT EXISTS (
      SELECT 1 FROM Temp_Logs t
      WHERE t.building_id = w.building_id
        AND t.recorded_at = DATE_ADD(w.start_time, INTERVAL -2 HOUR)
  );

-- Extra readings for Allen House and School House.
INSERT INTO Temp_Logs (building_id, recorded_at, temperature_f)
SELECT w.building_id, DATE_ADD(w.start_time, INTERVAL 30 MINUTE), 71.5
FROM Voting_Windows w
WHERE w.window_id = @allen_window
  AND NOT EXISTS (
    SELECT 1 FROM Temp_Logs t
    WHERE t.building_id = w.building_id
      AND t.recorded_at = DATE_ADD(w.start_time, INTERVAL 30 MINUTE)
  );

INSERT INTO Temp_Logs (building_id, recorded_at, temperature_f)
SELECT @schoolhouse_id, '2026-11-19 12:00:00', 69.5
WHERE NOT EXISTS (
    SELECT 1 FROM Temp_Logs t
    WHERE t.building_id = @schoolhouse_id
      AND t.recorded_at = '2026-11-19 12:00:00'
);

-- Phoom assigned to South House but can now vote in North Park.
INSERT INTO Student_Access (student_id, building_id)
SELECT @phoom_id, @north_id
WHERE NOT EXISTS (SELECT 1 FROM Student_Access
                  WHERE student_id = @phoom_id AND building_id = @north_id);

-- 6. Votes:
-- INACTIVE Patrick is NOT given any votes.
-- inserts use NOT EXISTS test on (student_id, window_id).
-- All requested temp fit each building's configured range.
-- Extra voting access for Trak and Jace to West House.

INSERT INTO Student_Access (student_id, building_id)
SELECT @trak_id, @west_id
WHERE NOT EXISTS (SELECT 1 FROM Student_Access
                  WHERE student_id = @trak_id AND building_id = @west_id);

INSERT INTO Student_Access (student_id, building_id)
SELECT @jace_id, @west_id
WHERE NOT EXISTS (SELECT 1 FROM Student_Access
                  WHERE student_id = @jace_id AND building_id = @west_id);

INSERT INTO Votes (student_id, window_id, requested_temp, submitted_at)
SELECT @trak_id, w.window_id, 70.0,
       DATE_ADD(w.start_time, INTERVAL 15 MINUTE)
FROM Voting_Windows w
WHERE w.window_id = @north_window
  AND NOT EXISTS (SELECT 1 FROM Votes v
                  WHERE v.student_id = @trak_id AND v.window_id = w.window_id);

INSERT INTO Votes (student_id, window_id, requested_temp, submitted_at)
SELECT @jace_id, w.window_id, 72.0,
       DATE_ADD(w.start_time, INTERVAL 25 MINUTE)
FROM Voting_Windows w
WHERE w.window_id = @north_window
  AND NOT EXISTS (SELECT 1 FROM Votes v
                  WHERE v.student_id = @jace_id AND v.window_id = w.window_id);

INSERT INTO Votes (student_id, window_id, requested_temp, submitted_at)
SELECT @baila_id, w.window_id, 74.0,
       DATE_ADD(w.start_time, INTERVAL 35 MINUTE)
FROM Voting_Windows w
WHERE w.window_id = @north_window
  AND NOT EXISTS (SELECT 1 FROM Votes v
                  WHERE v.student_id = @baila_id AND v.window_id = w.window_id);

INSERT INTO Votes (student_id, window_id, requested_temp, submitted_at)
SELECT @phoom_id, w.window_id, 73.0,
       DATE_ADD(w.start_time, INTERVAL 40 MINUTE)
FROM Voting_Windows w
WHERE w.window_id = @north_window
  AND NOT EXISTS (SELECT 1 FROM Votes v
                  WHERE v.student_id = @phoom_id AND v.window_id = w.window_id);

INSERT INTO Votes (student_id, window_id, requested_temp, submitted_at)
SELECT @phoom_id, w.window_id, 70.0,
       DATE_ADD(w.start_time, INTERVAL 30 MINUTE)
FROM Voting_Windows w
WHERE w.window_id = @south_window
  AND NOT EXISTS (SELECT 1 FROM Votes v
                  WHERE v.student_id = @phoom_id AND v.window_id = w.window_id);

INSERT INTO Votes (student_id, window_id, requested_temp, submitted_at)
SELECT @john_id, w.window_id, 72.0,
       DATE_ADD(w.start_time, INTERVAL 35 MINUTE)
FROM Voting_Windows w
WHERE w.window_id = @south_window
  AND NOT EXISTS (SELECT 1 FROM Votes v
                  WHERE v.student_id = @john_id AND v.window_id = w.window_id);

INSERT INTO Votes (student_id, window_id, requested_temp, submitted_at)
SELECT @james_id, w.window_id, 72.0,
       DATE_ADD(w.start_time, INTERVAL 25 MINUTE)
FROM Voting_Windows w
WHERE w.window_id = @west_window
  AND NOT EXISTS (SELECT 1 FROM Votes v
                  WHERE v.student_id = @james_id AND v.window_id = w.window_id);

INSERT INTO Votes (student_id, window_id, requested_temp, submitted_at)
SELECT @trak_id, w.window_id, 74.0,
       DATE_ADD(w.start_time, INTERVAL 30 MINUTE)
FROM Voting_Windows w
WHERE w.window_id = @west_window
  AND NOT EXISTS (SELECT 1 FROM Votes v
                  WHERE v.student_id = @trak_id AND v.window_id = w.window_id);

INSERT INTO Votes (student_id, window_id, requested_temp, submitted_at)
SELECT @jace_id, w.window_id, 76.0,
       DATE_ADD(w.start_time, INTERVAL 40 MINUTE)
FROM Voting_Windows w
WHERE w.window_id = @west_window
  AND NOT EXISTS (SELECT 1 FROM Votes v
                  WHERE v.student_id = @jace_id AND v.window_id = w.window_id);

-- Jace votes in Allen House using extra permission.
INSERT INTO Votes (student_id, window_id, requested_temp, submitted_at)
SELECT @jace_id, w.window_id, 72.0,
       DATE_ADD(w.start_time, INTERVAL 45 MINUTE)
FROM Voting_Windows w
WHERE w.window_id = @allen_window
  AND NOT EXISTS (SELECT 1 FROM Votes v
                  WHERE v.student_id = @jace_id AND v.window_id = w.window_id);

-- 7. Historical snapshot for (completed) West House window.
-- West votes: 72, 74, 76 -> median 74. logged temperature: 70.
-- direction = warmer.
-- One window can have zero OR one recommendation.
-- Other windows have no recommendation, North and Allen are open.
-- South ready for admin to close, Library is scheduled. School has no window.

INSERT INTO Recommendations
    (window_id, vote_count, median_temp, logged_temp, direction, computed_at)
SELECT w.window_id, 3, 74.0, 70.0, 'warmer',
       DATE_ADD(w.end_time, INTERVAL 1 MINUTE)
FROM Voting_Windows w
WHERE w.window_id = @west_window
  AND NOT EXISTS (SELECT 1 FROM Recommendations r WHERE r.window_id = w.window_id);

COMMIT;

-- 8. Verification queries (read-only).
SELECT building_id, building_name, building_type, min_temp, max_temp
FROM Buildings WHERE building_name LIKE 'SEED - %' ORDER BY building_id;

SELECT student_id, email, is_active, dorm_building_id
FROM Students WHERE email LIKE 'seed.%@example.test' ORDER BY student_id;

SELECT w.window_id, b.building_name, w.start_time, w.end_time,
       COUNT(DISTINCT v.vote_id) AS votes,
       IF(r.window_id IS NULL, 'not processed', 'processed') AS recommendation_status
FROM Voting_Windows w
JOIN Buildings b ON b.building_id = w.building_id
LEFT JOIN Votes v ON v.window_id = w.window_id
LEFT JOIN Recommendations r ON r.window_id = w.window_id
WHERE b.building_name LIKE 'SEED - %'
GROUP BY w.window_id, b.building_name, w.start_time, w.end_time, r.window_id
ORDER BY w.start_time;

SELECT r.* FROM Recommendations r
JOIN Voting_Windows w ON w.window_id = r.window_id
JOIN Buildings b ON b.building_id = w.building_id
WHERE b.building_name LIKE 'SEED - %';


SET @seed_mode = NULL;