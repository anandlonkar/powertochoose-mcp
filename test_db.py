#!/usr/bin/env python3
"""Quick test script to verify database contents."""

from powertochoose_mcp.db.operations import SessionLocal
from powertochoose_mcp.db.schema import Plan, PlanClassification
from sqlalchemy import func

db = SessionLocal()

print(f"Total plans: {db.query(Plan).count()}")
print(f"ZIP 75074: {db.query(Plan).filter(Plan.zip_code == '75074').count()}")
print(f"Plans with classifications: {db.query(Plan.id).join(PlanClassification).distinct().count()}")

sample = db.query(Plan).first()
if sample:
    print(f"\nSample plan: {sample.name}")
    print(f"Provider: {sample.provider}")
    print(f"Cost at 1000 kWh: ${sample.cost_1000_kwh['total_monthly_usd']:.2f}")
    print(f"Classifications: {[c.classification for c in sample.classifications]}")

db.close()
