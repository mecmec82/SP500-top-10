import streamlit as st
import pandas as pd
import yfinance as yf
import altair as alt

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="S&P 500 Analytics Dashboard", page_icon="⚡", layout="wide")

# --- HELPER FUNCTIONS for formatting ---
def format_percentage(pct):
    if not isinstance(pct, (int, float)): return "N/A"
    return f"{pct:.2%}"

def format_pe(pe):
    if not isinstance(pe, (int, float)) or pe <= 0: return "N/A"
    return f"{pe:.2f}"

# --- EFFICIENT DATA FETCHING & PROCESSING ---

@st.cache_data(ttl=86400)
def get_sp500_tickers():
    st.info("Fetching S&P 500 constituents from Wikipedia...")
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(url)
        return tables[0]['Symbol'].str.replace('.', '-', regex=False).tolist()
    except Exception as e:
        st.error(f"Failed to fetch tickers from Wikipedia: {e}")
        return []

@st.cache_data(ttl=3600)
def fetch_all_sp500_data(tickers, num_years_cagr):
    st.info(f"Performing deep scan on {len(tickers)} tickers... (This is efficient but may take a few minutes on first run)")
    all_data = []
    progress_bar = st.progress(0, text="Analyzing...")

    for i, ticker_symbol in enumerate(tickers):
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            income_statement = ticker.income_stmt

            # --- Gather all raw data points in one go ---
            market_cap = info.get('marketCap')
            if not market_cap or market_cap <= 0: continue

            # --- Calculate CAGR ---
            cagr = None
            if not income_statement.empty and 'Total Revenue' in income_statement.index:
                revenue = income_statement.loc['Total Revenue'].dropna()
                if len(revenue) >= num_years_cagr + 1:
                    ending_revenue = revenue.iloc[0]
                    beginning_revenue = revenue.iloc[num_years_cagr]
                    if beginning_revenue > 0:
                        cagr = ((ending_revenue / beginning_revenue) ** (1/num_years_cagr)) - 1
            
            all_data.append({
                'Ticker': ticker_symbol,
                'Name': info.get('shortName', 'N/A'),
                'MarketCap': market_cap,
                'QuarterlyGrowth': info.get('revenueGrowth'),
                'PERatio': info.get('trailingPE'),
                'CAGR': cagr
            })
        except Exception:
            continue
        finally:
            progress_bar.progress((i + 1) / len(tickers), text=f"Analyzing: {ticker_symbol}")
    
    progress_bar.empty()
    return pd.DataFrame(all_data)

# --- Main App Interface ---
st.title("⚡ S&P 500 Analytics Dashboard")
st.markdown("An efficient tool to identify market leaders by size, growth, and value.")

if st.button("🔄 Refresh All Data"):
    st.cache_data.clear()
    st.toast("Data caches cleared! All data will be re-fetched on next interaction.")

st.header("🏆 Top 10 Leaderboards")
all_tickers = get_sp500_tickers()
if all_tickers:
    # We only need 1 year of data for the top-level leaderboards, so we pass '1' for num_years_cagr
    # This doesn't affect the CAGR calculation for the growth section, just makes the initial load faster.
    master_df = fetch_all_sp500_data(all_tickers, 1)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("By Market Capitalization")
        top_10_mc = master_df.sort_values(by='MarketCap', ascending=False).head(10)
        total_cap = master_df['MarketCap'].sum()
        top_10_mc['% of Index'] = (top_10_mc['MarketCap'] / total_cap)
        st.dataframe(top_10_mc[['Name', 'Ticker', '% of Index']].rename(columns={'% of Index': 'Index Weight'}), use_container_width=True, hide_index=True)

    with col2:
        st.subheader("By Quarterly Revenue Growth")
        top_10_rg = master_df.dropna(subset=['QuarterlyGrowth']).sort_values(by='QuarterlyGrowth', ascending=False).head(10)
        display_rg = top_10_rg[['Name', 'Ticker', 'QuarterlyGrowth']].copy()
        display_rg['QuarterlyGrowth'] = display_rg['QuarterlyGrowth'].apply(format_percentage)
        st.dataframe(display_rg, use_container_width=True, hide_index=True)

st.header("📈 Consistent Growth & Value Screener")
st.markdown("Find companies with strong, multi-year revenue growth and analyze their current valuation.")

if 'master_df' in locals() and not master_df.empty:
    c1, c2 = st.columns(2)
    years = c1.slider("Revenue CAGR over how many years?", 2, 5, 3, 1)
    
    # Re-run the data fetch only if the number of years for CAGR changes
    # This is an optimization to reuse the fetched data if possible
    champions_df_raw = fetch_all_sp500_data(all_tickers, years)
    
    # Filter by the growth threshold using the calculated CAGR
    growth_threshold = c2.slider("Minimum Required CAGR (%)", 5, 50, 20, 1)
    champions_df = champions_df_raw[champions_df_raw['CAGR'] >= (growth_threshold / 100.0)].copy()

    if not champions_df.empty:
        st.success(f"Found {len(champions_df)} companies meeting the criteria!")
        
        # --- Display Table ---
        display_champions = champions_df[['Name', 'Ticker', 'CAGR', 'PERatio']].rename(columns={'CAGR': 'Revenue CAGR', 'PERatio': 'P/E Ratio'})
        display_champions['Revenue CAGR'] = display_champions['Revenue CAGR'].apply(format_percentage)
        display_champions['P/E Ratio'] = display_champions['P/E Ratio'].apply(format_pe)
        st.dataframe(display_champions, use_container_width=True, hide_index=True)

        # --- Display Scatter Plot ---
        st.subheader("Growth vs. Value Analysis")
        chart_df = champions_df[['Name', 'Ticker', 'CAGR', 'PERatio']].copy().dropna()
        chart_df = chart_df[(chart_df['PERatio'] > 0) & (chart_df['PERatio'] < 200)]

        if not chart_df.empty:
            # Base scatter plot layer
            scatter = alt.Chart(chart_df).mark_circle(size=100, opacity=0.7).encode(
                x=alt.X('PERatio:Q', scale=alt.Scale(zero=False), title='P/E Ratio (Value)'),
                y=alt.Y('CAGR:Q', axis=alt.Axis(format='%'), title='Revenue CAGR (Growth)'),
                color=alt.Color('PERatio:Q', scale=alt.Scale(scheme='viridis'), title='P/E Ratio'),
                tooltip=['Name', 'Ticker', alt.Tooltip('CAGR:Q', format='.2%'), 'PERatio']
            )
            # Text labels layer
            labels = scatter.mark_text(align='left', baseline='middle', dx=7, fontSize=11).encode(
                text='Ticker:N',
                color=alt.value('black') # Make labels always visible
            )
            chart = (scatter + labels).properties(
                title='Growth at a Reasonable Price (GARP) Analysis'
            ).interactive()
            st.altair_chart(chart, use_container_width=True)
    else:
        st.warning(f"No companies found with at least {growth_threshold}% CAGR over the last {years} years. Try lowering the criteria.")
