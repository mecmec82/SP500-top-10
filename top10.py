import streamlit as st
import pandas as pd
import yfinance as yf
import time
import altair as alt

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="S&P 500 Analytics Dashboard",
    page_icon="💎",
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

def format_pe(pe):
    if not isinstance(pe, (int, float)) or pe <= 0: return "N/A"
    return f"{pe:.2f}"

# --- DATA FETCHING & PROCESSING (with Caching) ---

@st.cache_data(ttl=86400)
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

@st.cache_data(ttl=3600)
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

@st.cache_data(ttl=3600)
def find_consistent_growers(tickers, required_growth_pct, num_years):
    st.info(f"Screening for consistent growers... (This is intensive and may take a few minutes on first run)")
    consistent_growers = []
    required_growth = required_growth_pct / 100.0
    progress_bar = st.progress(0, text="Analyzing annual financials...")

    for i, ticker_symbol in enumerate(tickers):
        try:
            ticker = yf.Ticker(ticker_symbol)
            income_statement = ticker.income_stmt
            if income_statement.empty or 'Total Revenue' not in income_statement.index: continue
            
            revenue = income_statement.loc['Total Revenue'].dropna().replace(0, pd.NA).dropna()
            if len(revenue) < num_years + 1: continue

            growth = revenue.pct_change(periods=-1).dropna()
            if len(growth) < num_years: continue

            recent_growth = growth.head(num_years)
            if (recent_growth >= required_growth).all():
                info = ticker.info
                ending_revenue = revenue.iloc[0]
                beginning_revenue = revenue.iloc[num_years]
                cagr = ((ending_revenue / beginning_revenue) ** (1/num_years)) - 1 if beginning_revenue > 0 else 0
                pe_ratio = info.get('trailingPE')

                grower_data = {
                    'Ticker': ticker_symbol, 'Name': info.get('shortName', ticker_symbol),
                    'P/E Ratio': pe_ratio, 'Revenue CAGR': cagr
                }
                consistent_growers.append(grower_data)
        except Exception: continue
        finally:
            progress_bar.progress((i + 1) / len(tickers), text=f"Analyzing: {ticker_symbol}")
    
    progress_bar.empty()
    if not consistent_growers: return pd.DataFrame()
    return pd.DataFrame(consistent_growers)

# --- Main App Interface ---
st.title("💎 S&P 500 Analytics Dashboard")
st.markdown("A tool to identify market leaders by size, quarterly growth, and long-term value creation.")

if st.button("🔄 Refresh All Data"):
    st.cache_data.clear()
    st.toast("Data caches cleared! All data will be re-fetched.")

st.header("🏆 Top 10 Leaderboards")
all_tickers = get_sp500_tickers()
if all_tickers:
    df_top_10_mc, df_top_10_rg, total_cap = fetch_market_cap_data(all_tickers)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("By Market Capitalization")
        if df_top_10_mc is not None:
            display_mc = df_top_10_mc[['Rank', 'Name', 'Ticker', '% of Index']].copy()
            display_mc['% of Index'] = display_mc['% of Index'].apply(format_percentage)
            st.dataframe(display_mc, use_container_width=True, hide_index=True)
    with col2:
        st.subheader("By Revenue Growth (YoY Quarterly)")
        if df_top_10_rg is not None and not df_top_10_rg.empty:
            display_rg = df_top_10_rg[['Rank', 'Name', 'Ticker', 'RevenueGrowth']].copy()
            display_rg.rename(columns={'RevenueGrowth': 'Quarterly Growth'}, inplace=True)
            display_rg['Quarterly Growth'] = display_rg['Quarterly Growth'].apply(format_percentage)
            st.dataframe(display_rg, use_container_width=True, hide_index=True)

st.header("📈 Consistent Growth & Value Screener")
st.markdown("Find companies with consistent year-over-year revenue growth and analyze their valuation.")

if all_tickers:
    c1, c2 = st.columns(2)
    with c1:
        growth_threshold = c1.slider("Required Annual Growth Rate (%)", 5, 50, 20, 1)
    with c2:
        years = c2.slider("Number of Consecutive Years", 2, 5, 3, 1)

    champions_df = find_consistent_growers(all_tickers, growth_threshold, years)

    if not champions_df.empty:
        st.success(f"Found {len(champions_df)} companies meeting the criteria!")
        
        # --- Display Table ---
        display_champions = champions_df[['Name', 'Ticker', 'Revenue CAGR', 'P/E Ratio']].copy()
        display_champions['Revenue CAGR'] = display_champions['Revenue CAGR'].apply(format_percentage)
        display_champions['P/E Ratio'] = display_champions['P/E Ratio'].apply(format_pe)
        st.dataframe(display_champions, use_container_width=True, hide_index=True)

        # --- Display Scatter Plot ---
        st.subheader("Growth vs. Value Analysis")
        chart_df = champions_df[['Name', 'Ticker', 'Revenue CAGR', 'P/E Ratio']].copy().dropna()
        chart_df = chart_df[(chart_df['P/E Ratio'] > 0) & (chart_df['P/E Ratio'] < 200)]

        if not chart_df.empty:
            # This is the new, robust chart creation block
            chart = alt.Chart(chart_df).mark_circle(size=80).encode(
                x=alt.X('P/E Ratio:Q', scale=alt.Scale(zero=False), title='P/E Ratio (Value)'),
                y=alt.Y('Revenue CAGR:Q', axis=alt.Axis(format='%'), title='Revenue CAGR (Growth)'),
                color=alt.Color('P/E Ratio:Q', scale=alt.Scale(scheme='redyellowblue', reverse=True)),
                tooltip=['Name', 'Ticker', alt.Tooltip('Revenue CAGR:Q', format='.2%'), 'P/E Ratio']
            ).properties(
                title='Growth at a Reasonable Price (GARP) Analysis'
            ).interactive()

            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No companies with positive P/E ratios found to plot.")
    else:
        st.warning(f"No companies found with at least {growth_threshold}% annual revenue growth for the last {years} consecutive years. Try lowering the criteria.")
