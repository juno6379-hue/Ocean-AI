"""Explicit migration, limited to two new source-review tables.

Dry-run is the default. This does not create all metadata tables or approvals.
"""
import argparse
from sqlalchemy.schema import CreateTable, CreateIndex
from app.core.database import engine
from app.models import domain  # ApprovalHistory FK, without creating its table.
from app.models.source_contracts import SourceContractPacket, SourceContractDecision


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    tables = [SourceContractPacket.__table__, SourceContractDecision.__table__]
    if args.apply:
        with engine.begin() as connection:
            for table in tables:
                table.create(connection, checkfirst=True)
        print('Created/verified only source_contract_packets and source_contract_decisions')
    else:
        for table in tables:
            print(str(CreateTable(table, if_not_exists=True).compile(engine)))
            for index in table.indexes:
                print(str(CreateIndex(index, if_not_exists=True).compile(engine)))


if __name__ == '__main__':
    main()
