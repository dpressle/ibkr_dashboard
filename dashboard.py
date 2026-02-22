"""
IBKR Dashboard - Streamlit application for visualizing trading data
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from parser import IBKRStatementParser
import os
from pathlib import Path
from datetime import datetime, date
import io
import tempfile
import re

# Page configuration
st.set_page_config(
    page_title="IBKR Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .positive {
        color: #00cc00;
    }
    .negative {
        color: #ff3333;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner="Parsing IBKR statement...")
def load_data(csv_path: str):
    """Load and parse IBKR statement data."""
    parser = IBKRStatementParser(csv_path)
    data = parser.parse()
    return data


def save_uploaded_file(uploaded_file):
    """Save uploaded file to temporary location and return path."""
    # Create a temporary file
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='wb')
    tfile.write(uploaded_file.getvalue())
    tfile.close()
    return tfile.name


def format_currency(value: float) -> str:
    """Format value as currency."""
    return f"${value:,.2f}"


def format_percentage(value: str) -> str:
    """Format percentage value."""
    return value if isinstance(value, str) else f"{value:.2f}%"


def calculate_trade_stats(trades_df: pd.DataFrame) -> dict:
    """Calculate trade statistics."""
    if trades_df.empty or 'Realized P/L' not in trades_df.columns:
        return {}

    # Filter out zero P/L trades (opening positions)
    closed_trades = trades_df[trades_df['Realized P/L'] != 0].copy()

    if closed_trades.empty:
        return {}

    # Optionally group by symbol to get net position P/L instead of individual trade legs
    # This is useful for options spreads where multiple trades make up one position
    if 'Symbol' in closed_trades.columns:
        # Calculate net P/L by symbol (aggregate all trades for same symbol)
        symbol_pl = closed_trades.groupby('Symbol')['Realized P/L'].sum().reset_index()
        symbol_pl.columns = ['Symbol', 'Net_P/L']

        # Use net position P/L for statistics instead of individual trade P/L
        winning_positions = symbol_pl[symbol_pl['Net_P/L'] > 0]
        losing_positions = symbol_pl[symbol_pl['Net_P/L'] < 0]

        # Find largest win/loss from net positions
        largest_win_pos = symbol_pl.loc[symbol_pl['Net_P/L'].idxmax()] if not symbol_pl.empty else None
        largest_loss_pos = symbol_pl.loc[symbol_pl['Net_P/L'].idxmin()] if not symbol_pl.empty else None

        # Count individual trades for win rate
        winning_trades = closed_trades[closed_trades['Realized P/L'] > 0]
        losing_trades = closed_trades[closed_trades['Realized P/L'] < 0]

        stats = {
            'total_trades': len(closed_trades),
            'total_positions': len(symbol_pl),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'winning_positions': len(winning_positions),
            'losing_positions': len(losing_positions),
            'win_rate': len(winning_trades) / len(closed_trades) * 100 if len(closed_trades) > 0 else 0,
            'position_win_rate': len(winning_positions) / len(symbol_pl) * 100 if len(symbol_pl) > 0 else 0,
            'total_pl': closed_trades['Realized P/L'].sum(),
            'avg_win': winning_trades['Realized P/L'].mean() if len(winning_trades) > 0 else 0,
            'avg_loss': losing_trades['Realized P/L'].mean() if len(losing_trades) > 0 else 0,
            'largest_win': largest_win_pos['Net_P/L'] if largest_win_pos is not None else closed_trades['Realized P/L'].max(),
            'largest_loss': largest_loss_pos['Net_P/L'] if largest_loss_pos is not None else closed_trades['Realized P/L'].min(),
            'largest_win_symbol': largest_win_pos['Symbol'] if largest_win_pos is not None else None,
            'largest_loss_symbol': largest_loss_pos['Symbol'] if largest_loss_pos is not None else None,
            'profit_factor': abs(winning_trades['Realized P/L'].sum() / losing_trades['Realized P/L'].sum())
                            if len(losing_trades) > 0 and losing_trades['Realized P/L'].sum() != 0 else 0,
        }
    else:
        # Fallback to individual trade statistics if no Symbol column
        winning_trades = closed_trades[closed_trades['Realized P/L'] > 0]
        losing_trades = closed_trades[closed_trades['Realized P/L'] < 0]

        stats = {
            'total_trades': len(closed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(closed_trades) * 100 if len(closed_trades) > 0 else 0,
            'total_pl': closed_trades['Realized P/L'].sum(),
            'avg_win': winning_trades['Realized P/L'].mean() if len(winning_trades) > 0 else 0,
            'avg_loss': losing_trades['Realized P/L'].mean() if len(losing_trades) > 0 else 0,
            'largest_win': closed_trades['Realized P/L'].max(),
            'largest_loss': closed_trades['Realized P/L'].min(),
            'profit_factor': abs(winning_trades['Realized P/L'].sum() / losing_trades['Realized P/L'].sum())
                            if len(losing_trades) > 0 and losing_trades['Realized P/L'].sum() != 0 else 0,
        }

    return stats


def export_to_csv(df: pd.DataFrame, filename: str):
    """Convert DataFrame to CSV and return as bytes."""
    return df.to_csv(index=False).encode('utf-8')


def main():
    st.title("📊 IBKR Trading Dashboard")

    # Sidebar for file selection
    st.sidebar.header("Data Source")

    # File upload option
    uploaded_file = st.sidebar.file_uploader(
        "📁 Upload IBKR Statement CSV",
        type=['csv'],
        help="Upload your IBKR statement CSV file here"
    )

    # Also show existing files in directory
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]

    selected_file = None
    file_source = None

    if uploaded_file is not None:
        # Use uploaded file
        try:
            # Save uploaded file temporarily
            temp_path = save_uploaded_file(uploaded_file)
            selected_file = uploaded_file.name
            file_source = temp_path
            st.sidebar.success(f"✅ Loaded: {uploaded_file.name}")
        except Exception as e:
            st.sidebar.error(f"Error processing uploaded file: {str(e)}")
            return
    elif csv_files:
        # Use file from directory
        selected_file = st.sidebar.selectbox("Or Select Statement File from Directory", csv_files)
        file_source = selected_file
    else:
        st.sidebar.info("👆 Upload a CSV file above or place CSV files in the current directory")
        st.info("Please upload an IBKR statement CSV file using the file uploader in the sidebar.")
        return

    if selected_file and file_source:
        try:
            data = load_data(file_source)

            # Display account info
            if 'account' in data:
                account = data['account']
                st.sidebar.markdown("### Account Information")
                st.sidebar.write(f"**Account:** {account.get('Account', 'N/A')}")
                st.sidebar.write(f"**Name:** {account.get('Name', 'N/A')}")
                st.sidebar.write(f"**Type:** {account.get('Account Type', 'N/A')}")

            # Statement period - only show if we have valid period data
            if 'statement' in data and isinstance(data['statement'], dict):
                period = data['statement'].get('Period')
                if period and period.strip() and period != 'N/A':
                    st.sidebar.markdown("### Statement Period")
                    st.sidebar.write(period)
                # If period is not available, don't show this section at all

            # Export section
            st.sidebar.markdown("---")
            st.sidebar.markdown("### Export Data")

            with st.sidebar.expander("ℹ️ About Export", expanded=False):
                st.markdown("""
                **Export Options:**
                - **Trades**: Export all trade data including dates, symbols, quantities, prices, and P/L
                - **Performance**: Export performance summary by symbol and asset category
                - **Open Positions**: Export current positions with cost basis and unrealized P/L

                Data is exported as CSV files that can be opened in Excel or other spreadsheet applications.
                """)

            export_options = []
            if 'trades' in data and not data['trades'].empty:
                export_options.append('Trades')
            if 'performance' in data and not data['performance'].empty:
                export_options.append('Performance')
            if 'open_positions' in data and not data['open_positions'].empty:
                export_options.append('Open Positions')

            if export_options:
                export_type = st.sidebar.selectbox("Export", ['None'] + export_options)
                if export_type != 'None':
                    if export_type == 'Trades':
                        csv_data = export_to_csv(data['trades'], 'trades.csv')
                        st.sidebar.download_button(
                            label="Download Trades CSV",
                            data=csv_data,
                            file_name=f"trades_{selected_file.replace('.csv', '')}.csv",
                            mime="text/csv"
                        )
                    elif export_type == 'Performance':
                        csv_data = export_to_csv(data['performance'], 'performance.csv')
                        st.sidebar.download_button(
                            label="Download Performance CSV",
                            data=csv_data,
                            file_name=f"performance_{selected_file.replace('.csv', '')}.csv",
                            mime="text/csv"
                        )
                    elif export_type == 'Open Positions':
                        csv_data = export_to_csv(data['open_positions'], 'positions.csv')
                        st.sidebar.download_button(
                            label="Download Positions CSV",
                            data=csv_data,
                            file_name=f"positions_{selected_file.replace('.csv', '')}.csv",
                            mime="text/csv"
                        )

            # Main metrics
            st.header("Portfolio Overview")

            with st.expander("ℹ️ About Portfolio Metrics", expanded=False):
                st.markdown("""
                **Portfolio Metrics Explained:**
                - **Ending Value**: Total account value at the end of the statement period
                - **Realized P/L**: Profit/Loss from closed positions (locked-in gains/losses)
                - **Unrealized P/L**: Current profit/loss on open positions (paper gains/losses)
                - **Total P/L**: Sum of realized and unrealized P/L
                - **Total Deposits**: Total amount deposited into the account
                - **Total Return %**: Simple return calculation: (Ending Value - Starting Value) / Starting Value
                - **ROI %**: Return on Invested Capital: (Ending Value - Invested Capital) / Invested Capital
                - **Realized ROI %**: Return based only on realized P/L: Realized P/L / Invested Capital
                - **Time Weighted Return**: Performance metric that eliminates the effect of cash flows
                """)

            col1, col2, col3, col4 = st.columns(4)

            # NAV metrics
            if 'change_in_nav' in data:
                nav_change = data['change_in_nav']
                starting_value = nav_change.get('Starting Value', 0)
                ending_value = nav_change.get('Ending Value', 0)

                # Handle both "Realized Summary" and "Activity Statement" formats
                # Realized Summary format has: Realized P/L, Change in Unrealized P/L
                # Activity Statement format has: Mark-to-Market
                is_activity_statement = 'Mark-to-Market' in nav_change

                if 'Realized P/L' in nav_change:
                    # Realized Summary format
                    realized_pl = nav_change.get('Realized P/L', 0)
                    unrealized_pl = nav_change.get('Change in Unrealized P/L', 0)
                    realized_label = "Realized P/L"
                    unrealized_label = "Unrealized P/L"
                elif is_activity_statement:
                    # Activity Statement format - Mark-to-Market is total P/L
                    mark_to_market = nav_change.get('Mark-to-Market', 0)
                    # For Activity Statement, we don't have separate realized/unrealized breakdown
                    # Mark-to-Market represents total performance
                    realized_pl = mark_to_market  # Use as total P/L
                    unrealized_pl = 0  # Not available in Activity Statement format
                    realized_label = "Mark-to-Market P/L"
                    unrealized_label = "Unrealized P/L (N/A)"
                else:
                    # Fallback
                    realized_pl = 0
                    unrealized_pl = 0
                    realized_label = "Realized P/L"
                    unrealized_label = "Unrealized P/L"

                deposits = nav_change.get('Deposits & Withdrawals', 0)

                with col1:
                    st.metric("Ending Value", format_currency(ending_value))

                with col2:
                    st.metric(realized_label, format_currency(realized_pl),
                             delta=f"{realized_pl/starting_value*100:.2f}%" if starting_value > 0 else "0%")

                with col3:
                    if is_activity_statement:
                        st.metric(unrealized_label, "N/A")
                    else:
                        st.metric(unrealized_label, format_currency(unrealized_pl),
                                 delta=f"{unrealized_pl/starting_value*100:.2f}%" if starting_value > 0 else "0%")

                with col4:
                    total_pl = realized_pl + unrealized_pl
                    st.metric("Total P/L", format_currency(total_pl),
                             delta=f"{total_pl/starting_value*100:.2f}%" if starting_value > 0 else "0%")

                # Additional metrics row
                col1, col2, col3, col4, col5 = st.columns(5)

                with col1:
                    st.metric("Total Deposits", format_currency(deposits))

                with col2:
                    if starting_value > 0:
                        total_return_pct = ((ending_value - starting_value) / starting_value) * 100
                        st.metric("Total Return %", f"{total_return_pct:.2f}%")
                    else:
                        st.metric("Total Return %", "N/A")

                with col3:
                    # Calculate return on invested capital (total ROI)
                    invested_capital = starting_value + deposits
                    if invested_capital > 0:
                        roi = ((ending_value - invested_capital) / invested_capital) * 100
                        st.metric("ROI %", f"{roi:.2f}%")
                    else:
                        st.metric("ROI %", "N/A")

                with col4:
                    # Calculate realized ROI (based only on realized P/L)
                    invested_capital = starting_value + deposits
                    if invested_capital > 0:
                        realized_roi = (realized_pl / invested_capital) * 100
                        st.metric("Realized ROI %", f"{realized_roi:.2f}%",
                                delta=f"{format_currency(realized_pl)}")
                    else:
                        st.metric("Realized ROI %", "N/A")

                with col5:
                    if 'time_weighted_return' in data:
                        st.metric("Time Weighted Return", data['time_weighted_return'])
                    else:
                        st.metric("Time Weighted Return", "N/A")

            # NAV breakdown
            if 'nav' in data:
                st.header("Net Asset Value Breakdown")

                with st.expander("ℹ️ About NAV Breakdown", expanded=False):
                    st.markdown("""
                    **Net Asset Value (NAV) Breakdown:**
                    - Shows the composition of your portfolio by asset class
                    - **Prior Total**: Value at the beginning of the period
                    - **Current Total**: Current value (Long positions - Short positions)
                    - **Change**: Net change during the period
                    - The pie chart shows asset allocation as a percentage of total portfolio value
                    """)

                nav_df = data['nav']

                col1, col2 = st.columns(2)

                with col1:
                    # Asset allocation pie chart
                    if 'Current Total' in nav_df.columns:
                        asset_df = nav_df[nav_df['Asset Class'] != 'Total'].copy()
                        fig = px.pie(
                            asset_df,
                            values='Current Total',
                            names='Asset Class',
                            title="Asset Allocation",
                            color_discrete_sequence=px.colors.qualitative.Set3
                        )
                        st.plotly_chart(fig, use_container_width=True)

                with col2:
                    # NAV table
                    st.subheader("NAV Details")
                    display_nav = nav_df[['Asset Class', 'Prior Total', 'Current Total', 'Change']].copy()
                    display_nav = display_nav.round(2)
                    st.dataframe(display_nav, use_container_width=True, hide_index=True)

                # Put Positions & Collateral Analysis
                if 'open_positions' in data and not data['open_positions'].empty:
                    st.subheader("Put Positions & Collateral Analysis")

                    positions_df = data['open_positions']
                    nav_total = nav_df[nav_df['Asset Class'] == 'Total']['Current Total'].iloc[0] if 'Total' in nav_df['Asset Class'].values else 0
                    nav_cash = nav_df[nav_df['Asset Class'] == 'Cash ']['Current Total'].iloc[0] if 'Cash ' in nav_df['Asset Class'].values else 0
                    nav_stocks = nav_df[nav_df['Asset Class'] == 'Stock']['Current Total'].iloc[0] if 'Stock' in nav_df['Asset Class'].values else 0

                    # Identify put positions (Symbol contains " P" or ends with " P")
                    put_positions = positions_df[
                        positions_df['Symbol'].str.contains(' P', regex=False, na=False) |
                        positions_df['Symbol'].str.endswith('P', na=False)
                    ].copy()

                    # Filter for short puts (negative quantity) - these require collateral
                    short_puts = put_positions[put_positions['Quantity'] < 0].copy()

                    if not short_puts.empty:
                        # Extract strike price from symbol (format: "SYMBOL DATE STRIKE P")
                        # Example: "APLD 28NOV25 30 P" -> strike is 30
                        # Example: "SOFI 28NOV25 28 P" -> strike is 28
                        def extract_strike(symbol):
                            try:
                                parts = symbol.split()
                                # Strike is typically the number before the last part (P or C)
                                # Format: SYMBOL DATE STRIKE P/C
                                if len(parts) >= 3:
                                    # Try the second-to-last part (before P/C)
                                    strike_str = parts[-2]
                                    try:
                                        strike = float(strike_str)
                                        return strike
                                    except ValueError:
                                        # If that fails, try finding any number before P/C
                                        for i in range(len(parts) - 2, -1, -1):
                                            try:
                                                strike = float(parts[i])
                                                return strike
                                            except ValueError:
                                                continue
                                return 0
                            except:
                                return 0

                        short_puts['Strike'] = short_puts['Symbol'].apply(extract_strike)
                        # Get multiplier from Mult column, default to 100 if not available
                        if 'Mult' in short_puts.columns:
                            short_puts['Multiplier'] = short_puts['Mult'].fillna(100)
                        else:
                            short_puts['Multiplier'] = 100
                        short_puts['Abs_Quantity'] = short_puts['Quantity'].abs()

                        # Calculate collateral requirement: Strike × |Quantity| × Multiplier
                        short_puts['Collateral_Required'] = short_puts['Strike'] * short_puts['Abs_Quantity'] * short_puts['Multiplier']
                        total_put_collateral = short_puts['Collateral_Required'].sum()

                        # Calculate free cash
                        free_cash = nav_cash - total_put_collateral
                        free_cash_pct = (free_cash / nav_total * 100) if nav_total > 0 else 0
                        allocated_collateral_pct = (total_put_collateral / nav_total * 100) if nav_total > 0 else 0

                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown("### Collateral Breakdown")
                            st.markdown(f"""
                            **Total Account Value:** ${nav_total:,.2f}

                            **Cash:** ${nav_cash:,.2f}

                            **Total Put Collateral Required:** ${total_put_collateral:,.2f}

                            **Free Cash:** ${free_cash:,.2f}
                            """)

                            # Metrics
                            st.metric("Free Cash", format_currency(free_cash),
                                     delta=f"{free_cash_pct:.2f}%")
                            st.metric("Allocated Collateral", format_currency(total_put_collateral),
                                     delta=f"{allocated_collateral_pct:.2f}%")

                        with col2:
                            st.markdown("### Calculation")
                            st.markdown(f"""
                            **Free Cash % Formula:**
                            ```
                            (Cash - Put Collateral) / Total Account Value × 100
                            ```

                            **Calculation:**
                            ```
                            (${nav_cash:,.2f} - ${total_put_collateral:,.2f}) / ${nav_total:,.2f} × 100
                            = ${free_cash:,.2f} / ${nav_total:,.2f} × 100
                            = {free_cash_pct:.2f}%
                            ```

                            **Allocated Collateral %:**
                            ```
                            ${total_put_collateral:,.2f} / ${nav_total:,.2f} × 100
                            = {allocated_collateral_pct:.2f}%
                            ```
                            """)

                        # Show put positions table
                        st.markdown("### Short Put Positions Details")
                        put_display = short_puts[['Symbol', 'Quantity', 'Strike', 'Abs_Quantity', 'Multiplier', 'Collateral_Required', 'Value', 'Unrealized P/L']].copy()
                        put_display.columns = ['Symbol', 'Quantity', 'Strike', 'Contracts', 'Multiplier', 'Collateral Required', 'Current Value', 'Unrealized P/L']
                        put_display = put_display.sort_values('Collateral Required', ascending=False)
                        st.dataframe(put_display, use_container_width=True, hide_index=True)

                        # Visual breakdown
                        col1, col2 = st.columns(2)
                        with col1:
                            # Pie chart of allocation
                            allocation_data = {
                                'Free Cash': max(0, free_cash),
                                'Put Collateral': total_put_collateral,
                                'Stocks': nav_stocks,
                                'Other': max(0, nav_total - nav_cash - nav_stocks)
                            }
                            allocation_df = pd.DataFrame(list(allocation_data.items()), columns=['Category', 'Value'])
                            allocation_df = allocation_df[allocation_df['Value'] > 0]

                            fig = px.pie(
                                allocation_df,
                                values='Value',
                                names='Category',
                                title="Account Allocation Breakdown",
                                color_discrete_sequence=px.colors.qualitative.Set2
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        with col2:
                            # Bar chart showing collateral breakdown
                            fig = px.bar(
                                put_display.head(10),
                                x='Symbol',
                                y='Collateral Required',
                                title="Top 10 Put Positions by Collateral",
                                color='Collateral Required',
                                color_continuous_scale='Reds'
                            )
                            st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No short put positions found. All cash is free cash.")
                        if nav_total > 0:
                            free_cash_pct = (nav_cash / nav_total * 100) if nav_total > 0 else 0
                            st.metric("Free Cash", format_currency(nav_cash), delta=f"{free_cash_pct:.2f}%")

            # Performance Summary
            if 'performance' in data:
                st.header("Performance Summary")

                with st.expander("ℹ️ About Performance Summary", expanded=False):
                    st.markdown("""
                    **Performance Summary Explained:**
                    - **Realized Total**: Total profit/loss from closed positions
                    - **Unrealized Total**: Current profit/loss on open positions
                    - **Total**: Combined realized and unrealized performance
                    - Use the search box to find specific symbols
                    - Sort by different columns to identify best/worst performers
                    - Options are aggregated by underlying symbol for easier analysis
                    """)

                perf_df = data['performance']

                # Filter out totals (rows with empty Symbol or 'Total' in Symbol)
                perf_df_filtered = perf_df[
                    (perf_df['Symbol'] != '') &
                    (~perf_df['Symbol'].str.contains('Total', case=False, na=False))
                ].copy()

                # Separate stocks and options
                stocks_perf = perf_df_filtered[perf_df_filtered['Asset Category'] == 'Stocks'].copy()
                options_perf = perf_df_filtered[perf_df_filtered['Asset Category'] == 'Equity and Index Options'].copy()

                tab1, tab2, tab3 = st.tabs(["Stocks", "Options", "All Positions"])

                with tab1:
                    if not stocks_perf.empty:
                        # Search/filter
                        search_col1, search_col2 = st.columns([3, 1])
                        with search_col1:
                            search_term = st.text_input("🔍 Search Symbol", key="stock_search")
                        with search_col2:
                            sort_by = st.selectbox("Sort By", ['Total', 'Realized Total', 'Unrealized Total'], key="stock_sort")

                        # Top performers
                        st.subheader("Stock Performance")
                        stock_display = stocks_perf[['Symbol', 'Realized Total', 'Unrealized Total', 'Total']].copy()

                        # Apply search filter
                        if search_term:
                            stock_display = stock_display[
                                stock_display['Symbol'].str.contains(search_term, case=False, na=False)
                            ]

                        stock_display = stock_display.sort_values(sort_by, ascending=False)
                        st.dataframe(stock_display, use_container_width=True, hide_index=True)

                        # Bar chart
                        if not stock_display.empty:
                            fig = px.bar(
                                stock_display.head(20),
                                x='Symbol',
                                y='Total',
                                title="Stock Performance (Realized + Unrealized)",
                                color='Total',
                                color_continuous_scale=['red', 'yellow', 'green']
                            )
                            st.plotly_chart(fig, use_container_width=True)

                with tab2:
                    if not options_perf.empty:
                        st.subheader("Options Performance")
                        # Aggregate by underlying symbol
                        options_perf['Underlying'] = options_perf['Symbol'].str.split().str[0]
                        options_summary = options_perf.groupby('Underlying').agg({
                            'Realized Total': 'sum',
                            'Unrealized Total': 'sum',
                            'Total': 'sum'
                        }).reset_index()

                        # Search/filter
                        search_col1, search_col2 = st.columns([3, 1])
                        with search_col1:
                            search_term = st.text_input("🔍 Search Underlying", key="options_search")
                        with search_col2:
                            sort_by = st.selectbox("Sort By", ['Total', 'Realized Total', 'Unrealized Total'], key="options_sort")

                        # Apply search filter
                        if search_term:
                            options_summary = options_summary[
                                options_summary['Underlying'].str.contains(search_term, case=False, na=False)
                            ]

                        options_summary = options_summary.sort_values(sort_by, ascending=False)
                        st.dataframe(options_summary, use_container_width=True, hide_index=True)

                        # Bar chart
                        if not options_summary.empty:
                            fig = px.bar(
                                options_summary.head(20),
                                x='Underlying',
                                y='Total',
                                title="Top 20 Options Underlyings Performance",
                                color='Total',
                                color_continuous_scale=['red', 'yellow', 'green']
                            )
                            st.plotly_chart(fig, use_container_width=True)

                with tab3:
                    st.subheader("All Positions Performance")
                    all_perf = perf_df_filtered[['Asset Category', 'Symbol', 'Realized Total', 'Unrealized Total', 'Total']].copy()
                    all_perf = all_perf.sort_values('Total', ascending=False)
                    st.dataframe(all_perf.head(50), use_container_width=True, hide_index=True)

            # Open Positions
            if 'open_positions' in data:
                st.header("Open Positions")

                with st.expander("ℹ️ About Open Positions", expanded=False):
                    st.markdown("""
                    **Open Positions Explained:**
                    - Shows all currently held positions (stocks and options)
                    - **Cost Basis**: Total amount invested in the position
                    - **Value**: Current market value of the position
                    - **Unrealized P/L**: Current profit/loss (Value - Cost Basis)
                    - Negative quantity indicates short positions
                    - Positions are sorted by unrealized P/L to highlight best/worst performers
                    """)

                positions_df = data['open_positions']

                if not positions_df.empty:
                    # Categorize positions for stacked bar chart
                    def categorize_position(row):
                        """Categorize position into Cash Secured Puts, Stocks, LEAPS, or Other Options."""
                        asset_cat = row.get('Asset Category', '')
                        symbol = str(row.get('Symbol', ''))
                        quantity = row.get('Quantity', 0)
                        
                        # Stocks
                        if asset_cat == 'Stocks':
                            return 'Stocks'
                        
                        # Options
                        if asset_cat == 'Equity and Index Options':
                            # Check if it's a put (ends with P or contains " P")
                            is_put = symbol.endswith(' P') or symbol.endswith('P')
                            
                            # Cash secured puts: short puts (negative quantity)
                            if is_put and quantity < 0:
                                return 'Cash Secured Puts'
                            
                            # LEAPS: options expiring in 2027 or later (typically > 1 year)
                            # Extract date from symbol (format: SYMBOL DDMMMYY STRIKE P/C)
                            # Example: "IREN 15JAN27 42 C" -> 2027
                            # Example: "SOFI 17JUN27 20 C" -> 2027 (LEAPS)
                            # Example: "INOD 27FEB26 60 C" -> 2026 Feb (NOT LEAPS)
                            date_match = re.search(r'(\d{2})([A-Z]{3})(\d{2})', symbol)
                            if date_match:
                                day = date_match.group(1)
                                month_str = date_match.group(2)
                                year_str = date_match.group(3)
                                year = int('20' + year_str)
                                
                                # Convert month abbreviation to number
                                months = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                                         'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
                                month_num = months.get(month_str, 0)
                                
                                # LEAPS are typically > 1 year, so 2027+ or December 2026
                                if year >= 2027 or (year == 2026 and month_num >= 12):
                                    return 'LEAPS'
                            
                            # Other options
                            return 'Other Options'
                        
                        return 'Other'
                    
                    # Add category column
                    positions_df['Position_Category'] = positions_df.apply(categorize_position, axis=1)
                    
                    # Calculate collateral for CSP positions
                    def extract_strike(symbol):
                        """Extract strike price from option symbol."""
                        try:
                            parts = symbol.split()
                            if len(parts) >= 3:
                                strike_str = parts[-2]
                                try:
                                    return float(strike_str)
                                except ValueError:
                                    for i in range(len(parts) - 2, -1, -1):
                                        try:
                                            return float(parts[i])
                                        except ValueError:
                                            continue
                            return 0
                        except:
                            return 0
                    
                    # Add collateral calculation
                    positions_df['Collateral'] = 0
                    csp_mask = positions_df['Position_Category'] == 'Cash Secured Puts'
                    if csp_mask.any():
                        csp_positions = positions_df[csp_mask].copy()
                        csp_positions['Strike'] = csp_positions['Symbol'].apply(extract_strike)
                        if 'Mult' in csp_positions.columns:
                            csp_positions['Multiplier'] = csp_positions['Mult'].fillna(100)
                        else:
                            csp_positions['Multiplier'] = 100
                        csp_positions['Abs_Quantity'] = csp_positions['Quantity'].abs()
                        csp_positions['Collateral'] = csp_positions['Strike'] * csp_positions['Abs_Quantity'] * csp_positions['Multiplier']
                        
                        # Update collateral in main dataframe
                        positions_df.loc[csp_mask, 'Collateral'] = csp_positions['Collateral'].values
                    
                    # Calculate totals by category
                    category_summary = positions_df.groupby('Position_Category').agg({
                        'Value': 'sum',
                        'Cost Basis': 'sum',
                        'Unrealized P/L': 'sum',
                        'Collateral': 'sum',
                        'Quantity': 'count'  # Count of positions
                    }).reset_index()
                    category_summary.columns = ['Category', 'Total Value', 'Total Cost Basis', 'Total Unrealized P/L', 'Total Collateral', 'Position Count']
                    
                    # Summary by asset category
                    pos_summary = positions_df.groupby('Asset Category').agg({
                        'Quantity': 'sum',
                        'Cost Basis': 'sum',
                        'Value': 'sum',
                        'Unrealized P/L': 'sum'
                    }).reset_index()

                    col1, col2 = st.columns(2)

                    with col1:
                        st.subheader("Position Summary")
                        st.dataframe(pos_summary, use_container_width=True, hide_index=True)

                    with col2:
                        # Unrealized P/L chart
                        fig = px.bar(
                            pos_summary,
                            x='Asset Category',
                            y='Unrealized P/L',
                            title="Unrealized P/L by Asset Category",
                            color='Unrealized P/L',
                            color_continuous_scale=['red', 'yellow', 'green']
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Stacked bar chart: One bar per stock, normalized to 100% per bar
                    st.subheader("Portfolio Allocation by Stock - Stacked Position Types")
                    
                    # Get total portfolio value from NAV
                    nav_total = nav_df[nav_df['Asset Class'] == 'Total']['Current Total'].iloc[0] if 'Total' in nav_df['Asset Class'].values else 0
                    nav_cash = nav_df[nav_df['Asset Class'] == 'Cash ']['Current Total'].iloc[0] if 'Cash ' in nav_df['Asset Class'].values else 0
                    
                    # Extract underlying symbol for each position
                    def get_underlying_symbol(row):
                        """Extract underlying symbol from position."""
                        symbol = str(row['Symbol'])
                        asset_cat = row.get('Asset Category', '')
                        
                        if asset_cat == 'Stocks':
                            return symbol
                        else:
                            # For options, extract underlying (first part before space)
                            parts = symbol.split()
                            return parts[0] if parts else symbol
                    
                    positions_df['Underlying'] = positions_df.apply(get_underlying_symbol, axis=1)
                    
                    # Group by underlying symbol and position category, sum values and collateral
                    position_summary = positions_df.groupby(['Underlying', 'Position_Category']).agg({
                        'Value': 'sum',
                        'Collateral': 'sum'
                    }).reset_index()
                    
                    # Calculate total value and collateral per symbol
                    symbol_totals = position_summary.groupby('Underlying').agg({
                        'Value': 'sum',
                        'Collateral': 'sum'
                    }).reset_index()
                    symbol_totals.columns = ['Underlying', 'Total_Value', 'Total_Collateral']
                    
                    # For normalization: use collateral for CSP-only stocks, value for others
                    symbol_totals['Total_Value_Abs'] = symbol_totals.apply(
                        lambda row: row['Total_Collateral'] if row['Total_Value'] < 0 and row['Total_Collateral'] > 0 
                                   else abs(row['Total_Value']),
                        axis=1
                    )
                    
                    # Calculate percentage of portfolio for each symbol (for labels)
                    symbol_totals['Portfolio_Percentage'] = (symbol_totals['Total_Value_Abs'] / nav_total * 100) if nav_total > 0 else 0
                    
                    # Sort by portfolio percentage descending
                    symbol_totals = symbol_totals.sort_values('Portfolio_Percentage', ascending=False)
                    all_symbols = symbol_totals['Underlying'].tolist()
                    
                    # Define colors - softer, easier on the eyes
                    colors = {
                        'Stocks': '#2E7D32',  # Darker green (easier on eyes)
                        'Cash Secured Puts': '#F57C00',  # Darker orange
                        'LEAPS': '#C62828',  # Darker red
                        'Other Options': '#FF8A65',  # Softer orange
                        'Other': '#78909C'  # Softer grey
                    }
                    
                    # Create stacked bar chart - scaled by portfolio percentage with visibility factor
                    fig = go.Figure()
                    
                    # Calculate scaling factor to make small positions visible
                    # Use square root scaling: scaled_height = sqrt(percentage) * factor
                    # This makes small percentages more visible relative to large ones
                    max_pct = symbol_totals['Portfolio_Percentage'].max()
                    min_pct = symbol_totals[symbol_totals['Portfolio_Percentage'] > 0]['Portfolio_Percentage'].min()
                    
                    # Calculate scaling factor: ensure smallest position is at least 5% of max bar height
                    if min_pct > 0:
                        # Scale so min_pct becomes visible (e.g., 5% of max bar)
                        scale_factor = 100 / (max_pct ** 0.5)  # Square root scaling
                        min_visible_height = (min_pct ** 0.5) * scale_factor
                        if min_visible_height < 5:  # Ensure minimum 5% visibility
                            scale_factor = 5 / (min_pct ** 0.5)
                    else:
                        scale_factor = 1
                    
                    # Order of stacking: Stocks on top, then Cash Secured Puts, then LEAPS
                    # Note: Other Options are hidden from the chart
                    stack_order = ['Stocks', 'Cash Secured Puts', 'LEAPS']
                    
                    for position_type in stack_order:
                        scaled_heights = []  # Scaled heights based on portfolio percentage
                        normalized_percentages = []  # Percentage within each stock (for reference)
                        portfolio_percentages = []  # Percentage of total portfolio
                        values_list = []
                        collateral_list = []
                        
                        for symbol in all_symbols:
                            symbol_data = position_summary[
                                (position_summary['Underlying'] == symbol) & 
                                (position_summary['Position_Category'] == position_type)
                            ]
                            value = symbol_data['Value'].sum() if not symbol_data.empty else 0
                            collateral = symbol_data['Collateral'].sum() if not symbol_data.empty else 0
                            
                            # Get total value for this symbol (use absolute value for normalization)
                            symbol_total_abs = symbol_totals[symbol_totals['Underlying'] == symbol]['Total_Value_Abs'].iloc[0]
                            
                            # For CSP positions, use collateral instead of value for display
                            if position_type == 'Cash Secured Puts':
                                display_value = collateral if collateral > 0 else abs(value)
                            else:
                                display_value = abs(value)
                            
                            # Calculate percentage within this stock (for hover info)
                            normalized_pct = (display_value / symbol_total_abs * 100) if symbol_total_abs > 0 else 0
                            normalized_percentages.append(normalized_pct)
                            
                            # Portfolio percentage - use collateral for CSP, value for others
                            if position_type == 'Cash Secured Puts':
                                portfolio_pct = (collateral / nav_total * 100) if nav_total > 0 else 0
                            else:
                                portfolio_pct = (display_value / nav_total * 100) if nav_total > 0 else 0
                            portfolio_percentages.append(portfolio_pct)
                            
                            # Calculate scaled height for this segment
                            # Use square root scaling to make small values more visible
                            if portfolio_pct > 0:
                                scaled_height = (portfolio_pct ** 0.5) * scale_factor
                            else:
                                scaled_height = 0
                            
                            # But we need to scale proportionally within each bar
                            # So calculate what portion of the bar this segment represents
                            symbol_total_pct = symbol_totals[symbol_totals['Underlying'] == symbol]['Portfolio_Percentage'].iloc[0]
                            symbol_scaled_height = (symbol_total_pct ** 0.5) * scale_factor if symbol_total_pct > 0 else 0
                            
                            # Segment height = (segment_pct / total_pct) * symbol_scaled_height
                            segment_height = (portfolio_pct / symbol_total_pct * symbol_scaled_height) if symbol_total_pct > 0 else 0
                            scaled_heights.append(segment_height)
                            
                            values_list.append(value)
                            collateral_list.append(collateral)
                        
                        # Only add trace if there are non-zero values
                        if any(h > 0 for h in scaled_heights):
                            # Custom hover template for CSP to show collateral
                            if position_type == 'Cash Secured Puts':
                                hover_template = f"<b>%{{x}}</b><br>" + \
                                               f"Type: {position_type}<br>" + \
                                               f"Within Stock: %{{customdata[3]:.1f}}%<br>" + \
                                               f"Of Portfolio: %{{customdata[0]:.2f}}%<br>" + \
                                               f"Collateral: $%{{customdata[2]:,.2f}}<br>" + \
                                               f"Option Value: $%{{customdata[1]:,.2f}}<extra></extra>"
                            else:
                                hover_template = f"<b>%{{x}}</b><br>" + \
                                               f"Type: {position_type}<br>" + \
                                               f"Within Stock: %{{customdata[3]:.1f}}%<br>" + \
                                               f"Of Portfolio: %{{customdata[0]:.2f}}%<br>" + \
                                               f"Value: $%{{customdata[1]:,.2f}}<extra></extra>"
                            
                            fig.add_trace(go.Bar(
                                name=position_type,
                                x=all_symbols,
                                y=scaled_heights,  # Use scaled heights based on portfolio percentage
                                marker_color=colors.get(position_type, '#95A5A6'),
                                hovertemplate=hover_template,
                                customdata=list(zip(portfolio_percentages, values_list, collateral_list, normalized_percentages))
                            ))
                    
                    # Calculate max bar height for y-axis range (excluding cash)
                    max_bar_height = symbol_totals['Portfolio_Percentage'].apply(lambda p: (p ** 0.5) * scale_factor).max()
                    
                    # Add portfolio percentage labels above bars
                    annotations = []
                    for symbol in all_symbols:
                        portfolio_pct = symbol_totals[symbol_totals['Underlying'] == symbol]['Portfolio_Percentage'].iloc[0]
                        symbol_scaled_height = (portfolio_pct ** 0.5) * scale_factor if portfolio_pct > 0 else 0
                        annotations.append(dict(
                            x=symbol,
                            y=symbol_scaled_height,
                            text=f'{portfolio_pct:.2f}%',
                            showarrow=False,
                            font=dict(color='white', size=10),
                            yshift=10
                        ))
                    
                    
                    fig.update_layout(
                        title="Portfolio Allocation by Stock - Scaled by Portfolio % (Square Root Scaling)",
                        xaxis_title="Stock Symbol",
                        yaxis_title="Scaled Height (Proportional to Portfolio %)",
                        barmode='stack',
                        showlegend=True,
                        height=600,
                        xaxis=dict(tickangle=-45),
                        yaxis=dict(range=[0, max_bar_height * 1.1], title="Scaled Height"),
                        annotations=annotations
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Detailed positions table
                    st.subheader("Detailed Positions")
                    display_pos = positions_df[['Asset Category', 'Symbol', 'Quantity',
                                               'Cost Basis', 'Value', 'Unrealized P/L', 'Position_Category']].copy()
                    display_pos = display_pos.sort_values('Unrealized P/L', ascending=False)
                    # Reorder columns to show category first
                    cols = ['Position_Category', 'Asset Category', 'Symbol', 'Quantity', 'Cost Basis', 'Value', 'Unrealized P/L']
                    display_pos = display_pos[[c for c in cols if c in display_pos.columns]]
                    display_pos.columns = ['Category', 'Asset Type', 'Symbol', 'Quantity', 'Cost Basis', 'Value', 'Unrealized P/L']
                    st.dataframe(display_pos, use_container_width=True, hide_index=True)

            # Trades Analysis
            if 'trades' in data:
                st.header("Trades Analysis")
                trades_df_full = data['trades'].copy()  # Keep full dataset for cumulative calculations
                trades_df = trades_df_full.copy()  # Filtered dataset

                if not trades_df.empty and 'Date/Time' in trades_df.columns:
                    # Create Date column first
                    trades_df_full['Date'] = trades_df_full['Date/Time'].dt.date
                    trades_df['Date'] = trades_df['Date/Time'].dt.date

                    # Filters
                    st.subheader("Filters")

                    with st.expander("ℹ️ About Filters", expanded=False):
                        st.markdown("""
                        **Filter Options:**
                        - **Date Range**: Select a specific time period to analyze. All metrics and charts will update to show only data from the selected period.
                        - **Symbol Filter**: Filter trades by a specific symbol (e.g., TSLA, AAPL). Select "All" to see all symbols.
                        - **Asset Category**: Filter by asset type (Stocks, Options, etc.). Select "All" to see all categories.

                        **Note**: Filters work together - you can combine date range, symbol, and asset category filters for detailed analysis.
                        """)

                    filter_col1, filter_col2, filter_col3 = st.columns(3)

                    with filter_col1:
                        # Date range filter
                        min_date = trades_df_full['Date'].min()
                        max_date = trades_df_full['Date'].max()
                        date_range = st.date_input(
                            "Date Range",
                            value=(min_date, max_date),
                            min_value=min_date,
                            max_value=max_date
                        )
                        if len(date_range) == 2:
                            trades_df = trades_df[
                                (trades_df['Date'] >= date_range[0]) &
                                (trades_df['Date'] <= date_range[1])
                            ]
                        else:
                            date_range = (min_date, max_date)  # Default to full range

                    with filter_col2:
                        # Symbol filter
                        if 'Symbol' in trades_df.columns:
                            symbols = ['All'] + sorted(trades_df['Symbol'].unique().tolist())
                            selected_symbol = st.selectbox("Symbol Filter", symbols)
                            if selected_symbol != 'All':
                                trades_df = trades_df[trades_df['Symbol'] == selected_symbol]

                    with filter_col3:
                        # Asset category filter
                        if 'Asset Category' in trades_df.columns:
                            categories = ['All'] + sorted(trades_df['Asset Category'].unique().tolist())
                            selected_category = st.selectbox("Asset Category", categories)
                            if selected_category != 'All':
                                trades_df = trades_df[trades_df['Asset Category'] == selected_category]

                    # Trade Statistics
                    st.subheader("Trade Statistics")

                    with st.expander("ℹ️ About Trade Statistics", expanded=False):
                        st.markdown("""
                        **Trade Statistics Explained:**
                        - **Total Trades**: Number of closed positions (trades with non-zero P/L)
                        - **Win Rate**: Percentage of profitable trades (Winning Trades / Total Trades)
                        - **Winning Trades**: Number of trades that resulted in profit
                        - **Losing Trades**: Number of trades that resulted in loss
                        - **Avg Win**: Average profit per winning trade
                        - **Avg Loss**: Average loss per losing trade (typically negative)
                        - **Largest Win**: Single largest profitable trade
                        - **Largest Loss**: Single largest losing trade
                        - **Profit Factor**: Ratio of total wins to total losses (higher is better, >1 means profitable)
                        - **Total P/L**: Sum of all realized profits and losses

                        **Note**: Statistics are calculated only for closed positions (trades with realized P/L).
                        """)

                    stats = calculate_trade_stats(trades_df)

                    if stats:
                        stat_col1, stat_col2, stat_col3, stat_col4, stat_col5 = st.columns(5)

                        with stat_col1:
                            st.metric("Total Trades", stats['total_trades'])
                            st.metric("Win Rate", f"{stats['win_rate']:.1f}%")

                        with stat_col2:
                            st.metric("Winning Trades", stats['winning_trades'])
                            st.metric("Losing Trades", stats['losing_trades'])

                        with stat_col3:
                            st.metric("Avg Win", format_currency(stats['avg_win']))
                            st.metric("Avg Loss", format_currency(stats['avg_loss']))

                        with stat_col4:
                            largest_win_display = format_currency(stats['largest_win'])
                            if 'largest_win_symbol' in stats and stats['largest_win_symbol']:
                                largest_win_display += f" ({stats['largest_win_symbol']})"
                            st.metric("Largest Win", largest_win_display)

                            largest_loss_display = format_currency(stats['largest_loss'])
                            if 'largest_loss_symbol' in stats and stats['largest_loss_symbol']:
                                largest_loss_display += f" ({stats['largest_loss_symbol']})"
                            st.metric("Largest Loss", largest_loss_display)

                        with stat_col5:
                            st.metric("Profit Factor", f"{stats['profit_factor']:.2f}" if stats['profit_factor'] > 0 else "N/A")
                            st.metric("Total P/L", format_currency(stats['total_pl']))

                    # Daily P/L with ROI calculations
                    if 'Date' in trades_df.columns:
                        # Get starting value and deposits for ROI calculation
                        starting_value = data.get('change_in_nav', {}).get('Starting Value', 0)
                        deposits_df = data.get('deposits_withdrawals', pd.DataFrame())

                        # date_range is already set from the filter section above

                        # Calculate cumulative deposits up to each date
                        if not deposits_df.empty and 'Settle Date' in deposits_df.columns:
                            deposits_df['Date'] = pd.to_datetime(deposits_df['Settle Date']).dt.date
                            deposits_df = deposits_df.sort_values('Date')
                            deposits_df['Cumulative Deposits'] = deposits_df['Amount'].cumsum()
                        else:
                            deposits_df = pd.DataFrame(columns=['Date', 'Cumulative Deposits'])

                        # Calculate daily P/L from filtered trades
                        daily_pl = trades_df.groupby('Date')['Realized P/L'].sum().reset_index()
                        daily_pl = daily_pl.sort_values('Date')

                        # Calculate period-specific cumulative P/L (only from filtered period)
                        daily_pl['Period Cumulative P/L'] = daily_pl['Realized P/L'].cumsum()

                        # Also calculate cumulative from all trades (for reference)
                        daily_pl_full = trades_df_full.groupby('Date')['Realized P/L'].sum().reset_index()
                        daily_pl_full = daily_pl_full.sort_values('Date')
                        daily_pl_full['Cumulative P/L Full'] = daily_pl_full['Realized P/L'].cumsum()

                        # Merge cumulative P/L from full dataset for reference
                        daily_pl = daily_pl.merge(
                            daily_pl_full[['Date', 'Cumulative P/L Full']],
                            on='Date',
                            how='left'
                        )
                        daily_pl['Cumulative P/L (All Trades)'] = daily_pl['Cumulative P/L Full'].fillna(0)
                        daily_pl = daily_pl.drop(columns=['Cumulative P/L Full'], errors='ignore')

                        # Calculate invested capital for period-specific ROI
                        daily_pl['Cumulative Deposits'] = daily_pl['Date'].apply(
                            lambda d: deposits_df[deposits_df['Date'] <= d]['Amount'].sum() if not deposits_df.empty else 0
                        )
                        daily_pl['Invested Capital'] = starting_value + daily_pl['Cumulative Deposits']

                        # Calculate period-specific ROI (using period cumulative P/L)
                        daily_pl['Period Realized ROI %'] = (daily_pl['Period Cumulative P/L'] / daily_pl['Invested Capital'] * 100).round(2)
                        daily_pl['Period Realized ROI %'] = daily_pl['Period Realized ROI %'].replace([float('inf'), float('-inf')], 0)
                        daily_pl['Period Realized ROI %'] = daily_pl['Period Realized ROI %'].fillna(0)

                        # Also calculate cumulative ROI (from all trades) for reference
                        daily_pl['Cumulative Realized ROI %'] = (daily_pl['Cumulative P/L (All Trades)'] / daily_pl['Invested Capital'] * 100).round(2)
                        daily_pl['Cumulative Realized ROI %'] = daily_pl['Cumulative Realized ROI %'].replace([float('inf'), float('-inf')], 0)
                        daily_pl['Cumulative Realized ROI %'] = daily_pl['Cumulative Realized ROI %'].fillna(0)

                        # Monthly P/L with ROI
                        trades_df['Month'] = pd.to_datetime(trades_df['Date']).dt.to_period('M')
                        monthly_pl = trades_df.groupby('Month')['Realized P/L'].sum().reset_index()
                        monthly_pl['Month'] = monthly_pl['Month'].astype(str)
                        monthly_pl = monthly_pl.sort_values('Month')

                        # Calculate period-specific cumulative P/L (only from filtered period)
                        monthly_pl['Period Cumulative P/L'] = monthly_pl['Realized P/L'].cumsum()

                        # Calculate cumulative deposits for each month
                        monthly_pl['Month_Date'] = pd.to_datetime(monthly_pl['Month'])
                        monthly_pl['Cumulative Deposits'] = monthly_pl['Month_Date'].apply(
                            lambda d: deposits_df[deposits_df['Date'] <= d.date()]['Amount'].sum() if not deposits_df.empty else 0
                        )
                        monthly_pl['Invested Capital'] = starting_value + monthly_pl['Cumulative Deposits']

                        # Calculate period-specific ROI (using period cumulative P/L)
                        monthly_pl['Period Realized ROI %'] = (monthly_pl['Period Cumulative P/L'] / monthly_pl['Invested Capital'] * 100).round(2)
                        monthly_pl['Period Realized ROI %'] = monthly_pl['Period Realized ROI %'].replace([float('inf'), float('-inf')], 0)
                        monthly_pl['Period Realized ROI %'] = monthly_pl['Period Realized ROI %'].fillna(0)

                        # Calculate monthly P/L as percentage of invested capital at start of each month
                        monthly_pl['Monthly P/L %'] = (monthly_pl['Realized P/L'] / monthly_pl['Invested Capital'] * 100).round(2)
                        monthly_pl['Monthly P/L %'] = monthly_pl['Monthly P/L %'].replace([float('inf'), float('-inf')], 0)
                        monthly_pl['Monthly P/L %'] = monthly_pl['Monthly P/L %'].fillna(0)

                        # Display ROI metrics for filtered period
                        if not daily_pl.empty:
                            # Calculate period-specific metrics (only for filtered period)
                            period_realized_pl = daily_pl['Realized P/L'].sum()  # Sum of P/L only in filtered period

                            # Get invested capital at START of filtered period
                            if len(date_range) == 2:
                                filter_start_date = date_range[0]
                                # Calculate deposits up to start of filter period
                                deposits_at_start = deposits_df[deposits_df['Date'] < filter_start_date]['Amount'].sum() if not deposits_df.empty else 0
                                invested_capital_at_start = starting_value + deposits_at_start

                                # Calculate deposits during filtered period
                                deposits_during_period = deposits_df[
                                    (deposits_df['Date'] >= filter_start_date) &
                                    (deposits_df['Date'] <= date_range[1])
                                ]['Amount'].sum() if not deposits_df.empty else 0

                                # Average invested capital during period (start + half of deposits during period)
                                avg_invested_capital = invested_capital_at_start + (deposits_during_period / 2)

                                # Period-specific ROI: P/L in period / average capital during period
                                if avg_invested_capital > 0:
                                    period_realized_roi = (period_realized_pl / avg_invested_capital) * 100
                                else:
                                    period_realized_roi = 0
                            else:
                                # No filter, use cumulative values
                                invested_capital_at_start = daily_pl['Invested Capital'].iloc[0] if not daily_pl.empty else starting_value
                                avg_invested_capital = daily_pl['Invested Capital'].iloc[-1] if not daily_pl.empty else starting_value
                                period_realized_roi = daily_pl['Realized ROI %'].iloc[-1] if not daily_pl.empty else 0

                            with st.expander("ℹ️ About Period ROI Calculations", expanded=False):
                                st.markdown("""
                                **Period-Specific ROI Explained:**

                                These metrics show performance ONLY for the selected date range:
                                - **Period Realized P/L**: Sum of realized P/L ONLY from trades in the filtered date range
                                - **Invested Capital (Period Start)**: Capital invested at the START of the filtered period
                                - **Period Realized ROI %**: (Period P/L / Average Invested Capital) × 100

                                **How it's calculated:**
                                - Only trades within the selected date range are included
                                - Invested capital is calculated at the start of the period
                                - Average invested capital accounts for deposits made during the period

                                **Note**: For overall/cumulative metrics, see the Portfolio Overview section at the top of the page.

                                **Example**:
                                If you filter Jan-Mar and made $500 in that period with $10,000 invested at the start, Period ROI = 5%
                                """)

                            # Period-specific metrics
                            st.markdown("### Period-Specific Metrics (Filtered Date Range Only)")
                            roi_col1, roi_col2, roi_col3 = st.columns(3)
                            with roi_col1:
                                st.metric("Period Realized P/L", format_currency(period_realized_pl),
                                         delta=f"{period_realized_pl:.2f}")
                            with roi_col2:
                                st.metric("Invested Capital (Period Start)", format_currency(invested_capital_at_start))
                            with roi_col3:
                                st.metric("Period Realized ROI %", f"{period_realized_roi:.2f}%",
                                         delta=f"{format_currency(period_realized_pl)}")

                        col1, col2 = st.columns(2)

                        with col1:
                            fig = px.line(
                                daily_pl,
                                x='Date',
                                y='Realized P/L',
                                title="Daily Realized P/L (Period Only)",
                                markers=True
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        with col2:
                            fig = px.line(
                                daily_pl,
                                x='Date',
                                y='Period Cumulative P/L',
                                title="Period Cumulative P/L (Filtered Range)",
                                markers=True
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        # Daily ROI chart
                        st.subheader("Realized ROI Over Time")

                        with st.expander("ℹ️ About ROI Charts", expanded=False):
                            st.markdown("""
                            **ROI Charts Explained:**
                            - **Period Realized ROI %**: Shows ROI calculated using ONLY trades in the filtered date range
                            - **Monthly Realized ROI %**: Shows monthly ROI trends for the filtered period
                            - The horizontal line at 0% represents break-even point
                            - Values above 0% indicate profitable performance
                            - Values below 0% indicate losses
                            - ROI is calculated as: (Period Cumulative P/L / Invested Capital) × 100
                            - Only includes trades from the selected date range
                            """)

                        col1, col2 = st.columns(2)

                        with col1:
                            fig = px.line(
                                daily_pl,
                                x='Date',
                                y='Period Realized ROI %',
                                title="Period Realized ROI % (Filtered Range)",
                                markers=True,
                                labels={'Period Realized ROI %': 'Period ROI (%)'}
                            )
                            fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Break-even")
                            st.plotly_chart(fig, use_container_width=True)

                        with col2:
                            # Show daily ROI table
                            daily_roi_display = daily_pl[['Date', 'Period Cumulative P/L', 'Invested Capital', 'Period Realized ROI %']].copy()
                            daily_roi_display = daily_roi_display.tail(30)  # Show last 30 days
                            daily_roi_display.columns = ['Date', 'Period Cumulative P/L', 'Invested Capital', 'Period ROI %']
                            st.dataframe(daily_roi_display, use_container_width=True, hide_index=True)

                        # Monthly performance
                        col1, col2 = st.columns(2)
                        with col1:
                            fig = px.bar(
                                monthly_pl,
                                x='Month',
                                y='Realized P/L',
                                title="Monthly Realized P/L (Period Only)",
                                color='Realized P/L',
                                color_continuous_scale=['red', 'yellow', 'green']
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        with col2:
                            fig = px.bar(
                                monthly_pl,
                                x='Month',
                                y='Monthly P/L %',
                                title="Monthly Realized P/L % (Period Only)",
                                color='Monthly P/L %',
                                color_continuous_scale=['red', 'yellow', 'green']
                            )
                            fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Break-even")
                            st.plotly_chart(fig, use_container_width=True)

                        # Cumulative monthly charts
                        col1, col2 = st.columns(2)
                        with col1:
                            fig = px.line(
                                monthly_pl,
                                x='Month',
                                y='Period Cumulative P/L',
                                title="Period Cumulative Monthly P/L (Filtered Range)",
                                markers=True
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        with col2:
                            fig = px.line(
                                monthly_pl,
                                x='Month',
                                y='Period Realized ROI %',
                                title="Period Cumulative Monthly ROI % (Filtered Range)",
                                markers=True,
                                labels={'Period Realized ROI %': 'Cumulative ROI (%)'}
                            )
                            fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Break-even")
                            st.plotly_chart(fig, use_container_width=True)

                        # Monthly ROI table
                        st.subheader("Monthly Performance Summary")
                        monthly_roi_display = monthly_pl[['Month', 'Realized P/L', 'Monthly P/L %', 'Period Cumulative P/L', 'Invested Capital', 'Period Realized ROI %']].copy()
                        monthly_roi_display.columns = ['Month', 'Monthly P/L', 'Monthly P/L %', 'Period Cumulative P/L', 'Invested Capital', 'Period ROI %']
                        st.dataframe(monthly_roi_display, use_container_width=True, hide_index=True)

                    # Trades by symbol
                    if 'Symbol' in trades_df.columns:
                        symbol_pl = trades_df.groupby('Symbol')['Realized P/L'].sum().reset_index()
                        symbol_pl = symbol_pl.sort_values('Realized P/L', ascending=False)

                        st.subheader("Realized P/L by Symbol")
                        col1, col2 = st.columns([2, 1])

                        with col1:
                            fig = px.bar(
                                symbol_pl.head(30),
                                x='Symbol',
                                y='Realized P/L',
                                title="Top 30 Symbols by Realized P/L",
                                color='Realized P/L',
                                color_continuous_scale=['red', 'yellow', 'green']
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        with col2:
                            st.dataframe(symbol_pl.head(30), use_container_width=True, hide_index=True)

                    # Asset Category Breakdown
                    if 'Asset Category' in trades_df.columns:
                        st.subheader("Performance by Asset Category")
                        category_pl = trades_df.groupby('Asset Category').agg({
                            'Realized P/L': 'sum',
                            'Quantity': 'count'
                        }).reset_index()
                        category_pl.columns = ['Asset Category', 'Total P/L', 'Trade Count']
                        category_pl = category_pl.sort_values('Total P/L', ascending=False)

                        col1, col2 = st.columns(2)

                        with col1:
                            fig = px.pie(
                                category_pl,
                                values='Total P/L',
                                names='Asset Category',
                                title="P/L Distribution by Asset Category"
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        with col2:
                            fig = px.bar(
                                category_pl,
                                x='Asset Category',
                                y='Total P/L',
                                title="P/L by Asset Category",
                                color='Total P/L',
                                color_continuous_scale=['red', 'yellow', 'green']
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        st.dataframe(category_pl, use_container_width=True, hide_index=True)

                    # Detailed trades table
                    st.subheader("Trade Details")
                    display_cols = ['Date/Time', 'Asset Category', 'Symbol', 'Quantity',
                                  'T. Price', 'Realized P/L']
                    available_cols = [col for col in display_cols if col in trades_df.columns]
                    display_trades = trades_df[available_cols].copy()
                    display_trades = display_trades.sort_values('Date/Time', ascending=False)
                    st.dataframe(display_trades.head(100), use_container_width=True, hide_index=True)

            # Deposits & Withdrawals
            if 'deposits_withdrawals' in data:
                st.header("Cash Flow")

                with st.expander("ℹ️ About Cash Flow", expanded=False):
                    st.markdown("""
                    **Cash Flow Explained:**
                    - Shows all deposits and withdrawals made to/from your account
                    - **Cumulative Cash Flow**: Running total of all deposits and withdrawals
                    - Positive amounts indicate deposits (money added to account)
                    - Negative amounts would indicate withdrawals (money removed from account)
                    - The cumulative chart shows how your account funding has changed over time
                    """)

                dw_df = data['deposits_withdrawals']

                if not dw_df.empty and 'Settle Date' in dw_df.columns:
                    dw_df['Date'] = dw_df['Settle Date'].dt.date
                    dw_df['Cumulative'] = dw_df['Amount'].cumsum()

                    col1, col2 = st.columns(2)

                    with col1:
                        st.subheader("Deposits & Withdrawals")
                        st.dataframe(dw_df[['Date', 'Description', 'Amount']],
                                   use_container_width=True, hide_index=True)

                    with col2:
                        fig = px.line(
                            dw_df,
                            x='Date',
                            y='Cumulative',
                            title="Cumulative Cash Flow",
                            markers=True
                        )
                        st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
            st.exception(e)


if __name__ == "__main__":
    main()

