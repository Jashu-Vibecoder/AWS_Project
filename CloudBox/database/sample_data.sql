-- Local development fixtures only. These rows do not point to real S3 objects.
-- Do not run this file against a deployed database.
USE cloudbox_db;

INSERT IGNORE INTO files (file_name, s3_key, file_size, file_type, status)
VALUES
  ('project-brief.md', 'local-demo/project-brief.md', 512, 'text/markdown', 'active'),
  ('sample-data.csv', 'local-demo/sample-data.csv', 128, 'text/csv', 'active'),
  ('design-notes.txt', 'local-demo/design-notes.txt', 256, 'text/plain', 'active');
