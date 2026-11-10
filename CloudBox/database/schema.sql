-- Run this schema with a MySQL administrative account on a local database or RDS.
CREATE DATABASE IF NOT EXISTS cloudbox_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE cloudbox_db;

CREATE TABLE IF NOT EXISTS files (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  file_name VARCHAR(255) NOT NULL,
  s3_key VARCHAR(500) NOT NULL,
  file_size BIGINT UNSIGNED NOT NULL,
  file_type VARCHAR(100) NULL,
  status VARCHAR(30) NOT NULL DEFAULT 'active',
  uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_files_s3_key (s3_key),
  KEY idx_files_file_name (file_name),
  KEY idx_files_status_uploaded_at (status, uploaded_at)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
