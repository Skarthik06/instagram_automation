-- Runs ONCE, on first initialization of the shared Postgres volume, as the
-- superuser (POSTGRES_USER) against the default database.
--
-- POSTGRES_DB already created `instagram_business` for the Instagram project.
-- Here we add the affiliate project's database and enable pgvector in it.

CREATE DATABASE affiliate_rag_bot;

\connect affiliate_rag_bot
CREATE EXTENSION IF NOT EXISTS vector;
