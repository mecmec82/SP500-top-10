import streamlit as st
import pandas as pd
import yfinance as yf
import time

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="S&P 500 Live Dashboard",
    page_icon="🚀",
    layout="wide"
)

# --- Caching ---
# The function now returns three items: market cap table, revenue growth table, and total market cap.
@st.cache_data(ttl=3600)
def fetch_sp500_data():
    """
    Orchestrates the data fetching and processing pipeline.
    Returns a tuple: (top_10_mc_df, top_10_rg_df, total_market_cap)
    """
    # --- 1. GET S&P 500 TICKERS ---
    try:
        st.info("Fetching S&P 500 constituents from Wikipedia...")
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(url)
        sp500_table = tables[0]
        tickers = sp500_table['Symbol'].str.replace('.', '-', regex=False).tolist()
    except Exception as e:
        st.error(f"Failed to fetch tickers from Wikipedia: {e}")
        return None, None, None

    # --- 2. GET MARKET CAPS AND REVENUE GROWTH ---
    st.info(f"Fetching data for {len(tickers)} tickers... (This may take a minute)")
    all_company_data = []
    progress_bar = st.progress(0, text="Fetching...")

    for i, ticker_symbol in enumerate(tickers):
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            
            # Fetch both market cap and revenue growth
            market_cap = info.get('marketCap')
            revenue_growth = info.get('revenueGrowth') # This is YoY quarterly growth

            # Only add to our list if market cap is present
            if market_cap and market_cap > 0:
                all_company_data.append({
                    'Ticker': ticker_symbol, 
                    'Name': info.get('shortName', 'N/A'),
                    'MarketCap': market_cap,
                    'RevenueGrowth': revenue_growth # This may be None
                })
            progress_bar.progress((i + 1) / len(tickers), text=f"Fetching: {ticker_symbol}")
            time.sleep(0.01)
        except Exception:
            continue
            
    progress_bar.empty()

    if not all_company_data:
        st.error("Could not fetch any company data.")
        return None, None, None
        
    # Create a single DataFrame with all data
    df = pd.DataFrame(all_company_data)

    # --- 3a. PROCESS FOR MARKET CAP RANKING ---
    total_market_cap = df['MarketCap'].sum()
    top_10_mc = df.sort_values(by='MarketCap', ascending=False).head(10).reset_index(drop=True)
    top_10_mc['Rank'] = top_10_mc.index + 1
    top_10_mc['% of Index'] = (top_10_mc['MarketCap'] / total_market_cap)
    
    # --- 3b. PROCESS FOR REVENUE GROWTH RANKING ---
    # Filter for companies that have revenue growth data and are not zero
    growth_df = df[df['RevenueGrowth'].notna() & (df['RevenueGrowth'] != 0)].copy()
    top_10_rg = growth_df.sort_values(by='RevenueGrowth', ascending=False).head(10).reset_index(drop=True)
    top_10_rg['Rank'] = top_10_rg.index + 1

    return top_10_mc, top_10_rg, total_market_cap

# --- Helper functions for formatting ---
def format_market_cap(cap):
    if not isinstance(cap, (int, float)): return "N/A"
    if cap > 1e12: return f"${cap / 1e12:.2f} T"
    if cap > 1e9: return f"${cap / 1e9:.2f} B"
    return f"${cap / 1e6:.2f} M"

def format_percentage(pct):
    if not isinstance(pct, (int, float)): return "N/A"
    return f"{pct:.2%}"

# --- Main App Interface ---
st.title("🚀 S&P 500 Live Dashboard")
st.markdown("Comparing market leaders (by size) with growth leaders (by sales velocity).")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.toast("Data refreshed!")

try:
    # Unpack the three items returned by the function
    df_top_10_mc, df_top_10_rg, total_cap = fetch_sp500_data()

    if df_top_10_mc is not None:
        st.header("🏆 Top 10 by Market Capitalization")
        
        col1, col2 = st.columns(2)
        top_10_weight_sum = df_top_10_mc['% of Index'].sum()
        col1.metric("Top 10 Weight Concentration", value=format_percentage(top_10_weight_sum))
        col2.metric("Total S&P 500 Market Cap", value=format_market_cap(total_cap))

        display_mc = df_top_10_mc[['Rank', 'Name', 'Ticker', 'MarketCap', '% of Index']].copy()
        display_mc['Market Cap'] = display_mc['MarketCap'].apply(format_market_cap)
        display_mc['% of Index'] = display_mc['% of Index'].apply(format_percentage)
        
        st.dataframe(display_mc, use_container_width=True, hide_index=True)

    if df_top_10_rg is not None:
        st.header("📈 Top 10 by Revenue Growth (YoY Quarterly)")
        
        display_rg = df_top_10_rg[['Rank', 'Name', 'Ticker', 'RevenueGrowth']].copy()
        display_rg.rename(columns={'RevenueGrowth': 'Revenue Growth'}, inplace=True)
        display_rg['Revenue Growth'] = display_rg['Revenue Growth'].apply(format_percentage)
        
        st.dataframe(display_rg, use_container_width=True, hide_index=True)
    
    if df_top_10_mc is not None or df_top_10_rg is not None:
        st.success("Data loaded successfully.")

except Exception as e:
    st.error(f"An error occurred during execution: {e}")
