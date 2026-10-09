"""Add the explicit UTC binding clock; dry-run by default, no legacy backfill.

Run only after deployment review. No approvals, source payloads or legacy
created_at values change. Existing rows retain NULL availability.
"""
import argparse
from sqlalchemy import DateTime, inspect, text

DDL = ('ALTER TABLE source_observation_binding ADD COLUMN IF NOT EXISTS '
       'bound_at_utc TIMESTAMP WITH TIME ZONE NULL')


def migrate(engine, *, apply=False):
    if engine.dialect.name != 'postgresql':
        raise ValueError('BINDING_CLOCK_MIGRATION_REQUIRES_POSTGRESQL')
    if not apply:
        return {'applied': False, 'sql': DDL, 'legacy_backfill': False,
                'server_default': None, 'data_writes': 0}
    with engine.begin() as connection:
        columns = {c['name']: c for c in inspect(connection).get_columns('source_observation_binding')}
        existing = columns.get('bound_at_utc')
        if existing and (not isinstance(existing['type'], DateTime) or
                         not existing['type'].timezone or not existing['nullable'] or
                         existing.get('default') is not None):
            raise ValueError('EXISTING_BINDING_CLOCK_SCHEMA_MISMATCH')
        if not existing:
            connection.execute(text(DDL))
    return {'applied': True, 'legacy_backfill': False, 'server_default': None,
            'data_writes': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    from app.core.database import engine
    result = migrate(engine, apply=args.apply)
    print(result['sql'] if not args.apply else 'Verified nullable timestamptz binding clock; no backfill')


if __name__ == '__main__':
    main()
