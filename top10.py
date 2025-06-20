import streamlit as st
import pandas as pd
import yfinance as yf
import time

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="S&P 500 Live Market Cap",
    page_icon="📊",
    layout="wide"
)

# --- Caching ---
# We use @st.cache_data to avoid re-scraping on every interaction.
# The cache will expire after 1 hour (3600 seconds).
@st.cache_data(ttl=3600)
def fetch_and_process_top_10():
    """
    Orchestrates the entire data fetching and processing pipeline.
    This function's output is cached by Streamlit.
    """
    # --- 1. GET S&P 500 TICKERS from Wikipedia ---
    try:
        st.info("Fetching S&P 500 constituents from Wikipedia...")
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(url)
        sp500_table = tables[0]
        tickers = sp500_table['Symbol'].str.replace('.', '-', regex=False).tolist()
    except Exception as e:
        st.error(f"Failed to fetch tickers from Wikipedia: {e}")
        return None

    # --- 2. GET MARKET CAPS from yfinance ---
    st.info(f"Fetching market caps for {len(tickers)} tickers from Yahoo Finance... (This may take a minute)")
    market_data = []
    progress_bar = st.progress(0, text="Fetching...")

    for i, ticker_symbol in enumerate(tickers):
        try:
            ticker = yf.Ticker(ticker_symbol)
            # .info is a dictionary containing company summary data
            market_cap = ticker.info.get('marketCap')
            
            if market_cap and market_cap > 0:
                market_data.append({
                    'Ticker': ticker_symbol, 
                    'Name': ticker.info.get('shortName', 'N/A'),
                    'MarketCap': market_cap
                })
            
            # Update the progress bar
            progress_bar.progress((i + 1) / len(tickers), text=f"Fetching: {ticker_symbol}")
            time.sleep(0.01) # Small delay to prevent overwhelming the source

        except Exception:
            # Silently fail for individual tickers, as some may be delisted or have issues
            continue
            
    progress_bar.empty() # Remove the progress bar after completion

    # --- 3. PROCESS AND RANK ---
    if not market_data:
        st.error("Could not fetch any market cap data.")
        return None
        
    df = pd.DataFrame(market_data)
    top_10 = df.sort_values(by='MarketCap', ascending=False).head(10).reset_index(drop=True)
    top_10['Rank'] = top_10.index + 1
    
    return top_10[['Rank', 'Name', 'Ticker', 'MarketCap']]

# --- Helper function for formatting ---
def format_market_cap(cap):
    if cap > 1e12:
        return f"${cap / 1e12:.2f} T"
    elif cap > 1e9:
        return f"${cap / 1e9:.2f} B"
    else:
        return f"${cap / 1e6:.2f} M"

# --- Main App Interface ---
st.title("📊 Live S&P 500 Top 10 by Market Cap")
st.markdown("This app scrapes the S&P 500 constituents from Wikipedia and fetches their live market capitalization from Yahoo Finance.")

# Create columns for layout
col1, col2, col3 = st.columns([1, 1, 5])

# Add a refresh button
if col1.button("🔄 Refresh Data"):
    # Clear the cache to force a re-run of the data fetching function
    st.cache_data.clear()
    st.toast("Data refreshed!")

# Fetch and display the data
try:
    df_top_10 = fetch_and_process_top_10()

    if df_top_10 is not None:
        # Create a display-friendly DataFrame with formatted market caps
        display_df = df_top_10.copy()
        display_df['Market Cap'] = display_df['MarketCap'].apply(format_market_cap)
        display_df.drop(columns=['MarketCap'], inplace=True)
        
        st.subheader("Current Top 10 Companies")
        # Use st.dataframe to display the table. use_container_width makes it responsive.
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.success("Data loaded successfully.")

except Exception as e:
    st.error(f"An error occurred during execution: {e}")
