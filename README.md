
# AI Financial Analyst
### A 90-Day Finance, Python, SQL & AI Portfolio

A hands-on project combining financial analysis, portfolio
management, quantitative research, SQL, Python and AI.

The objective is to build practical investment analytics tools,
automate financial research and develop a portfolio of projects
demonstrating both financial knowledge and technical skills.

## Tech Stack

- Python: Pandas, NumPy, Matplotlib, SciPy
- SQL: SQLite, window functions, CTEs
- Tools: VS Code, Jupyter Notebook, Git, GitHub
- Finance: Portfolio optimization, CAPM, risk attribution,
  Monte Carlo simulation and stress testing

## Project Progress

### Days 1–7: Python for Financial Analytics
- Stock returns and historical price analysis
- Portfolio risk and performance
- CAPM, beta and alpha
- Monte Carlo simulation
- Financial dashboards

### Days 8–15: Portfolio & Quantitative Analytics
- Hedge fund analytics
- Trading strategy analysis
- Portfolio optimization
- Out-of-sample backtesting
- Rolling portfolio optimization
- Portfolio stress testing
- Risk attribution and risk parity

### Days 16–17: SQL for Financial Analytics
- Connected Python to an SQLite financial database
- Explored database tables and validated price data
- Used SQL LAG() to calculate daily stock returns
- Calculated average daily returns and extreme daily moves
- Estimated annualized volatility
- Calculated compounded cumulative returns
- Created a risk-versus-return visualization

## Day 17: SQL Daily Returns & Risk Analysis

Analyzed five equities: AAPL, BLK, GS, JPM and MSFT,
using historical closing prices stored in SQLite.

### Annualized Volatility

| Stock | Volatility |
|-------|-----------:|
| AAPL  | 24.59% |
| BLK   | 27.51% |
| GS    | 32.22% |
| JPM   | 22.22% |
| MSFT  | 32.66% |

JPM had the lowest estimated historical volatility in
this sample, while MSFT had the highest.

The analysis uses 249 daily-return observations per stock
and assumes 252 trading days per year.

### Methodology

1. Retrieve stock prices from SQLite.
2. Calculate daily returns using SQL window functions.
3. Calculate annualized volatility using Python.
4. Calculate compounded cumulative returns.
5. Visualize historical risk versus return.

### Limitations

Results are based on historical closing prices and exclude
dividends and transaction costs. Historical performance
does not predict future results.

## Upcoming Projects

- Advanced SQL portfolio analytics
- Financial data pipelines
- Machine learning for credit risk
- AI-powered investment research assistant

## Project Status

Days 1–17 completed.
Currently progressing through SQL for Financial Analytics.

## Disclaimer

This repository is an educational research project.
It does not constitute investment advice.
