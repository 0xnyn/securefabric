-- Runs once, on first initialisation of the Postgres volume.
-- A separate database for the integration test suite so tests never touch dev data.
CREATE DATABASE securefabric_test OWNER securefabric;
