-- CS61 Dorm Temperature Voting: schema
-- Matches CS61_Project_corrected.mwb, plus the CHECK constraints and
-- triggers the professor's feedback asked for.
-- Time convention: every DATETIME is stored in UTC. The API compares
-- against UTC_TIMESTAMP(), so the triggers do too.

DROP DATABASE IF EXISTS CS61_Project;
CREATE DATABASE CS61_Project DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE CS61_Project;

CREATE TABLE Buildings (
  building_id   INT NOT NULL AUTO_INCREMENT,
  building_name VARCHAR(120) NOT NULL,
  building_type ENUM('DORM','PUBLIC') NOT NULL,
  min_temp      DECIMAL(4,1) NOT NULL DEFAULT 66.0,
  max_temp      DECIMAL(4,1) NOT NULL DEFAULT 74.0,
  PRIMARY KEY (building_id),
  UNIQUE KEY uq_building_name (building_name),
  CONSTRAINT chk_building_range CHECK (min_temp >= 60 AND max_temp <= 80 AND min_temp < max_temp)
) ENGINE=InnoDB;

CREATE TABLE Students (
  student_id       BIGINT NOT NULL AUTO_INCREMENT,
  email            VARCHAR(255) NOT NULL,
  is_active        TINYINT NOT NULL DEFAULT 1,
  dorm_building_id INT NOT NULL,
  PRIMARY KEY (student_id),
  UNIQUE KEY uq_students_email (email),
  KEY idx_student_dorm (dorm_building_id),
  CONSTRAINT fk_student_dorm FOREIGN KEY (dorm_building_id)
    REFERENCES Buildings (building_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT chk_student_active CHECK (is_active IN (0, 1))
) ENGINE=InnoDB;

-- Extra buildings a student may vote on. The student's own dorm is NOT stored
-- here. Dorm access comes from Students.dorm_building_id, so each fact is stored once.
CREATE TABLE Student_Access (
  student_id  BIGINT NOT NULL,
  building_id INT NOT NULL,
  PRIMARY KEY (student_id, building_id),
  KEY idx_access_building (building_id),
  CONSTRAINT fk_access_student FOREIGN KEY (student_id)
    REFERENCES Students (student_id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_access_building FOREIGN KEY (building_id)
    REFERENCES Buildings (building_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE Temp_Logs (
  log_id        BIGINT NOT NULL AUTO_INCREMENT,
  building_id   INT NOT NULL,
  recorded_at   DATETIME NOT NULL,
  temperature_f DECIMAL(4,1) NOT NULL,
  PRIMARY KEY (log_id),
  UNIQUE KEY uq_temp_building_timestamp (building_id, recorded_at),
  CONSTRAINT fk_temp_building FOREIGN KEY (building_id)
    REFERENCES Buildings (building_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT chk_temp_reading CHECK (temperature_f BETWEEN 30 AND 100)
) ENGINE=InnoDB;

CREATE TABLE Voting_Windows (
  window_id   BIGINT NOT NULL AUTO_INCREMENT,
  building_id INT NOT NULL,
  start_time  DATETIME NOT NULL,
  end_time    DATETIME NOT NULL,
  PRIMARY KEY (window_id),
  UNIQUE KEY uq_window_building_start (building_id, start_time),
  KEY idx_window_building_end (building_id, end_time),
  CONSTRAINT fk_window_building FOREIGN KEY (building_id)
    REFERENCES Buildings (building_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT chk_window_times CHECK (start_time < end_time)
) ENGINE=InnoDB;

CREATE TABLE Recommendations (
  window_id   BIGINT NOT NULL,
  vote_count  INT NOT NULL DEFAULT 0,
  median_temp DECIMAL(4,1) NULL DEFAULT NULL,
  logged_temp DECIMAL(4,1) NULL DEFAULT NULL,
  direction   ENUM('warmer','colder','hold','no data') NOT NULL DEFAULT 'no data',
  computed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (window_id),
  CONSTRAINT fk_recommendation_window FOREIGN KEY (window_id)
    REFERENCES Voting_Windows (window_id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT chk_rec_count CHECK (vote_count >= 0)
) ENGINE=InnoDB;

CREATE TABLE Votes (
  vote_id        BIGINT NOT NULL AUTO_INCREMENT,
  student_id     BIGINT NOT NULL,
  window_id      BIGINT NOT NULL,
  requested_temp DECIMAL(4,1) NOT NULL,
  submitted_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (vote_id),
  UNIQUE KEY uq_vote_student_window (student_id, window_id),
  KEY fk_vote_window_idx (window_id),
  CONSTRAINT fk_vote_student FOREIGN KEY (student_id)
    REFERENCES Students (student_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_vote_window FOREIGN KEY (window_id)
    REFERENCES Voting_Windows (window_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT chk_vote_temp CHECK (requested_temp BETWEEN 60 AND 80)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------
-- Triggers: the second line of defense. The API checks first and gives
-- friendly errors. These stop bad rows even if the API has a bug.
-- Seed scripts may SET @seed_mode = 1 to load historical votes into
-- closed windows. The app never sets it.
-- ------------------------------------------------------------------
DELIMITER $$

-- Feedback item: a student's dorm must be a DORM building.
CREATE TRIGGER trg_students_dorm_bi BEFORE INSERT ON Students FOR EACH ROW
BEGIN
  IF (SELECT building_type FROM Buildings WHERE building_id = NEW.dorm_building_id) <> 'DORM' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'dorm_building_id must reference a DORM building';
  END IF;
END$$

CREATE TRIGGER trg_students_dorm_bu BEFORE UPDATE ON Students FOR EACH ROW
BEGIN
  IF NEW.dorm_building_id <> OLD.dorm_building_id
     AND (SELECT building_type FROM Buildings WHERE building_id = NEW.dorm_building_id) <> 'DORM' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'dorm_building_id must reference a DORM building';
  END IF;
END$$

-- Keep dorm and Student_Access from overlapping when a student moves dorms.
CREATE TRIGGER trg_students_dorm_au AFTER UPDATE ON Students FOR EACH ROW
BEGIN
  IF NEW.dorm_building_id <> OLD.dorm_building_id THEN
    DELETE FROM Student_Access
    WHERE student_id = NEW.student_id AND building_id = NEW.dorm_building_id;
  END IF;
END$$

-- A building can't become PUBLIC while it is someone's dorm.
CREATE TRIGGER trg_buildings_type_bu BEFORE UPDATE ON Buildings FOR EACH ROW
BEGIN
  IF NEW.building_type <> 'DORM' AND OLD.building_type = 'DORM'
     AND EXISTS (SELECT 1 FROM Students WHERE dorm_building_id = NEW.building_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Building is a dorm for existing students';
  END IF;
END$$

-- Feedback item: no duplicate of the dorm fact in Student_Access.
CREATE TRIGGER trg_access_bi BEFORE INSERT ON Student_Access FOR EACH ROW
BEGIN
  IF EXISTS (SELECT 1 FROM Students
             WHERE student_id = NEW.student_id AND dorm_building_id = NEW.building_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Dorm access is implied; do not add it to Student_Access';
  END IF;
END$$

-- Prevent updates to Student_Access from duplicating student's existing dorm access.
CREATE TRIGGER trg_access_bu
BEFORE UPDATE ON Student_Access
FOR EACH ROW
BEGIN
    IF EXISTS (SELECT 1 FROM Students WHERE student_id = NEW.student_id AND dorm_building_id = NEW.building_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Dorm access already implied. DO NOT add it to Student_Access';
    END IF;
END$$

-- Feedback item: tie every vote to access. Also enforce active student,
-- open window, and the building's own temperature range.
CREATE TRIGGER trg_votes_bi BEFORE INSERT ON Votes FOR EACH ROW
BEGIN
  DECLARE v_building INT;
  DECLARE v_start DATETIME;
  DECLARE v_end DATETIME;
  DECLARE v_min DECIMAL(4,1);
  DECLARE v_max DECIMAL(4,1);

  SELECT w.building_id, w.start_time, w.end_time, b.min_temp, b.max_temp
    INTO v_building, v_start, v_end, v_min, v_max
  FROM Voting_Windows w JOIN Buildings b ON b.building_id = w.building_id
  WHERE w.window_id = NEW.window_id;

  IF NOT EXISTS (SELECT 1 FROM Students WHERE student_id = NEW.student_id AND is_active = 1) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Student is not active';
  END IF;
  IF NOT EXISTS (
      SELECT 1 FROM Students s
      WHERE s.student_id = NEW.student_id
        AND (s.dorm_building_id = v_building
             OR EXISTS (SELECT 1 FROM Student_Access a
                        WHERE a.student_id = s.student_id AND a.building_id = v_building))) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Student has no access to this building';
  END IF;
  IF NEW.requested_temp < v_min OR NEW.requested_temp > v_max THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Requested temperature is outside the building range';
  END IF;
  IF @seed_mode IS NULL THEN
    IF UTC_TIMESTAMP() < v_start OR UTC_TIMESTAMP() >= v_end
       OR EXISTS (SELECT 1 FROM Recommendations WHERE window_id = NEW.window_id) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Voting window is not open';
    END IF;
  END IF;
END$$

-- Prevent unauthorized vote updates, including after building access is revoked.
CREATE TRIGGER trg_votes_bu BEFORE UPDATE ON Votes FOR EACH ROW
BEGIN
  DECLARE v_building INT;
  DECLARE v_start DATETIME;
  DECLARE v_end DATETIME;
  DECLARE v_min DECIMAL(4,1);
  DECLARE v_max DECIMAL(4,1);

  IF NEW.student_id <> OLD.student_id OR NEW.window_id <> OLD.window_id THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A vote cannot move to another student or window';
  END IF;

  SELECT w.building_id, w.start_time, w.end_time, b.min_temp, b.max_temp
    INTO v_building, v_start, v_end, v_min, v_max
  FROM Voting_Windows w
  JOIN Buildings b ON b.building_id = w.building_id
  WHERE w.window_id = NEW.window_id;

  IF NOT EXISTS (
    SELECT 1 FROM Students
    WHERE student_id = NEW.student_id AND is_active = 1
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Student is not active';
  END IF;

  -- Reject vote updates if student no longer has building access.
  IF NOT EXISTS (
    SELECT 1 FROM Students s
    WHERE s.student_id = NEW.student_id
      AND (
        s.dorm_building_id = v_building
        OR EXISTS (
          SELECT 1 FROM Student_Access a
          WHERE a.student_id = s.student_id
            AND a.building_id = v_building
        )
      )
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Student has no access to this building';
  END IF;

  IF NEW.requested_temp < v_min OR NEW.requested_temp > v_max THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Requested temperature is outside the building range';
  END IF;

  IF UTC_TIMESTAMP() < v_start OR UTC_TIMESTAMP() >= v_end
     OR EXISTS (
       SELECT 1 FROM Recommendations
       WHERE window_id = NEW.window_id
     ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Voting window is not open';
  END IF;
END$$

DELIMITER ;