USE borrowback;
-- Run each ALTER only if the column is not already present in DESCRIBE output.
ALTER TABLE users ADD COLUMN branch VARCHAR(100) NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN section VARCHAR(30) NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN contact VARCHAR(40) NOT NULL DEFAULT '';
ALTER TABLE borrow_requests MODIFY item_id BIGINT NULL;
ALTER TABLE borrow_requests MODIFY owner_id VARCHAR(64) NULL;
ALTER TABLE borrow_requests MODIFY due_date DATE NULL;
ALTER TABLE borrow_requests ADD COLUMN requested_item_title VARCHAR(120) NULL;
ALTER TABLE borrow_requests ADD COLUMN requested_category VARCHAR(60) NULL;
ALTER TABLE borrow_requests ADD COLUMN requested_description TEXT NULL;
CREATE TABLE IF NOT EXISTS user_ratings (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 request_id BIGINT NOT NULL,
 rater_user_id VARCHAR(64) NOT NULL,
 rated_user_id VARCHAR(64) NOT NULL,
 rating TINYINT NOT NULL,
 comment VARCHAR(500) NOT NULL DEFAULT '',
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY unique_user_rating_per_request (request_id,rater_user_id),
 CONSTRAINT fk_rating_request FOREIGN KEY (request_id) REFERENCES borrow_requests(id),
 CONSTRAINT fk_rating_rater FOREIGN KEY (rater_user_id) REFERENCES users(id),
 CONSTRAINT fk_rating_rated FOREIGN KEY (rated_user_id) REFERENCES users(id)
);


-- In-app notifications for borrow and return events. Safe to run more than once.
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
