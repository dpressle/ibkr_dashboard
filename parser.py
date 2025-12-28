"""
IBKR Statement CSV Parser
Parses Interactive Brokers statement CSV files into structured data.
"""

import csv
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime


class IBKRStatementParser:
    """Parser for IBKR statement CSV files."""

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.raw_data: List[List[str]] = []
        self.parsed_data: Dict[str, Any] = {}

    def parse(self) -> Dict[str, Any]:
        """Parse the CSV file and return structured data."""
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            self.raw_data = list(reader)

        self._parse_statement_info()
        self._parse_account_info()
        self._parse_nav()
        self._parse_change_in_nav()
        self._parse_performance_summary()
        self._parse_open_positions()
        self._parse_trades()
        self._parse_deposits_withdrawals()
        self._parse_interest()

        return self.parsed_data

    def _get_section_data(self, section_name: str) -> List[List[str]]:
        """Extract data rows for a specific section."""
        section_data = []
        in_section = False

        for row in self.raw_data:
            if len(row) > 0:
                # Strip BOM and whitespace from section name
                row_section = row[0].lstrip('\ufeff').strip()
                if row_section == section_name:
                    if len(row) > 1 and row[1] == 'Header':
                        in_section = True
                        continue
                    elif in_section:
                        if len(row) > 1 and row[1] == 'Data':
                            section_data.append(row)
                        elif len(row) > 0 and row_section != section_name:
                            break

        return section_data

    def _parse_statement_info(self):
        """Parse statement metadata."""
        data = self._get_section_data('Statement')
        info = {}
        for row in data:
            if len(row) >= 4:
                field_name = row[2]
                field_value = row[3]
                info[field_name] = field_value
        self.parsed_data['statement'] = info

    def _parse_account_info(self):
        """Parse account information."""
        data = self._get_section_data('Account Information')
        info = {}
        for row in data:
            if len(row) >= 4:
                field_name = row[2]
                field_value = row[3]
                info[field_name] = field_value
        self.parsed_data['account'] = info

    def _parse_nav(self):
        """Parse Net Asset Value section."""
        nav_data = []
        headers = None
        in_section = False

        for i, row in enumerate(self.raw_data):
            if len(row) > 0 and row[0] == 'Net Asset Value':
                if len(row) > 1 and row[1] == 'Header':
                    if 'Asset Class' in row:
                        headers = row[2:]
                    elif len(row) > 2 and 'Time Weighted Rate of Return' in row[2]:
                        # Extract return percentage from next row
                        if i + 1 < len(self.raw_data):
                            next_row = self.raw_data[i + 1]
                            if len(next_row) > 1 and next_row[1] == 'Data' and len(next_row) > 2:
                                return_str = next_row[2]
                                self.parsed_data['time_weighted_return'] = return_str
                    in_section = True
                    continue
                elif in_section:
                    if len(row) > 1 and row[1] == 'Data':
                        if headers and len(row) > 2:
                            nav_data.append(row[2:])
                    elif len(row) > 0 and row[0] != 'Net Asset Value':
                        break

        if nav_data and headers:
            df = pd.DataFrame(nav_data, columns=headers)
            # Convert numeric columns
            numeric_cols = ['Prior Total', 'Current Long', 'Current Short', 'Current Total', 'Change']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            self.parsed_data['nav'] = df

    def _parse_change_in_nav(self):
        """Parse Change in NAV section."""
        data = self._get_section_data('Change in NAV')
        info = {}
        for row in data:
            if len(row) >= 4:
                field_name = row[2]
                field_value = row[3]
                try:
                    info[field_name] = float(field_value)
                except ValueError:
                    info[field_name] = field_value
        self.parsed_data['change_in_nav'] = info

    def _parse_performance_summary(self):
        """Parse Realized & Unrealized Performance Summary."""
        data = []
        headers = None
        in_section = False

        for row in self.raw_data:
            if len(row) > 0 and row[0] == 'Realized & Unrealized Performance Summary':
                if len(row) > 1 and row[1] == 'Header':
                    headers = row[2:]
                    in_section = True
                    continue
                elif in_section:
                    if len(row) > 1 and row[1] == 'Data':
                        data.append(row[2:])
                    elif len(row) > 0 and row[0] != 'Realized & Unrealized Performance Summary':
                        break

        if data and headers:
            df = pd.DataFrame(data, columns=headers)
            # Convert numeric columns
            numeric_cols = ['Cost Adj.', 'Realized S/T Profit', 'Realized S/T Loss',
                          'Realized L/T Profit', 'Realized L/T Loss', 'Realized Total',
                          'Unrealized S/T Profit', 'Unrealized S/T Loss',
                          'Unrealized L/T Profit', 'Unrealized L/T Loss',
                          'Unrealized Total', 'Total']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            self.parsed_data['performance'] = df

    def _parse_open_positions(self):
        """Parse Open Positions section."""
        positions = []
        headers = None
        in_section = False

        for row in self.raw_data:
            if len(row) > 0 and row[0] == 'Open Positions':
                if len(row) > 1 and row[1] == 'Header':
                    headers = row[2:]
                    in_section = True
                    continue
                elif in_section:
                    if len(row) > 1 and row[1] == 'Data':
                        if row[2] == 'Summary':  # Skip totals
                            positions.append(row[3:])
                    elif len(row) > 0 and row[0] != 'Open Positions':
                        break

        if positions and headers:
            df = pd.DataFrame(positions, columns=headers[1:])  # Skip DataDiscriminator
            # Convert numeric columns
            numeric_cols = ['Quantity', 'Mult', 'Cost Price', 'Cost Basis',
                          'Close Price', 'Value', 'Unrealized P/L']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            self.parsed_data['open_positions'] = df

    def _parse_trades(self):
        """Parse Trades section."""
        trades = []
        headers = None
        in_section = False

        for row in self.raw_data:
            if len(row) > 0 and row[0] == 'Trades':
                if len(row) > 1 and row[1] == 'Header':
                    headers = row[2:]
                    in_section = True
                    continue
                elif in_section:
                    if len(row) > 1 and row[1] == 'Data':
                        if row[2] == 'Order':  # Only actual trades, not subtotals
                            trades.append(row[3:])
                    elif len(row) > 0 and row[0] != 'Trades':
                        break

        if trades and headers:
            df = pd.DataFrame(trades, columns=headers[1:])  # Skip DataDiscriminator
            # Convert date/time
            if 'Date/Time' in df.columns:
                df['Date/Time'] = pd.to_datetime(df['Date/Time'], format='%Y-%m-%d, %H:%M:%S', errors='coerce')
            # Convert numeric columns
            numeric_cols = ['Quantity', 'T. Price', 'Proceeds', 'Comm/Fee',
                          'Basis', 'Realized P/L']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            self.parsed_data['trades'] = df

    def _parse_deposits_withdrawals(self):
        """Parse Deposits & Withdrawals section."""
        data = []
        headers = None
        in_section = False

        for row in self.raw_data:
            if len(row) > 0 and row[0] == 'Deposits & Withdrawals':
                if len(row) > 1 and row[1] == 'Header':
                    headers = row[2:]
                    in_section = True
                    continue
                elif in_section:
                    if len(row) > 1 and row[1] == 'Data':
                        if row[2] != 'Total':  # Skip total row
                            data.append(row[2:])
                    elif len(row) > 0 and row[0] != 'Deposits & Withdrawals':
                        break

        if data and headers:
            df = pd.DataFrame(data, columns=headers)
            if 'Settle Date' in df.columns:
                df['Settle Date'] = pd.to_datetime(df['Settle Date'], errors='coerce')
            if 'Amount' in df.columns:
                df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
            self.parsed_data['deposits_withdrawals'] = df

    def _parse_interest(self):
        """Parse Interest section."""
        data = []
        headers = None
        in_section = False

        for row in self.raw_data:
            if len(row) > 0 and row[0] == 'Interest':
                if len(row) > 1 and row[1] == 'Header':
                    headers = row[2:]
                    in_section = True
                    continue
                elif in_section:
                    if len(row) > 1 and row[1] == 'Data':
                        if row[2] != 'Total':  # Skip total row
                            data.append(row[2:])
                    elif len(row) > 0 and row[0] != 'Interest':
                        break

        if data and headers:
            df = pd.DataFrame(data, columns=headers)
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            if 'Amount' in df.columns:
                df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
            self.parsed_data['interest'] = df

