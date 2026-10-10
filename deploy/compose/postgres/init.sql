-- Runs once, on first start of an empty data volume.
-- Database per service, each owned by its own user: a service can only touch
-- its own data, so the services stay decoupled. Dev-only passwords.

CREATE USER catalog WITH PASSWORD 'catalog';
CREATE DATABASE catalog OWNER catalog;

CREATE USER orders WITH PASSWORD 'orders';
CREATE DATABASE orders OWNER orders;

CREATE USER notifications WITH PASSWORD 'notifications';
CREATE DATABASE notifications OWNER notifications;
