"""Repository classes.

Each repository wraps a single SQLAlchemy session and exposes typed methods
that mirror the original PHP ``App/Service/*`` classes.  All SQL is written
explicitly (no ORM models) to keep behaviour identical to the reference
implementation.
"""
