import streamlit as st
import pandas as pd
import yfinance as yf
import time

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="S&P 500 Live Dashboard",
    page_icon="👑",
    layout="wide"
)

# --- HELPER FUNCTIONS for formatting ---
def format_market_cap(cap):
    if not isinstance(cap, (int, float)): return "N/A"
    if cap > 1e12: return f"${cap / 1e12:.2f} T"
    if cap > 1e9: return f"${cap / 1e9:.2f} B"
    return f"${cap / 1e6:.2f} M"

def format_percentage(pct):
    if not isinstance(pct, (int, float)): return "N/A"
    return f"{pct:.2%}"

# --- DATA FETCHING & PROCESSING (with Caching) ---

# Cache 1: Get the list of tickers (runs once)
@st.cache_data(ttl=86400) # Cache for a full day
def get_sp500_tickers():
    st.info("Fetching S&P 500 constituents from Wikipedia...")
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(url)
        tickers = tables[0]['Symbol'].str.replace('.', '-', regex=False).tolist()
        return tickers
    except Exception as e:
        st.error(f"Failed to fetch tickers from Wikipedia: {e}")
        return []

# Cache 2: Fetch market cap and quarterly growth data
@st.cache_data(ttl=3600) # Cache for 1 hour
def fetch_market_cap_data(tickers):
    st.info(f"Fetching market caps & quarterly growth for {len(tickers)} tickers...")
    all_company_data = []
    progress_bar = st.progress(0, text="Fetching...")
    for i, ticker_symbol in enumerate(tickers):
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            market_cap = info.get('marketCap')
            if market_cap and market_cap > 0:
                all_company_data.append({
                    'Ticker': ticker_symbol, 'Name': info.get('shortName', 'N/A'),
                    'MarketCap': market_cap, 'RevenueGrowth': info.get('revenueGrowth')
                })
            progress_bar.progress((i + 1) / len(tickers), text=f"Fetching: {ticker_symbol}")
        except Exception: continue
    progress_bar.empty()
    if not all_company_data: return None, None, None
    
    df = pd.DataFrame(all_company_data)
    total_market_cap = df['MarketCap'].sum()
    top_10_mc = df.sort_values(by='MarketCap', ascending=False).head(10).reset_index(drop=True)
    top_10_mc['Rank'] = top_10_mc.index + 1
    top_10_mc['% of Index'] = (top_10_mc['MarketCap'] / total_market_cap)
    
    growth_df = df[df['RevenueGrowth'].notna() & (df['RevenueGrowth'] != 0)].copy()
    top_10_rg = growth_df.sort_values(by='RevenueGrowth', ascending=False).head(10).reset_index(drop=True)
    top_10_rg['Rank'] = top_10_rg.index + 1
    
    return top_10_mc, top_10_rg, total_market_cap

# Cache 3: Find consistent growers (intensive operation)
@st.cache_data(ttl=3600)
def find_consistent_growers(tickers, required_growth_pct, num_years):
    st.info(f"Screening for consistent growers... (This is intensive and may take a few minutes on first run)")
    consistent_growers = []
    required_growth = required_growth_pct / 100.0
    progress_bar = st.progress(0, text="Analyzing annual financials...")

    for i, ticker_symbol in enumerate(tickers):
        try:
            # Fetch annual income statement
            income_statement = yf.Ticker(ticker_symbol).income_stmt
            if income_statement.empty or 'Total Revenue' not in income_statement.index:
                continue

            revenue = income_statement.loc['Total Revenue'].dropna().replace(0, pd.NA).dropna()
            
            # Need N+1 years of data to calculate N years of growth
            if len(revenue) < num_years + 1:
                continue

            # Calculate year-over-year growth
            growth = revenue.pct_change(periods=-1).dropna()
            
            if len(growth) < num_years:
                continue

            # Check if the most recent N years meet the criteria
            recent_growth = growth.head(num_years)
            if (recent_growth >= required_growth).all():
                grower_data = {'Ticker': ticker_symbol, 'Name': yf.Ticker(ticker_symbol).info.get('shortName', ticker_symbol)}
                # Add the last few years of growth to the output
                for j, g in enumerate(recent_growth.head(4)): # Show up to 4 years of growth
                    grower_data[f'YoY Growth Y-{j+1}'] = g
                consistent_growers.append(grower_data)

        except Exception:
            continue
        finally:
            progress_bar.progress((i + 1) / len(tickers), text=f"Analyzing: {ticker_symbol}")
    
    progress_bar.empty()
    if not consistent_growers: return pd.DataFrame()
    return pd.DataFrame(consistent_growers)

# --- Main App Interface ---
st.title("👑 S&P 500 Live Dashboard")
st.markdown("A tool to identify market leaders by size, quarterly growth, and long-term sales consistency.")

if st.button("🔄 Refresh All Data"):
    st.cache_data.clear()
    st.toast("Data caches cleared! All data will be re-fetched.")

# --- Section 1 & 2: Market Cap and Quarterly Growth ---
st.header("🏆 Top 10 by Market Capitalization & Quarterly Growth")
all_tickers = get_sp500_tickers()
if all_tickers:
    df_top_10_mc, df_top_10_rg, total_cap = fetch_market_cap_data(all_tickers)
    if df_top_10_mc is not None:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("By Market Cap")
            top_10_weight_sum = df_top_10_mc['% of Index'].sum()
            st.metric("Top 10 Weight", value=format_percentage(top_10_weight_sum))
            st.metric("Total Index Cap", value=format_market_cap(total_cap))
            
            display_mc = df_top_10_mc[['Rank', 'Name', 'Ticker', 'MarketCap', '% of Index']].copy()
            display_mc['Market Cap'] = display_mc['MarketCap'].apply(format_market_cap)
            display_mc['% of Index'] = display_mc['% of Index'].apply(format_percentage)
            st.dataframe(display_mc, use_container_width=True, hide_index=True)
            
        with col2:
            st.subheader("By Revenue Growth (YoY Quarterly)")
            if df_top_10_rg is not None and not df_top_10_rg.empty:
                display_rg = df_top_10_rg[['Rank', 'Name', 'Ticker', 'RevenueGrowth']].copy()
                display_rg.rename(columns={'RevenueGrowth': 'Revenue Growth'}, inplace=True)
                display_rg['Revenue Growth'] = display_rg['Revenue Growth'].apply(format_percentage)
                st.dataframe(display_rg, use_container_width=True, hide_index=True)
            else:
                st.info("No companies with positive quarterly revenue growth found.")

# --- Section 3: Consistent Growth Champions ---
st.header("📈 Consistent Annual Revenue Growth Screener")
st.markdown("Find companies with consistent year-over-year revenue growth. This analysis is data-intensive and is cached.")

if all_tickers:
    col1, col2 = st.columns(2)
    with col1:
        growth_threshold_pct = st.slider(
            "Required Annual Growth Rate (%)", 
            min_value=5, max_value=50, value=20, step=1
        )
    with col2:
        num_years = st.slider(
            "Number of Consecutive Years", 
            min_value=2, max_value=5, value=3, step=1
        )

    # Find and display the consistent growers
    champions_df = find_consistent_growers(all_tickers, growth_threshold_pct, num_years)

    if not champions_df.empty:
        st.success(f"Found {len(champions_df)} companies meeting the criteria!")
        # Dynamically format the growth columns
        for col in champions_df.columns:
            if "Growth" in col:
                champions_df[col] = champions_df[col].apply(format_percentage)
        st.dataframe(champions_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No companies found with at least {growth_threshold_pct}% annual revenue growth for the last {num_years} consecutive years. Try lowering the criteria.")
