# Explorative Analysis Report

## Executive Finding

The biggest profit lever is **discount control**, followed by shifting investment from Furniture toward Technology and Office Supplies. Geography matters, but much of the geographic loss appears connected to unprofitable product and discount combinations.

The dataset contains:

- **Sales:** $2.30M
- **Profit:** $286.4K
- **Overall profit margin:** 12.47%
- **Period:** 2014-2017

## Category Economics

| Category | Sales | Profit | Margin |
|---|---:|---:|---:|
| Technology | $836.2K | $145.5K | 17.40% |
| Office Supplies | $719.0K | $122.5K | 17.04% |
| Furniture | $742.0K | $18.5K | 2.49% |

Furniture generates almost as much revenue as Technology but only one-eighth of its profit. It consumes substantial sales capacity without producing a competitive return.

### Profit Trend

| Year | Technology | Office Supplies | Furniture |
|---:|---:|---:|---:|
| 2014 | $21.5K | $22.6K | $5.5K |
| 2015 | $33.5K | $25.1K | $3.0K |
| 2016 | $39.8K | $35.1K | $7.0K |
| 2017 | $50.7K | $39.7K | $3.0K |

Technology and Office Supplies show sustained growth. Furniture remains volatile and ends 2017 below its 2014 profit.

## Discount Problem

| Discount | Total Profit |
|---:|---:|
| 0% | $320.99K |
| 10% | $9.03K |
| 15% | $1.42K |
| 20% | $90.34K |
| 30% and above | **-$135.38K combined** |

Every aggregate discount level above 20% loses money.

The damage differs by category:

- Furniture loses **$54.5K** at discounts of 30% or more.
- Office Supplies loses **$47.1K** at its 70% and 80% discount levels.
- Technology loses **$34.1K** at discounts of 40%, 50%, and 70%.
- Technology's 30% discount is approximately break-even at only $326 profit.

**The first intervention should be eliminating or requiring approval for discounts above 20%.** The historical loss attached to those transactions is $135.4K, although removing discounts does not guarantee that all associated demand will remain.

## Product Portfolio

### Strongest Sub-Categories

| Sub-Category | Sales | Profit | Margin |
|---|---:|---:|---:|
| Copiers | $149.5K | $55.6K | 37.20% |
| Paper | $78.5K | $34.1K | 43.39% |
| Accessories | $167.4K | $41.9K | 25.05% |
| Phones | $330.0K | $44.5K | 13.49% |
| Binders | $203.4K | $30.2K | 14.86% |

Copiers, Paper, and Accessories combine strong margins with meaningful profit. Phones provide the largest sales base and remain solidly profitable.

### Weakest Sub-Categories

| Sub-Category | Sales | Profit | Margin |
|---|---:|---:|---:|
| Tables | $207.0K | -$17.7K | -8.56% |
| Bookcases | $114.9K | -$3.5K | -3.02% |
| Supplies | $46.7K | -$1.2K | -2.55% |
| Machines | $189.2K | $3.4K | 1.79% |

Tables are the clearest product-level problem: high revenue and the largest loss. Machines also tie up substantial revenue for almost no return.

The regional detail provides a more targeted response:

- Tables lose money in the East, South, and Central regions but earn **$1.5K** in the West.
- Bookcases lose money in the West, East, and Central regions but earn **$1.3K** in the South.
- Machines earn **$6.9K** in the East but lose money in every other region.
- Supplies lose money in the East and Central regions, are nearly flat in the South, and earn only $626 in the West.

This argues for regional pruning rather than automatically removing every weak sub-category nationwide.

## Geography

### Strongest States

- California: **$76.4K**
- New York: **$74.0K**
- Washington: **$33.4K**
- Michigan: **$24.5K**
- Virginia: **$18.6K**

### Weakest States

- Texas: **-$25.7K**
- Ohio: **-$17.0K**
- Pennsylvania: **-$15.6K**
- Illinois: **-$12.6K**
- North Carolina: **-$7.5K**

This supports the earlier city findings:

- New York City, Los Angeles, and Seattle are reliable expansion markets.
- Philadelphia loses money in all three categories.
- Houston and Chicago have serious Furniture and Office Supplies problems.
- Lancaster's Technology loss is part of Pennsylvania's wider underperformance.

### Region And Category

- West Office Supplies: **$52.6K**
- East Technology: **$47.5K**
- West Technology: **$44.3K**
- East Office Supplies: **$41.0K**
- Central Technology: **$33.7K**
- Central Furniture: **-$2.9K**

Central Furniture is the only unprofitable category-region combination.

## Other Dimensions

All customer segments are profitable:

- Consumer: $134.1K
- Corporate: $92.0K
- Home Office: $60.3K

All shipping modes are also profitable. Their approximate margins are similar, so shipping mode is not currently a major strategic problem.

## Recommended Actions

### Invest

- Technology and Office Supplies in New York City, Los Angeles, and Seattle.
- Office Supplies in the West.
- Technology in the East and Central regions.
- Copiers, Paper, Accessories, Phones, and Binders.
- Machines only in the East unless pricing improves elsewhere.

### Drop Or Restrict

- Discounts above 20% unless individually justified.
- Tables outside the West.
- Bookcases outside the South.
- Machines outside the East.
- Supplies in the East and Central regions.
- Central-region Furniture expansion.
- Philadelphia across all three categories.
- The worst offers in Texas, Ohio, Pennsylvania, and Illinois.

## Final Verdict

**Do not maximize profit by chasing more sales. Maximize it by protecting prices, expanding Technology and Office Supplies in proven markets, and removing region-product combinations that generate revenue without profit.**

The TinyBI analysis produced 25 managed charts covering cities, categories, discounts, sub-categories, regions, segments, states, shipping modes, sales, and yearly performance.
