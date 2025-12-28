"""EFL (Electricity Facts Label) PDF parser.

Parses EFL PDFs to extract rate structures, tiered pricing, and fees.
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import pypdf

from .models import RateStructure


class EFLParser:
    """Parser for Electricity Facts Label PDFs."""

    def __init__(self, pdf_path: Path):
        """Initialize parser with PDF file path.

        Args:
            pdf_path: Path to EFL PDF file
        """
        self.pdf_path = pdf_path
        self.text = self._extract_text()

    def _extract_text(self) -> str:
        """Extract text from PDF.

        Returns:
            Extracted text content
        """
        try:
            with open(self.pdf_path, "rb") as f:
                pdf_reader = pypdf.PdfReader(f)
                text_parts = []
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text())
                return "\n".join(text_parts)
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {e}")

    def parse(self) -> RateStructure:
        """Parse EFL to extract rate structure.

        Returns:
            RateStructure object

        Raises:
            ValueError: If parsing fails
        """
        try:
            # Extract key components
            plan_type = self._extract_plan_type()
            base_charge = self._extract_base_charge()
            tiers = self._extract_rate_tiers()
            tdu_rate = self._extract_tdu_rate()
            renewable_pct = self._extract_renewable_percentage()
            termination_fee = self._extract_termination_fee()
            has_tou = self._has_time_of_use()

            return RateStructure(
                plan_type=plan_type,
                base_charge=base_charge,
                tiers=tiers,
                tdu_delivery_rate=tdu_rate,
                renewable_percentage=renewable_pct,
                has_time_of_use=has_tou,
                early_termination_fee=termination_fee,
            )
        except Exception as e:
            raise ValueError(f"Failed to parse EFL: {e}")

    def _extract_plan_type(self) -> str:
        """Determine plan type (fixed, variable, time_of_use)."""
        text_lower = self.text.lower()

        if "time of use" in text_lower or "time-of-use" in text_lower:
            return "time_of_use"
        elif "variable" in text_lower and "price" in text_lower:
            return "variable"
        else:
            return "fixed"

    def _extract_base_charge(self) -> float:
        """Extract monthly base charge.

        Returns:
            Base charge in dollars
        """
        # Look for patterns like "Base Charge: $9.95" or "Monthly Charge $9.95"
        patterns = [
            r"base\s+charge[:\s]+\$?([\d.]+)",
            r"monthly\s+charge[:\s]+\$?([\d.]+)",
            r"customer\s+charge[:\s]+\$?([\d.]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                return float(match.group(1))

        # Default to 0 if not found
        return 0.0

    def _extract_rate_tiers(self) -> List[Dict[str, Any]]:
        """Extract tiered pricing structure.

        Returns:
            List of tier dictionaries
        """
        tiers = []

        # Look for patterns like "500 kWh: $0.095 per kWh"
        # Common patterns in EFLs:
        # - "0-500 kWh @ $0.095/kWh"
        # - "501-2000 kWh: $0.085 per kWh"
        # - "Above 2000 kWh $0.080"

        tier_pattern = r"(\d+)\s*-?\s*(\d+)?\s*kwh.*?\$?([\d.]+)\s*(?:per\s+kwh|\/kwh|¢)"

        for match in re.finditer(tier_pattern, self.text, re.IGNORECASE):
            start_kwh = int(match.group(1))
            end_kwh = int(match.group(2)) if match.group(2) else None
            rate = float(match.group(3))

            # If rate appears to be in cents (> 1), convert to dollars
            if rate > 1:
                rate = rate / 100

            tiers.append({
                "start_kwh": start_kwh,
                "end_kwh": end_kwh,
                "rate_per_kwh": rate,
            })

        # If no tiers found, look for a single flat rate
        if not tiers:
            flat_rate_pattern = r"energy\s+charge[:\s]+\$?([\d.]+)\s*(?:per\s+kwh|\/kwh|¢)"
            match = re.search(flat_rate_pattern, self.text, re.IGNORECASE)
            if match:
                rate = float(match.group(1))
                if rate > 1:
                    rate = rate / 100
                tiers.append({
                    "start_kwh": 0,
                    "end_kwh": None,
                    "rate_per_kwh": rate,
                })

        return tiers

    def _extract_tdu_rate(self) -> Optional[float]:
        """Extract TDU delivery rate.

        Returns:
            TDU rate per kWh or None
        """
        # Look for TDU/TDSP charges
        patterns = [
            r"tdu.*?\$?([\d.]+)\s*(?:per\s+kwh|\/kwh|¢)",
            r"tdsp.*?\$?([\d.]+)\s*(?:per\s+kwh|\/kwh|¢)",
            r"delivery.*?\$?([\d.]+)\s*(?:per\s+kwh|\/kwh|¢)",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                rate = float(match.group(1))
                if rate > 1:
                    rate = rate / 100
                return rate

        return None

    def _extract_renewable_percentage(self) -> Optional[int]:
        """Extract renewable energy percentage.

        Returns:
            Renewable percentage (0-100) or None
        """
        pattern = r"(\d+)%?\s+renewable"
        match = re.search(pattern, self.text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def _extract_termination_fee(self) -> Optional[float]:
        """Extract early termination fee.

        Returns:
            Termination fee in dollars or None
        """
        patterns = [
            r"early\s+termination.*?\$?([\d.]+)",
            r"cancellation.*?fee.*?\$?([\d.]+)",
            r"termination.*?fee.*?\$?([\d.]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                return float(match.group(1))

        return None

    def _has_time_of_use(self) -> bool:
        """Check if plan has time-of-use rates.

        Returns:
            True if time-of-use rates detected
        """
        tou_keywords = ["time of use", "time-of-use", "peak hours", "off-peak"]
        text_lower = self.text.lower()
        return any(keyword in text_lower for keyword in tou_keywords)


def parse_efl_file(pdf_path: Path) -> RateStructure:
    """Parse an EFL PDF file.

    Args:
        pdf_path: Path to EFL PDF

    Returns:
        RateStructure object

    Raises:
        ValueError: If parsing fails
    """
    parser = EFLParser(pdf_path)
    return parser.parse()
