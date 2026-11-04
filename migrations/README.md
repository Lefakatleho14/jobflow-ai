# JobFlow AI — Database Migrations

This folder contains forward-only schema migrations. Each `.py` file is a
single, versioned, ordered change to the SQLite schema.

## Rules

1. **Never edit an applied migration.** Once a file is in `git` and has been
   applied to any database, it is immutable. Add a new migration instead.
2. **Forward-only.** We do not support `down()` reversion. If a change is
   wrong, add a new migration that reverses it.
3. **Never drop a column in SQLite.** SQLite has limited `ALTER TABLE`
   support. If a column is obsolete, stop reading it in the app and leave
   it in place. Drop it only when you can recreate the table.
4. **Never rename in-place.** Add a new column, backfill, deprecate old.
5. **Migrations are raw SQL only.** Do not import `app.models` or
   `app.services`. This keeps migrations runnable even after refactors.
6. **Migration files must be idempotent-safe.** Running twice must not
   cause errors. Use `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN` only once
   per column (guarded by checking `PRAGMA table_info`), etc.

## Naming

`NNN_short_description.py` where `NNN` is a zero-padded 3-digit integer.
Examples:

- `001_add_verification_fields.py`
- `002_add_saved_searches.py`
- `003_add_cv_versions.py`

## Running

From the project root, venv active:

```powershell
python -m migrations              # apply pending migrations
python -m migrations --status     # show status only