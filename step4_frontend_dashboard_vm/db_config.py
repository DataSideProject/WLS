import os

# Database Configuration for GCP VM
# Default to localhost since the app runs on the same VM as the DB
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '') # Set via env var in production or edit here
DB_NAME = os.getenv('DB_NAME', 'job_data_warehouse')
