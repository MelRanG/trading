from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.task13_earnings_strength.source import eps_pairs


def test_quarter_header_dates_with_filing_typography_and_annual_columns():
    source = b"""<table>
      <tr><td>Three Months Ended</td><td>Year Ended</td></tr>
      <tr><td>January 28,2024</td><td>January 29,2023</td><td>January 28,2024</td><td>January 29,2023</td></tr>
      <tr><td>Net sales</td><td>100</td><td>90</td><td>500</td><td>490</td></tr>
      <tr><td>Net earnings</td><td>10</td><td>9</td><td>50</td><td>49</td></tr>
      <tr><td>Diluted earnings per share</td><td>$2.82</td><td>$3.30</td><td>$15.11</td><td>$16.69</td></tr>
      <tr><td>Adjusted diluted earnings per share</td><td>2.99</td><td>3.56</td></tr>
    </table>"""
    assert list(eps_pairs(source, date(2024, 2, 21))) == [("2024-01-28", "2023-01-29", "2.82", "3.3")]
    assert not eps_pairs(source.replace(b"Three Months Ended", b"Year Ended"), date(2024, 2, 21))


def test_explicit_quarter_day_and_comparison_year_columns():
    source = b"""<table>
      <tr><td>Three Months Ended September 30,</td><td>Nine Months ended September 30,</td></tr>
      <tr><td>2024</td><td>2023</td><td>2024</td><td>2023</td></tr>
      <tr><td>Total revenues</td><td>400</td><td>420</td><td>1800</td><td>1300</td></tr>
      <tr><td>Net income</td><td>10</td><td>19</td><td>50</td><td>49</td></tr>
      <tr><td>Net income per share</td></tr>
      <tr><td>Diluted</td><td>(0.17)</td><td>0.26</td><td>0.99</td><td>0.72</td></tr>
    </table>"""
    assert list(eps_pairs(source, date(2024, 11, 21))) == [("2024-09-30", "2023-09-30", "-0.17", "0.26")]
