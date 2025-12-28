# IBKR Dashboard

Interactive dashboard for visualizing and analyzing Interactive Brokers (IBKR) trading statement data.

## 🌐 Web Access

**Live Dashboard**: [https://ibkr-dashboard.streamlit.app/](https://ibkr-dashboard.streamlit.app/)

You can use the dashboard directly in your browser without any installation. Simply upload your IBKR statement CSV file and start analyzing your trading data!

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

## Installation (Local Development)

If you want to run the dashboard locally:

1. Clone this repository:
```bash
git clone <repository-url>
cd ibkr_dashboard
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Generating IBKR Statements

The dashboard supports two types of IBKR statement formats:

1. **Realized Summary** (Recommended for detailed P/L analysis)
   - Provides separate "Realized P/L" and "Unrealized P/L" breakdowns
   - Best for analyzing closed positions and open position performance separately
   - Generate in IBKR: Reports → Realized Summary → Export as CSV

2. **Activity Statement** (Also supported)
   - Uses "Mark-to-Market" for total P/L
   - Does not separate realized vs unrealized P/L
   - Generate in IBKR: Reports → Activity Statement → Export as CSV

**Note**: Both formats work with the dashboard, but "Realized Summary" provides more detailed metrics.

### Running the Dashboard

#### Option 1: Use the Web Version (Recommended)
1. Visit [https://ibkr-dashboard.streamlit.app/](https://ibkr-dashboard.streamlit.app/)
2. Upload your IBKR statement CSV file using the file uploader in the sidebar
3. Explore the various sections and visualizations

#### Option 2: Run Locally
1. Generate your IBKR statement CSV file (see above)
2. Run the dashboard:
```bash
streamlit run dashboard.py
```

3. Upload your CSV file using the file uploader in the sidebar, or place it in the project directory and select it from the dropdown
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

- The parser handles the hierarchical CSV format used by IBKR statements
- The dashboard supports both **Realized Summary** and **Activity Statement** formats
- For best results with detailed P/L analysis, use the **Realized Summary** format
- Make sure your CSV files follow the standard IBKR statement format
- CSV files with BOM (Byte Order Mark) characters are automatically handled

