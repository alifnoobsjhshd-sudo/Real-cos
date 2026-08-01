---
name: Supabase integration boundary
description: The project uses Supabase as an additive option while existing SQLite storage remains unchanged.
---

Supabase is an optional server-side data layer for this bot. Production credentials belong in Render's environment, while Replit Secrets are only for development. Existing SQLite databases should not be migrated or replaced implicitly.

**Why:** The bot has many existing SQLite databases and a Render deployment; an automatic migration could change persistence behavior or risk production data.

**How to apply:** Add Supabase-backed functionality behind explicit, feature-scoped changes. For any table migration, define the schema, backup/rollback plan, and access policies before changing a cog.