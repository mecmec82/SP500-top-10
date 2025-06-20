import streamlit as st
import pandas as pd
import yfinance as yf

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="S&P 500 Portfolio Builder", page_icon="🏦", layout="wide")

# --- HELPER FUNCTIONS for formatting ---
def format_percentage(pct):
    if not isinstance(pct, (int, float)): return "N/A"
    return f"{pct:.2%}"

def format_pe(pe):
    if not isinstance(pe, (int, float)) or pe <= 0: return "N/A"
    return f"{pe:.2f}"

def format_garp(ratio):
    if not isinstance(ratio, (int, float)) or ratio <= 0: return "N/A"
    return f"{ratio:.3f}"

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
    st.info(f"Performing deep scan on {len(tickers)} tickers... (This is efficient and runs only when parameters change)")
    all_data = []
    progress_bar = st.progress(0, text="Analyzing...")

    for i, ticker_symbol in enumerate(tickers):
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            income_statement = ticker.income_stmt

            market_cap = info.get('marketCap')
            if not market_cap or market_cap <= 0: continue

            cagr = None
            if not income_statement.empty and 'Total Revenue' in income_statement.index:
                revenue = income_statement.loc['Total Revenue'].dropna()
                if len(revenue) >= num_years_cagr + 1:
                    ending_revenue = revenue.iloc[0]
                    beginning_revenue = revenue.iloc[num_years_cagr]
                    if beginning_revenue > 0:
                        cagr = ((ending_revenue / beginning_revenue) ** (1/num_years_cagr)) - 1
            
            all_data.append({
                'Ticker': ticker_symbol, 'Name': info.get('shortName', 'N/A'),
                'Sector': info.get('sector', 'N/A'), 'MarketCap': market_cap,
                'QuarterlyGrowth': info.get('revenueGrowth'),
                'PERatio': info.get('trailingPE'), 'CAGR': cagr
            })
        except Exception:
            continue
        finally:
            progress_bar.progress((i + 1) / len(tickers), text=f"Analyzing: {ticker_symbol}")
    
    progress_bar.empty()
    return pd.DataFrame(all_data)

# --- Main App Interface ---
st.title("🏦 S&P 500 Analytics & Portfolio Builder")
st.markdown("An efficient tool to identify market leaders and build a suggested portfolio based on size, growth, and value.")

if st.button("🔄 Refresh All Data"):
    st.cache_data.clear()
    st.toast("Data caches cleared! All data will be re-fetched on next interaction.")

st.header("🏆 Top 10 Leaderboards")
all_tickers = get_sp500_tickers()
if all_tickers:
    master_df = fetch_all_sp500_data(all_tickers, 1)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("By Market Capitalization")
        top_10_mc = master_df.sort_values(by='MarketCap', ascending=False).head(10)
        st.dataframe(top_10_mc[['Name', 'Ticker', 'Sector']], use_container_width=True, hide_index=True)

    with col2:
        st.subheader("By Quarterly Revenue Growth")
        top_10_rg = master_df.dropna(subset=['QuarterlyGrowth']).sort_values(by='QuarterlyGrowth', ascending=False).head(10)
        st.dataframe(top_10_rg[['Name', 'Ticker', 'Sector', 'QuarterlyGrowth']].rename(columns={'QuarterlyGrowth': 'Quarterly Growth'}), use_container_width=True, hide_index=True)

st.header("✨ Consistent Growth & Value (GARP) Screener")
st.markdown("Find companies with strong, multi-year revenue growth relative to their price.")

if 'master_df' in locals() and not master_df.empty:
    c1, c2 = st.columns(2)
    years = c1.slider("Revenue CAGR over how many years?", 2, 5, 3, 1)
    growth_threshold = c2.slider("Minimum Required CAGR (%)", 5, 50, 20, 1)
    
    champions_df_raw = fetch_all_sp500_data(all_tickers, years)
    champions_df = champions_df_raw[champions_df_raw['CAGR'] >= (growth_threshold / 100.0)].copy()
    
    valid_pe = (champions_df['PERatio'].notna()) & (champions_df['PERatio'] > 0)
    champions_df['GARP Ratio'] = 0.0
    champions_df.loc[valid_pe, 'GARP Ratio'] = champions_df['CAGR'] / champions_df['PERatio']
    champions_df = champions_df.sort_values(by='GARP Ratio', ascending=False)

    if not champions_df.empty:
        # --- NEW: Sector Multiselect Filter ---
        all_sectors = sorted(champions_df['Sector'].dropna().unique())
        selected_sectors = st.multiselect(
            'Filter GARP Champions by Sector:',
            options=all_sectors,
            default=all_sectors
        )
        
        # Filter the DataFrame based on selection
        filtered_champions_df = champions_df[champions_df['Sector'].isin(selected_sectors)]
        top_10_garp = filtered_champions_df.head(10)

        st.success(f"Displaying top 10 GARP champions from selected sectors.")
        display_champions = top_10_garp[['Name', 'Ticker', 'Sector', 'CAGR', 'PERatio', 'GARP Ratio']].rename(columns={'CAGR': 'Revenue CAGR', 'PERatio': 'P/E Ratio'})
        display_champions['Revenue CAGR'] = display_champions['Revenue CAGR'].apply(format_percentage)
        display_champions['P/E Ratio'] = display_champions['P/E Ratio'].apply(format_pe)
        display_champions['GARP Ratio'] = display_champions['GARP Ratio'].apply(format_garp)
        st.dataframe(display_champions, use_container_width=True, hide_index=True)

        # --- NEW: Suggested Portfolio Allocation Section ---
        st.header("📊 Suggested Portfolio Allocation")
        portfolio = {}
        reasons = {}

        # The allocation logic now uses the potentially filtered top_10_garp DataFrame
        for _, row in top_10_mc.iterrows():
            portfolio[row['Ticker']] = 5.0
            reasons[row['Ticker']] = "Top 10 by Market Cap (Core Holding)"
        
        for _, row in top_10_rg.iterrows():
            if row['Ticker'] not in portfolio:
                portfolio[row['Ticker']] = 1.0
                reasons[row['Ticker']] = "Top 10 by Quarterly Growth"

        for _, row in top_10_garp.iterrows():
            if row['Ticker'] not in portfolio:
                portfolio[row['Ticker']] = 1.0
                reasons[row['Ticker']] = "Top 10 by Growth/Value (GARP)"

        if portfolio:
            portfolio_list = [{'Ticker': t, 'Allocation (%)': a, 'Reason': reasons[t]} for t, a in portfolio.items()]
            portfolio_df = pd.DataFrame(portfolio_list)
            portfolio_df = pd.merge(portfolio_df, master_df[['Ticker', 'Name', 'Sector']], on='Ticker', how='left')
            portfolio_df = portfolio_df[['Name', 'Ticker', 'Sector', 'Allocation (%)', 'Reason']]
            st.dataframe(portfolio_df, use_container_width=True, hide_index=True)
            total_allocation = portfolio_df['Allocation (%)'].sum()
            st.metric("Total Suggested Allocation", f"{total_allocation:.0f}% of portfolio")

    else:
        st.warning(f"No companies found with at least {growth_threshold}% CAGR over the last {years} years. Try lowering the criteria.")
