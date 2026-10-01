# ATLAS — Synthetic Data Generation Rules

Version: 0.2 (DRAFT) | Status: rules only; no generator code written yet

## 0. Change log

| Version | Change | Reason |
|---|---|---|
| 0.1 | First draft | Initial rules from the owner's review |
| 0.2 | Design aims are not pass/fail criteria; loss-making lines allowed and recorded; target base period and growth formula made explicit; pre-generation scale check added | Owner/ChatGPT review before any generator code exists |

### Version policy

- A rule change requires a documented reason: a calculation error or a design flaw. It is made by creating a new version with a change-log entry.
- A result outside a design aim (low-margin share, top-5 concentration, line count) is **not** a reason to change rules, seeds, or parameters. The result is recorded as generated and used as is.
- The seed and parameters are never changed in order to obtain a preferred outcome.
Items marked **(Proposed)** are simple, consistent starting values chosen by the implementer and open to review. Everything else is fixed by `PROJECT_BRIEF.md` or by the owner's review decisions.

## 1. Purpose and disclosure

- All data is synthetic and independently generated for a fictional B2B industrial-consumables supplier. It does not reflect any real company, customer, price, cost, or market.
- Market patterns (Thailand large and stable, Vietnam faster growth, Indonesia volatile) are learning assumptions, not statements about real markets.
- Findings from this data are not professional achievements and are not evidence of real business impact.
- Monetary values are modeled directly in USD. No FX conversion is implied.

## 2. Fixed scope (from the brief)

| Item | Value |
|---|---|
| Period | 24 months, 2024-01 to 2025-12 |
| Markets | Thailand, Vietnam, Indonesia |
| Customers | 20 (Thailand 7, Vietnam 7, Indonesia 6) |
| Products | 3 |
| Sales lines | approximately 1,500 |
| Tables | customers, products, sales, monthly_targets (72 target rows) |

## 3. Reproducibility

- **Seed (Proposed):** `20240101`.
- **Method (Proposed):** Python standard library only (`random.Random`). Each component uses its own generator, seeded as `seed + offset`, so changing one component does not change the others:
  customers `+1`, line counts `+2`, customer/product assignment `+3`, quantities `+4`, prices `+5`, special discounts `+6`, costs `+7`.
- **Rebuild:** delete `atlas.db`, run the generator script (to be written), and the database is recreated. `atlas.db` is not stored in Git; the script and these rules are.
- **Record:** the Python version (currently 3.14.8 on both machines) and the seed are written to the results file (section 11).
- **No post-hoc edits:** generated values are never adjusted to make an analysis look better. Actual outcomes are recorded as generated (section 11).

## 4. Tables

| Table | Grain (one row = ) | Fields |
|---|---|---|
| customers | one fictional customer | customer_id (PK, e.g. `C01`), customer_name, market |
| products | one fictional product | product_id (PK, e.g. `P01`), product_name, unit_of_sale |
| sales | one completed sales line | sales_line_id (PK, sequential by date), sale_date, customer_id (FK), product_id (FK), quantity, net_unit_price_usd, unit_cogs_usd |
| monthly_targets | one market in one month | month_start + market (combined PK), revenue_target_usd, gross_profit_target_usd |

- `sale_date` is stored as `YYYY-MM-DD`, with the day drawn uniformly from 1–28 within the month. `month_start` is `YYYY-MM-01`.
- No special-discount flag is stored in `sales`. The generator writes a separate `generation_log.csv` (sales_line_id, is_special_discount, special_discount_pct) used only for validation and excluded from Git. (Proposed)
- Prices and costs are **per one unit of sale**. Revenue = quantity × net_unit_price_usd. Gross profit = revenue − quantity × unit_cogs_usd. Operating expenses are excluded.

## 5. Products

| product_id | product_name | unit_of_sale | Base price (USD / unit) | Base COGS (USD / unit) | Base margin |
|---|---|---|---|---|---|
| P01 | Industrial Cutting Fluid | 20L container | 100 | 70 | 30.0% |
| P02 | Abrasive Disc Pack | box of 50 | 60 | 45 | 25.0% |
| P03 | Protective Glove Set | box of 100 pairs | 150 | 95 | 36.7% |

- Quantities of different products are in different units and must not be added together as a "volume" performance measure. Quantity comparisons are valid only within one product.
- Price and cost basis are always stated per unit of sale so the structure can be reused for other product types later. No other product data is part of this MVP.

Product mix per sales line (Proposed): P01 40%, P02 35%, P03 25%.
Median quantity per line (Proposed): P01 20, P02 40, P03 15 units.
Quantity = `max(1, round(median_quantity × lognormal(mu=0, sigma=0.4)))`, giving positive integers.

## 6. Customers

IDs and names (Proposed): `C01`–`C07` Thailand, `C08`–`C14` Vietnam, `C15`–`C20` Indonesia. Names are generic placeholders, e.g. `Customer TH-01`, `Customer VN-01`, `Customer ID-01`, to avoid resemblance to any real company.

**Purchase size tier (Proposed).** Tier sets each customer's relative share of sales lines within its market. Quantity per line does not depend on tier.

| Tier | Weight | Customers |
|---|---|---|
| Large (5) | 7 | C01, C02 (TH); C08, C09 (VN); C15 (ID) |
| Medium (6) | 3 | C03, C04, C05 (TH); C10, C11 (VN); C16 (ID) |
| Small (9) | 1 | C06, C07 (TH); C12, C13, C14 (VN); C17, C18, C19, C20 (ID) |

Design goal: the top 5 customers account for roughly 50–60% of total revenue. The weights are set toward that goal (hand estimate about 56% of lines), but this is a design aim, **not a pass/fail criterion**. The ratio is not forced. The actual concentration is measured after generation and recorded, whether or not it falls in the range.

**Customer price adjustment (Proposed).** Each customer draws one fixed `customer_adj` from Uniform(−0.04, +0.04), representing a standing discount or premium tendency.

**Special discount tendency (Proposed).** Probability that a line from the customer is a special discount deal:

| Group | Customers | Probability |
|---|---|---|
| High | C11, C18 | 0.45 |
| Elevated | C02, C09, C16 | 0.15 |
| Standard | all others | 0.03 |

## 7. Pricing rules

Applied in this order for each sales line.

**Step 1 — Normal price.**
`price_multiplier = 1 + customer_adj + txn_noise`, where `txn_noise ~ Uniform(−0.04, +0.04)` is drawn per line.
Because both terms are within ±0.04, the multiplier is within ±8% of base (guard: clip to [0.92, 1.08]; expected to never trigger).
`normal_price = base_price × price_multiplier`.

**Step 2 — Special discount decision.** Draw once per line with the customer's special-discount probability (section 6).

**Step 3 — Special discount depth (only if special).** `d ~ Uniform(0.12, 0.30)` (Proposed).
`net_unit_price_usd = normal_price × (1 − d)`. Special lines may fall outside the ±8% band; this is intended.
Non-special lines: `net_unit_price_usd = normal_price`.

**Step 4 — Rounding.** Round `net_unit_price_usd` to 2 decimals. Validation of the ±8% band uses a tolerance of 0.005 USD for rounding.

**Cost.** `unit_cogs_usd = base_cogs × (1 + e)`, `e ~ Uniform(−0.03, +0.03)` per line, rounded to 2 decimals. Cost is independent of price.

**Not modeled in v1:** seasonality, market-specific logistics cost adjustments, volume discounts, returns, credit notes, taxes, FX.

## 8. Low-margin behavior

- Project example threshold: gross margin **below 20%**. This is an illustrative project line, not an industry standard.
- Design aim (Proposed): about 8–10% of all sales lines have gross margin below 20%. This is a design aim, **not a pass/fail criterion**; the generated result is recorded and used as is, even if outside the range.
- Special-discount lines and low-margin lines are **not the same set**. By hand estimate: some special discounts on P03 stay above 20% margin (P03 needs roughly a 21% discount or more to fall below), while some normal lines of P02 can fall below 20% on their own (lowest-price, highest-cost combinations).
- Hand estimate before generation (not a result): special-discount lines about 8% of all lines. The low-margin share was not estimated by hand and may land below, within, or above the 8–10% design aim; it is measured after generation.
- Some customers have more frequent special discounts (section 6). Whether any customer ends up below 20% aggregate margin is **not guaranteed**.

Three measures are validated separately and reported side by side:
1. Share of lines that are special-discount deals (from `generation_log.csv`).
2. Share of lines with line-level gross margin below 20% (from `sales` and `products`).
3. Customer-level aggregate margin = sum of gross profit ÷ sum of revenue per customer, and which customers fall below 20%.

If a measure lands outside the design aim, it is recorded as is. Rules change only under the version policy in section 0 (calculation error or design flaw), never to hit a target range and never by editing generated rows.

**Loss-making lines are allowed.** A special discount can push `net_unit_price_usd` below `unit_cogs_usd`, giving negative gross profit (for example, a deep discount on P02 can price below its cost). Such lines are not deleted, repriced, or capped. `GENERATION_RESULTS.md` records the **count of sales lines with negative gross profit and their share of all sales lines**, reported as a fourth measure next to the three above. These lines are also included in the below-20% measure.

## 9. Market and time patterns

Number of sales lines per market-month:
`lines = round(base_lines × (1 + g)^(t/12) × demand_factor)`, where `t` = months since 2024-01 (0 to 23) and `demand_factor = clip(Normal(1, sigma), 0.5, 1.5)` drawn per market-month. Lines are then assigned to customers of that market with probability proportional to tier weight.

| Market | Base lines in 2024-01 (Proposed) | Annual line growth g (Proposed) | Demand volatility sigma (Proposed) | Assumption |
|---|---|---|---|---|
| Thailand | 28 | 3% | 0.05 | large scale, low volatility |
| Vietnam | 18 | 15% | 0.10 | relatively high growth |
| Indonesia | 13 | 8% | 0.20 | high volatility |

- Hand estimate: about 1,520 lines in total (target is approximately 1,500). The actual count is recorded as generated; a deviation alone does not trigger a rule change.
- No market is guaranteed to beat or miss its targets.

## 10. Monthly targets (planning assumptions)

Targets are created from the plan assumptions below only. **They never read, reference, or are back-calculated from generated sales, and are never tuned to reach any attainment level.**

### Definitions

- **Start monthly revenue** = the **revenue target (USD) for January of that year**, for that market. It is a monthly figure, not an annual one.
- **Plan growth rate (g_plan)** = an **annual** growth rate, applied as smooth monthly compounding within the year.
- Formula, for month number m = 1..12 of the year:
  `revenue_target_usd(m) = start_monthly_revenue × (1 + g_plan)^((m − 1)/12)`
  The monthly step is therefore (1 + g_plan)^(1/12) − 1 (about 0.33% for 4% annual). December is `start × (1 + g_plan)^(11/12)`, not `start × (1 + g_plan)`.
- `gross_profit_target_usd = revenue_target_usd × planned_gross_margin`. Both rounded to 2 decimals.
- **2025 start rule:** `start_2025 = start_2024 × (1 + g_plan_2024)`. This is a calendar continuity rule: January 2025 sits exactly one year after January 2024 on the same compounding path. It uses no actuals. Because of this rule, 2025 January is a continuation of the 2024 plan, and 2025 may have its own growth rate going forward.
- The same compounding convention is used for line-count growth in section 9.

| Market | Year | Jan revenue target (USD) (Proposed) | Annual plan growth (Proposed) | Planned gross margin (Proposed) |
|---|---|---|---|---|
| Thailand | 2024 | 65,000 | 4% | 29% |
| Thailand | 2025 | 67,600 (= 65,000 × 1.04) | 4% | 29% |
| Vietnam | 2024 | 40,000 | 18% | 28% |
| Vietnam | 2025 | 47,200 (= 40,000 × 1.18) | 15% | 28% |
| Indonesia | 2024 | 30,000 | 10% | 27% |
| Indonesia | 2025 | 33,000 (= 30,000 × 1.10) | 10% | 27% |

Comparability: targets and actuals use the same currency (USD), period (calendar month by sale_date), market (the customer's market), and gross profit definition (revenue minus COGS, no operating expenses). Targets exist only at market-month level; no customer or product targets are created.

### Pre-generation scale check (units and magnitude only)

Purpose: confirm that targets and expected sales are in the same unit and order of magnitude. It is **not** a way to set attainment levels, and no target is changed because of it.

Expected revenue per sales line (design assumptions only):
- Mean quantity per line ≈ median × e^(sigma²/2) = median × 1.083 → P01 ≈ 21.7, P02 ≈ 43.3, P03 ≈ 16.3 units.
- Revenue per line at base price ≈ P01 2,170; P02 2,600; P03 2,440 USD.
- Mix-weighted (40/35/25) ≈ 2,385 USD per line; special discounts (about 8% of lines, average depth 21%) lower this by about 1.7%, so ≈ 2,350 USD per line.

| Market | Jan 2024 base lines | Approx. expected revenue (lines × 2,350) | Jan 2024 target | Ratio (scale only) |
|---|---|---|---|---|
| Thailand | 28 | ≈ 65,800 | 65,000 | ≈ 1.01 |
| Vietnam | 18 | ≈ 42,300 | 40,000 | ≈ 1.06 |
| Indonesia | 13 | ≈ 30,600 | 30,000 | ≈ 1.02 |

Result: units (USD per month) and order of magnitude agree for all three markets. Note: the starting target values were chosen with these line-count assumptions in mind, so the ratios sit near 1; this was done to avoid a unit or scale mismatch, not to guarantee any attainment. Random demand factors, discounts, and the different plan and line growth rates (for example Thailand 4% vs 3%) mean actual attainment will vary and may be well above or below 100%. Whatever is generated is recorded and used as is.

## 11. Validation and results record

Integrity checks (from the brief): primary keys unique; foreign keys valid; required fields complete; quantity > 0; prices and costs ≥ 0; 72 target rows covering every market-month.

Generation checks:
- Normal (non-special) lines have price within ±8% of base (tolerance 0.005).
- Unit COGS within ±3% of base (tolerance 0.005).
- Line count, product mix, and market line counts are recorded.
- Top-5 customer revenue share is recorded (design aim 50–60%, not a pass/fail criterion).
- The low-margin measures in section 8 (special-discount share, below-20% share, customer-level margins, and the count and share of negative-gross-profit lines) are recorded separately.
- Revenue and gross profit totals by market and by customer reconcile to the overall totals.

After generation, a `docs/GENERATION_RESULTS.md` records the seed, Python version, row counts, and the actual measured values above, whether or not they match the design aims.

## 12. Limitations

- Prices, costs, volumes, and market behavior are learning assumptions, not estimates of any real business.
- Price variation here is not an estimate of price elasticity or demand response.
- The 20% margin line is a project example only.
- Targets are independent planning assumptions; attainment results are properties of this synthetic setup, not performance evidence.
