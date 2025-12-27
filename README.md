# IBKR Dashboard

Interactive dashboard for visualizing and analyzing Interactive Brokers (IBKR) trading statement data.

## Features

### Portfolio Overview
- Key metrics: Ending value, realized/unrealized P/L, total performance
- Additional metrics: Total deposits, ROI, total return percentage, time-weighted return
- Net Asset Value breakdown with visual asset allocation

### Performance Analysis
- **Stocks & Options Performance**: Separate tabs with search and sort functionality
- Realized and unrealized P/L tracking
- Performance by underlying symbol for options
- Interactive charts and tables

### Trade Analysis
- **Trade Statistics**: Win rate, profit factor, average win/loss, largest trades
- **Advanced Filtering**: Date range, symbol, and asset category filters
- **Time-based Analysis**: Daily, monthly, and cumulative P/L charts
- **Asset Category Breakdown**: Performance distribution by asset type
- Detailed trade history table

### Open Positions
- Current positions with unrealized P/L tracking
- Summary by asset category
- Detailed position table

### Cash Flow
- Deposits and withdrawals tracking
- Cumulative cash flow visualization

### Export Functionality
- Export trades, performance, and positions data to CSV
- Download buttons in sidebar

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Place your IBKR statement CSV file in the project directory
2. Run the dashboard:
```bash
streamlit run dashboard.py
```

3. Select your statement file from the sidebar
4. Explore the various sections and visualizations

## File Structure

- `parser.py`: IBKR CSV statement parser
- `dashboard.py`: Streamlit dashboard application
- `requirements.txt`: Python dependencies
- `*.csv`: IBKR statement files

## Data Sections Parsed

- Statement metadata (period, generation date)
- Account information
- Net Asset Value (NAV)
- Change in NAV
- Realized & Unrealized Performance Summary
- Open Positions
- Trades
- Deposits & Withdrawals
- Interest

## Notes

The parser handles the hierarchical CSV format used by IBKR statements. Make sure your CSV files follow the standard IBKR statement format.

