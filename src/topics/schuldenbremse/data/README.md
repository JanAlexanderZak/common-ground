# Data

**Status: reviewed 2026-06-23.** The three time series below were checked
against official Eurostat dissemination API datasets and updated to those
published values. Refresh the series before public release if a newer Eurostat
dataset timestamp is available.

| File | Columns | Source (canonical) | Review status |
|---|---|---|---|
| `debt-to-gdp.csv` | `year`, `debt_to_gdp_pct` | Eurostat `gov_10dd_edpt1`, `GD`, `PC_GDP`, `S13`, `DE` — government consolidated gross debt in % GDP | Reviewed 2026-06-23; dataset timestamp 2026-04-22 |
| `bip-wachstum.csv` | `year`, `real_gdp_growth_pct` | Eurostat `nama_10_gdp`, `B1GQ`, `CLV_PCH_PRE`, `DE` — chain-linked GDP, percentage change on previous period | Reviewed 2026-06-23; dataset timestamp 2026-06-19; 2022-2024 provisional |
| `inflation-hvpi.csv` | `year`, `inflation_pct` | Eurostat `prc_hicp_aind`, `CP00`, `RCH_A_AVG`, `DE` — all-items HICP annual average rate of change | Reviewed 2026-06-23; dataset timestamp 2026-02-06 |

## Source links

- **debt-to-gdp.csv**: <https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_10dd_edpt1?geo=DE&unit=PC_GDP&sector=S13&na_item=GD>
- **bip-wachstum.csv**: <https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nama_10_gdp?geo=DE&unit=CLV_PCH_PRE&na_item=B1GQ>
- **inflation-hvpi.csv**: <https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_aind?geo=DE&unit=RCH_A_AVG&coicop=CP00>

When refreshing these files, replace the values in place and update the
`Review status` column with the retrieval date and dataset timestamp.
