#!/usr/bin/env python3
"""Remove test plans from database."""

from powertochoose_mcp.db.operations import SessionLocal
from powertochoose_mcp.db.schema import Plan, PlanClassification

db = SessionLocal()

# Find and delete test plans
test_plans = db.query(Plan).filter(Plan.provider == 'Test Provider').all()
print(f"Found {len(test_plans)} test plans to delete...")

for plan in test_plans:
    print(f"  Deleting: {plan.name}")
    db.delete(plan)

db.commit()

# Verify
remaining = db.query(Plan).count()
print(f"\nTotal plans remaining: {remaining}")

# Show sample of real plans
sample = db.query(Plan).first()
if sample:
    print(f"\nSample real plan:")
    print(f"  Name: {sample.name}")
    print(f"  Provider: {sample.provider}")
    print(f"  ZIP: {sample.zip_code}")

db.close()
