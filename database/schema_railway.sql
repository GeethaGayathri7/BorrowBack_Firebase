
CREATE TABLE IF NOT EXISTS users (
  id VARCHAR(64) PRIMARY KEY,
  display_name VARCHAR(100) NOT NULL,
  email VARCHAR(190) NULL UNIQUE,
  password_hash VARCHAR(300) NULL,
  branch VARCHAR(100) NOT NULL DEFAULT '',
  section VARCHAR(30) NOT NULL DEFAULT '',
  contact VARCHAR(40) NOT NULL DEFAULT '',
  completed_borrows INT NOT NULL DEFAULT 0,
  late_returns INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  owner_id VARCHAR(64) NOT NULL,
  title VARCHAR(120) NOT NULL,
  category VARCHAR(60) NOT NULL,
  description TEXT,
  available BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_items_owner FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS borrow_requests (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  item_id BIGINT NULL,
  borrower_id VARCHAR(64) NOT NULL,
  owner_id VARCHAR(64) NULL,
  due_date DATE NULL,
  status ENUM('pending','approved','rejected','returned','overdue') NOT NULL DEFAULT 'pending',
  requested_item_title VARCHAR(120) NULL,
  requested_category VARCHAR(60) NULL,
  requested_description TEXT NULL,
  requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  approved_at DATETIME NULL,
  returned_at DATETIME NULL,
  CONSTRAINT fk_req_item FOREIGN KEY (item_id) REFERENCES items(id),
  CONSTRAINT fk_req_borrower FOREIGN KEY (borrower_id) REFERENCES users(id),
  CONSTRAINT fk_req_owner FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS user_ratings (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  request_id BIGINT NOT NULL,
  rater_user_id VARCHAR(64) NOT NULL,
  rated_user_id VARCHAR(64) NOT NULL,
  rating TINYINT NOT NULL,
  comment VARCHAR(500) NOT NULL DEFAULT '',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY unique_user_rating_per_request (request_id, rater_user_id),
  CONSTRAINT chk_rating_range CHECK (rating BETWEEN 1 AND 5),
  CONSTRAINT fk_rating_request FOREIGN KEY (request_id) REFERENCES borrow_requests(id),
  CONSTRAINT fk_rating_rater FOREIGN KEY (rater_user_id) REFERENCES users(id),
  CONSTRAINT fk_rating_rated FOREIGN KEY (rated_user_id) REFERENCES users(id)
);


CREATE TABLE IF NOT EXISTS notifications (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  event_type VARCHAR(40) NOT NULL,
  title VARCHAR(160) NOT NULL,
  message TEXT NOT NULL,
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_notifications_user_read_created (user_id, is_read, created_at),
  CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
