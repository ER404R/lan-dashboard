# lan-dashboard

> **Disclaimer:** This project is used to test agentic AI coding workflows. The codebase is largely AI-generated with minimal human oversight. Expect security vulnerabilities, rough edges, and questionable code practices. Use at your own risk.

A self-hosted dashboard for LAN parties. Tracks game scores, manages a shared game library (Steam + custom), and lets users submit feature requests. User registration is invite-token gated.

## Features

- Scoreboard per game per user
- Game library with Steam search and custom game support; ownership and wishlist tracking
- Feature requests with comments
- Invite-token-based registration with admin role

## Setup

1. Copy `.env.example` to `.env` and fill in the values.
2. Run `docker compose up -d`.

The app is exposed on port 80/443 via Nginx. The Docker image is pulled from `ghcr.io/er404r/lan-dashboard:latest`.

## Configuration

| Variable | Description |
|---|---|
| `SECRET_KEY` | Random string for session signing |
| `DATABASE_URL` | PostgreSQL connection string (`postgresql://user:pass@db:5432/dbname`) |
| `REGISTRATION_ENABLED` | `true` or `false` — whether new users can register |
| `ADMIN_INVITE_TOKEN` | Token that grants admin role on registration |
| `SEED_INVITE_TOKENS` | Comma-separated tokens to seed on startup |
| `POSTGRES_DB` | PostgreSQL database name (used by the `db` service) |
| `POSTGRES_USER` | PostgreSQL username (used by the `db` service) |
| `POSTGRES_PASSWORD` | PostgreSQL password (used by the `db` service) |
