# Query Performance Analysis

### Query: SELECT TOP 2000000 * FROM dp03_catalogs_10yr.SSObject

Run 1

TABLEDATA Format

Memory spike: 500 MB
Result size: 2.9 GB
Query execution: 3m 4.37s
Parsing time: 4m 8.48s
Total time: ~7m 13s

BINARY Format

Memory spike: 500 MB
Result size: 617 MB
Query execution: 3m 8.61s
Parsing time: 5m 39.25s
Total time: ~8m 48s

--- 

Run 2

TABLEDATA Format

Query execution: 5m 39.42s
Parsing time: 4m 14.89s
Total time: ~9m 54s

BINARY Format

Query execution: 3m 27.75s
Parsing time: 5m 45.41s
Total time: ~9m 13s

--- 

Run 3

TABLEDATA Format

Query execution: 5m 31.39s
Parsing time: 4m 13.61s
Total time: ~9m 45s

BINARY Format

Query execution: 3m 51.33s
Parsing time: 5m 39.47s
Total time: ~9m 31s


--- 

## Summary Statistics

### TABLEDATA Format (Average across runs)

Query execution: 4m 45s

Parsing time: 4m 12s

Total time: ~8m 57s

Result size: 2.9 GB

### BINARY Format (Average across runs)

Query execution: 3m 29s

Parsing time: 5m 41s

Total time: ~9m 10s

Result size: 617 MB


## Key Observations

Binary format reduced result size by 79% (2.9 GB → 617 MB)

Binary format reduced query execution time by 27% on average (4m 45s → 3m 29s)

Binary format increased parsing time by 35% on average (4m 12s → 5m 41s)

Total end-to-end time is similar between formats (~9 minutes)

TABLEDATA shows more variable query execution times (3m 4s to 5m 39s) compared to BINARY (3m 9s to 3m 51s)
Peak memory usage is similar between formats (500 MB)
