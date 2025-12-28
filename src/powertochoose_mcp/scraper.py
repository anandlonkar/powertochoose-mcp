"""Web scraper for powertochoose.org.

Scrapes electricity plan listings, downloads EFL PDFs, and extracts plan details.
"""

import asyncio
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup

from .config import (
    POWERTOCHOOSE_BASE_URL,
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    EFL_DIR,
    ZIP_CODES,
    EFL_RETENTION_DAYS,
    LOG_RETENTION_DAYS,
)
from .db import get_session, store_plan, init_database
from .efl_parser import parse_efl_file
from .calculator import calculate_plan_costs
from .utils.logging import cleanup_old_log_files


class PowerToChooseScraper:
    """Scraper for powertochoose.org electricity plans."""

    def __init__(self):
        """Initialize scraper."""
        self.client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
        self.base_url = POWERTOCHOOSE_BASE_URL

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def scrape_zip_code(self, zip_code: str) -> int:
        """Scrape all plans for a ZIP code using PowerToChoose API.

        Args:
            zip_code: ZIP code to scrape

        Returns:
            Number of plans successfully scraped
        """
        print(f"Scraping ZIP code: {zip_code}")

        try:
            # Use PowerToChoose API
            api_url = "http://api.powertochoose.org/api/PowerToChoose/plans"
            params = {"zip_code": zip_code}
            
            response = await self.client.get(api_url, params=params)
            response.raise_for_status()

            # Parse JSON response
            data = response.json()
            plans = data.get("data", [])
            
            if not plans:
                print(f"  ⚠ No plans found for ZIP {zip_code}")
                return 0

            print(f"  Found {len(plans)} plans from API")

            successful_count = 0
            
            for plan in plans:
                try:
                    plan_data = await self._extract_plan_data_from_api(plan, zip_code)
                    if plan_data:
                        successful_count += 1
                        print(f"  ✓ Scraped: {plan_data['name']}")
                    
                    # Respect rate limits (lighter since we're using API)
                    await asyncio.sleep(REQUEST_DELAY_SECONDS / 2)
                    
                except Exception as e:
                    print(f"  ✗ Error processing plan {plan.get('plan_name', 'unknown')}: {e}")
                    continue

            print(f"Successfully scraped {successful_count} plans for ZIP {zip_code}")
            return successful_count

        except Exception as e:
            print(f"Error scraping ZIP code {zip_code}: {e}")
            return 0

            print(f"Successfully scraped {successful_count} plans for ZIP {zip_code}")
            return successful_count

        except Exception as e:
            print(f"Error scraping ZIP code {zip_code}: {e}")
            return 0

    async def _extract_plan_data_from_api(self, plan: dict, zip_code: str) -> Optional[dict]:
        """Extract plan data from API response.

        Args:
            plan: Plan dictionary from API
            zip_code: ZIP code being scraped

        Returns:
            Plan data dictionary or None if extraction fails
        """
        try:
            plan_name = plan.get("plan_name", "")
            provider = plan.get("company_name", "")
            
            if not plan_name or not provider:
                return None
            
            # Generate unique plan ID
            plan_id = str(plan.get("plan_id", self._generate_plan_id(provider, plan_name, zip_code)))

            # Get EFL URL
            efl_url = plan.get("fact_sheet", "")
            if not efl_url:
                print(f"  ⚠ No EFL found for {plan_name}")
                return None

            # Download and parse EFL for detailed rate structure
            efl_path = await self._download_efl(efl_url, plan_id)
            if not efl_path:
                # If EFL parsing fails, use API data as fallback
                print(f"  ⚠ Could not parse EFL, using API data for {plan_name}")
                rate_structure = self._create_rate_structure_from_api(plan)
                costs = self._calculate_costs_from_api(plan)
            else:
                rate_structure = parse_efl_file(efl_path)
                costs = calculate_plan_costs(rate_structure)

            # Extract contract length
            contract_length = plan.get("term_value")

            # Extract renewable percentage from description
            renewable_desc = plan.get("renewable_energy_description", "")
            renewable_pct = self._extract_renewable_percentage(renewable_desc)

            # Extract cancellation fee
            pricing_details = plan.get("pricing_details", "")
            cancellation_fee = self._extract_cancellation_fee(pricing_details)

            # Extract classifications
            classifications = self._extract_classifications_from_api(plan, rate_structure)

            # Build plan data
            plan_data = {
                "id": plan_id,
                "name": plan_name,
                "provider": provider,
                "zip_code": zip_code,
                "contract_length_months": contract_length,
                "renewable_percentage": renewable_pct,
                "cancellation_fee": cancellation_fee,
                "rate_structure": rate_structure.model_dump() if hasattr(rate_structure, 'model_dump') else rate_structure,
                "cost_500_kwh": costs["cost_500_kwh"],
                "cost_1000_kwh": costs["cost_1000_kwh"],
                "cost_2000_kwh": costs["cost_2000_kwh"],
                "efl_url": efl_url,
                "plan_url": plan.get("go_to_plan", ""),
                "efl_parsed": efl_path is not None,
            }

            # Store in database
            with get_session() as session:
                store_plan(session, plan_data, classifications)

            return plan_data

        except Exception as e:
            print(f"  ✗ Error extracting plan data: {e}")
            return None

    async def _download_efl(self, efl_url: str, plan_id: str) -> Optional[Path]:
        """Download EFL PDF.

        Args:
            efl_url: URL to EFL PDF
            plan_id: Plan identifier

        Returns:
            Path to downloaded PDF or None if download fails
        """
        try:
            response = await self.client.get(efl_url)
            response.raise_for_status()

            # Save PDF
            pdf_filename = f"{plan_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
            pdf_path = EFL_DIR / pdf_filename

            with open(pdf_path, "wb") as f:
                f.write(response.content)

            return pdf_path

        except Exception as e:
            print(f"  ✗ Error downloading EFL: {e}")
            return None

    def _generate_plan_id(self, provider: str, plan_name: str, zip_code: str) -> str:
        """Generate unique plan ID.

        Args:
            provider: Provider name
            plan_name: Plan name
            zip_code: ZIP code

        Returns:
            Unique plan identifier
        """
        # Create hash of provider + plan name + zip
        content = f"{provider}_{plan_name}_{zip_code}".lower()
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _extract_contract_length(self, plan_card) -> Optional[int]:
        """Extract contract length in months.

        Args:
            plan_card: BeautifulSoup element

        Returns:
            Contract length in months or None
        """
        try:
            # Look for contract length text (adjust selector)
            contract_text = plan_card.select_one(".contract-length")
            if contract_text:
                text = contract_text.text.lower()
                if "month" in text:
                    # Extract number
                    import re
                    match = re.search(r"(\d+)", text)
                    if match:
                        return int(match.group(1))
        except:
            pass
        return None

    def _extract_renewable_percentage(self, renewable_desc: str) -> Optional[int]:
        """Extract renewable percentage from description.

        Args:
            renewable_desc: Renewable energy description (e.g., "100% Renewable")

        Returns:
            Renewable percentage or None
        """
        try:
            import re
            match = re.search(r"(\d+)%?\s*renewable", renewable_desc, re.IGNORECASE)
            if match:
                return int(match.group(1))
        except:
            pass
        return None

    def _extract_cancellation_fee(self, pricing_details: str) -> Optional[float]:
        """Extract cancellation fee from pricing details.

        Args:
            pricing_details: Pricing details text

        Returns:
            Cancellation fee or None
        """
        try:
            import re
            # Look for patterns like "$150.00" or "$150"
            match = re.search(r"\$(\d+(?:\.\d+)?)", pricing_details)
            if match:
                return float(match.group(1))
        except:
            pass
        return None

    def _create_rate_structure_from_api(self, plan: dict) -> dict:
        """Create rate structure from API data (fallback when EFL parsing fails).

        Args:
            plan: Plan dictionary from API

        Returns:
            Rate structure dictionary
        """
        from .models import RateStructure
        
        # Extract rates
        rate_500 = plan.get("price_kwh500", 0) / 100  # API returns cents per kWh
        rate_1000 = plan.get("price_kwh1000", 0) / 100
        rate_2000 = plan.get("price_kwh2000", 0) / 100
        
        # Create tiered structure (simplified)
        tiers = [
            {"start_kwh": 0, "end_kwh": 500, "rate_per_kwh": rate_500},
            {"start_kwh": 500, "end_kwh": 2000, "rate_per_kwh": rate_1000},
            {"start_kwh": 2000, "end_kwh": None, "rate_per_kwh": rate_2000},
        ]
        
        renewable_desc = plan.get("renewable_energy_description", "")
        renewable_pct = self._extract_renewable_percentage(renewable_desc)
        
        pricing_details = plan.get("pricing_details", "")
        cancellation_fee = self._extract_cancellation_fee(pricing_details)
        
        return RateStructure(
            plan_type="fixed" if plan.get("rate_type") == "Fixed" else "variable",
            base_charge=0.0,  # API doesn't separate base charge
            tiers=tiers,
            tdu_delivery_rate=0.04,  # Standard estimate
            renewable_percentage=renewable_pct,
            has_time_of_use=plan.get("timeofuse", False),
            early_termination_fee=cancellation_fee,
        )

    def _calculate_costs_from_api(self, plan: dict) -> dict:
        """Calculate costs from API data (when EFL parsing isn't available).

        Args:
            plan: Plan dictionary from API

        Returns:
            Dictionary with cost breakdowns for 500, 1000, 2000 kWh
        """
        costs = {}
        
        for usage in [500, 1000, 2000]:
            rate_key = f"price_kwh{usage}"
            rate = plan.get(rate_key, 0) / 100  # Convert cents to dollars
            
            # Simplified calculation (API gives total rate including TDU)
            total = rate * usage
            
            costs[f"cost_{usage}_kwh"] = {
                "usage_kwh": usage,
                "base_charge_usd": 0.0,
                "energy_charge_usd": total * 0.6,  # Estimate
                "energy_rate_per_kwh": rate,
                "tdu_delivery_usd": total * 0.3,  # Estimate
                "taxes_fees_usd": total * 0.1,  # Estimate
                "total_monthly_usd": total,
                "breakdown_by_tier": [],
            }
        
        return costs

    def _extract_classifications_from_api(self, plan: dict, rate_structure) -> List[str]:
        """Extract plan classifications from API data.

        Args:
            plan: Plan dictionary from API
            rate_structure: Parsed rate structure

        Returns:
            List of classification tags
        """
        classifications = []

        # Get renewable percentage
        renewable_pct = None
        if hasattr(rate_structure, 'renewable_percentage'):
            renewable_pct = rate_structure.renewable_percentage
        else:
            renewable_desc = plan.get("renewable_energy_description", "")
            renewable_pct = self._extract_renewable_percentage(renewable_desc)

        # Check for green/renewable plans
        if renewable_pct and renewable_pct >= 50:
            classifications.append("green")
        if renewable_pct == 100:
            classifications.append("100_renewable")

        # Check for time-of-use plans
        if plan.get("timeofuse", False):
            classifications.append("time_of_use")
        elif hasattr(rate_structure, 'has_time_of_use') and rate_structure.has_time_of_use:
            classifications.append("time_of_use")

        # Check for EV plans
        plan_name = plan.get("plan_name", "").lower()
        special_terms = plan.get("special_terms", "").lower()
        if "ev" in plan_name or "electric vehicle" in plan_name or "ev" in special_terms:
            classifications.append("ev")

        # Check for fixed vs variable
        rate_type = plan.get("rate_type", "")
        if rate_type == "Fixed":
            classifications.append("fixed_rate")
        elif rate_type == "Variable":
            classifications.append("variable_rate")

        # Check for prepaid
        if plan.get("prepaid", False):
            classifications.append("prepaid")

        # Check for new customer only
        if plan.get("new_customer", False):
            classifications.append("new_customer_only")

        return classifications

    def _extract_classifications(self, plan_card, rate_structure) -> List[str]:
        """Extract plan classifications (old HTML-based method).

        Args:
            plan_card: BeautifulSoup element
            rate_structure: Parsed rate structure

        Returns:
            List of classification tags
        """
        classifications = []

        # Check for green/renewable plans
        if rate_structure.renewable_percentage and rate_structure.renewable_percentage >= 50:
            classifications.append("green")
        if rate_structure.renewable_percentage == 100:
            classifications.append("100_renewable")

        # Check for time-of-use plans
        if rate_structure.has_time_of_use:
            classifications.append("time_of_use")

        # Check for EV plans (look for keywords in plan name or card)
        text = plan_card.text.lower()
        if "ev" in text or "electric vehicle" in text:
            classifications.append("ev")

        # Check for fixed vs variable
        if rate_structure.plan_type == "fixed":
            classifications.append("fixed_rate")
        elif rate_structure.plan_type == "variable":
            classifications.append("variable_rate")

        return classifications


def cleanup_old_files():
    """Clean up old EFL PDFs and log files."""
    print("Cleaning up old files...")

    # Clean up EFL PDFs older than retention period
    cutoff_date = datetime.now() - timedelta(days=EFL_RETENTION_DAYS)
    cutoff_timestamp = cutoff_date.timestamp()

    removed_efls = 0
    for pdf_file in EFL_DIR.glob("*.pdf"):
        if pdf_file.stat().st_mtime < cutoff_timestamp:
            pdf_file.unlink()
            removed_efls += 1

    print(f"  Removed {removed_efls} old EFL PDFs")

    # Clean up old log files
    cleanup_old_log_files(LOG_RETENTION_DAYS)
    print(f"  Cleaned up log files older than {LOG_RETENTION_DAYS} days")


async def scrape_bucket(bucket_id: int) -> int:
    """Scrape all ZIP codes in a bucket.

    Args:
        bucket_id: Bucket ID (0-6 for days of week)

    Returns:
        Total number of plans scraped
    """
    # Determine which ZIP codes belong to this bucket
    bucket_zips = [z for z in ZIP_CODES if int(z) % 7 == bucket_id]

    print(f"\n=== Scraping Bucket {bucket_id} ===")
    print(f"ZIP codes: {', '.join(bucket_zips)}\n")

    scraper = PowerToChooseScraper()
    total_plans = 0

    try:
        for zip_code in bucket_zips:
            count = await scraper.scrape_zip_code(zip_code)
            total_plans += count
            await asyncio.sleep(REQUEST_DELAY_SECONDS * 2)  # Extra delay between ZIP codes

    finally:
        await scraper.close()

    print(f"\n=== Bucket {bucket_id} Complete ===")
    print(f"Total plans scraped: {total_plans}\n")

    return total_plans


async def scrape_today():
    """Scrape the bucket for today's day of week."""
    # Cleanup old data first
    cleanup_old_files()

    # Determine today's bucket (0=Sunday, 6=Saturday)
    bucket_id = datetime.now().weekday()
    if bucket_id == 6:  # Adjust Sunday from 6 to 0
        bucket_id = 0
    else:
        bucket_id += 1

    return await scrape_bucket(bucket_id)


async def scrape_all():
    """Scrape all buckets (all ZIP codes)."""
    # Cleanup old data first
    cleanup_old_files()

    total_plans = 0
    for bucket_id in range(7):
        count = await scrape_bucket(bucket_id)
        total_plans += count

    print(f"\n=== All Buckets Complete ===")
    print(f"Total plans scraped: {total_plans}\n")

    return total_plans


def main():
    """CLI entry point for scraper."""
    import sys

    # Initialize database
    init_database()

    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        # Scrape all buckets
        asyncio.run(scrape_all())
    else:
        # Scrape today's bucket
        asyncio.run(scrape_today())


if __name__ == "__main__":
    main()
