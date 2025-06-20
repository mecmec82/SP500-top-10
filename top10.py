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
# The function now returns the top 10 DataFrame AND the total market cap.
@st.cache_data(ttl=3600)
def fetch_and_process_data():
    """
    Orchestrates the data fetching and processing pipeline.
    Returns a tuple: (top_10_df, total_market_cap)
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
        return None, None

    # --- 2. GET MARKET CAPS ---
    st.info(f"Fetching market caps for {len(tickers)} tickers... (This may take a minute)")
    market_data = []
    progress_bar = st.progress(0, text="Fetching...")

    for i, ticker_symbol in enumerate(tickers):
        try:
            ticker = yf.Ticker(ticker_symbol)
            market_cap = ticker.info.get('marketCap')
            if market_cap and market_cap > 0:
                market_data.append({
                    'Ticker': ticker_symbol, 
                    'Name': ticker.info.get('shortName', 'N/A'),
                    'MarketCap': market_cap
                })
            progress_bar.progress((i + 1) / len(tickers), text=f"Fetching: {ticker_symbol}")
            time.sleep(0.01)
        except Exception:
            continue
            
    progress_bar.empty()

    # --- 3. PROCESS AND RANK ---
    if not market_data:
        st.error("Could not fetch any market cap data.")
        return None, None
        
    df = pd.DataFrame(market_data)
    
    # NEW: Calculate total market cap of the entire index
    total_market_cap = df['MarketCap'].sum()
    
    # Get the top 10
    top_10 = df.sort_values(by='MarketCap', ascending=False).head(10).reset_index(drop=True)
    top_10['Rank'] = top_10.index + 1
    
    # NEW: Calculate the weight percentage for each of the top 10
    top_10['% of Index'] = (top_10['MarketCap'] / total_market_cap)
    
    # Return both the DataFrame and the total market cap
    return top_10[['Rank', 'Name', 'Ticker', 'MarketCap', '% of Index']], total_market_cap

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
st.markdown("This app scrapes S&P 500 constituents and their live market caps to show the top 10 companies and their weight within the total index.")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.toast("Data refreshed!")

try:
    # Unpack the tuple returned by the function
    df_top_10, total_cap = fetch_and_process_data()

    if df_top_10 is not None:
        st.subheader("Key Metrics")
        
        # Display summary metrics in columns
        col1, col2 = st.columns(2)
        top_10_weight_sum = df_top_10['% of Index'].sum()
        col1.metric("Top 10 Weight Concentration", value=f"{top_10_weight_sum:.2%}")
        col2.metric("Total S&P 500 Market Cap", value=format_market_cap(total_cap))

        # Create a display-friendly DataFrame
        display_df = df_top_10.copy()
        display_df['Market Cap'] = display_df['MarketCap'].apply(format_market_cap)
        display_df['% of Index'] = display_df['% of Index'].apply(lambda w: f"{w:.2%}")
        display_df.drop(columns=['MarketCap'], inplace=True)
        
        st.subheader("Current Top 10 Companies")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.success("Data loaded successfully.")

except Exception as e:
    st.error(f"An error occurred during execution: {e}")
