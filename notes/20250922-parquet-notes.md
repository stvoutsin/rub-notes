## VOParquet in qserv-kafka


Feature:
Support generating VOParquet output https://www.ivoa.net/documents/Notes/VOParquet/ from the qserv-kafka bridge.
Requirements:
- End-to-end performance close to what we have with the binary2 VOTable encoder
- Memory usage needs to be somewhat bounded / steady
- Support large queries (up to the QServ limit)


## Challenges

- Parquet is a column-oriented format which present a challenge during writing compared to row-oriented formats like VOTable or CSV in that metadata, statistics, indeces need to be collected in memory during writing and these are used to write the parquet footer which includes such information and allows clients to easily navigate columns/row-groups when reading.

The VOTable encoder processes data in a memory-efficient row-by-row manner, where each row is processed and yielded to the http client.

- The idea of VOParquet as output for a TAP query implies that the goal is to return a single Parquet file, so we cannot split the output into many files. If this was possible, it would allow us to free the memory used for part/file when it is done, so the memory footprint would be much smaller.


## Parquet

The Parquet format itself is written in row groups containing columnar data pages with embedded statistics and compression. PyArrow handles the complex columnar reorganization internally, so our row batches get transformed from Python dictionaries into Arrows columnar representation, then compressed and encoded into Parquet's binary format. 
Each row group contains complete column chunks with their own metadata, page indices, and compression dictionaries.

The VOParquet specification extends Parquet by embedding a VOTable file (just the metadata, no data) in the footer metadata of the Parquet file using specific keys. This preserves the VOTable column metadata as well as other metadata resources such as the datalink resources for example or INFO elements related to the query and it's execution.


## Architecture

### Overall design

Since we have to write in the column oriented way with row groups, streaming row-by-row is not feasible. However the approach I went with processes the results in batches of size: 2000 and writes these as individual row groups, thus avoiding loading full datasets into memory. Each batch is converted to an Arrow RecordBatch before writing. This allows us to match a batch size to a row-group because it gives us control over PyArrow's memory usage and write patterns. 

By setting row_group_size=2000 to match our batch size, we force PyArrow to write each batch as a complete row group rather than accumulating multiple batches internally, which prevents PyArrow from buffering large amounts of data while waiting to reach its default row group thresholds (64MB+). 

The 1:1 batch-to-row-group mapping ensures predictable memory behavior, each 2K batch gets processed, written to the buffer, and immediately becomes available for HTTP streaming. 

I settled on 2000 as the batch size through trial and error, and based on recommendations from forum resources. Initially I went with higher numbers, but ended-up with OOM pods kills.
2000 seems to strike the right balance between performance, memory accumulation of metadata needed per row group and memory footprint.

While this uses more memory than the streaming row-by-row approach of the VOTable binary2 encoder it is better than loading all the data in memory and produces a footprint of about ~0.5-1KB per row.



### Streaming buffer

There is a missmatch between how PyArrow writes data (expects file-like object) compared to what our http client expects which is an async iterator that yields bytes.

The solution follows a suggestion here:
https://stackoverflow.com/questions/64791558/create-parquet-files-from-stream-in-python-in-memory-efficient-manner

And creates a adapter between these two so that:

- PyArrow writes: buffer.write(parquet_chunk)
- Buffer stores data
- buffer.flush_buffer() returns accumulated bytes
- HTTP client takes yielded bytes and sends via PUT


### Metadata

VOParquet expects the footer to include the VOTable header/footer without the data element, so this required a change to the TAP service to send a slightly modified envelope in the case of parquet as the requested output format. The modification is basically just to not include the <DATA> & <TABLE> elements.
So the parquet writes takes the VOTable envelope as input and writes it to the parquet footer.


## Tradeoffs
 
- More complex implementation
Due to the challenges of needing to bridge pyarrow writer and http client & the complexities of how such a format needs to be written out the implementation is more complex than the VOTable encoder

- Memory usage
As described this leads to increased memory usage during writing, which becomes more prevelant during large queries to wide columns. Note that to handle the largest query from the benchmarks below, I had to increase the memory request limit to 500MB, otherwise the pods would OOM. This does seem however to be close to the limit of what QServ supports as well, as requesting more rows than that produced a QServ memory error (going from 200k to 300k rows).

 

## Testing

### Large queries

Memory profiling showed the implementation successfully batched data through without retention of the full data in memory.
I observed about a 15-25% memory-to-output ratio.

Breakdown of tested queries:
Note (Memory increase is Memory before - Memory immediately after query is complete)


SELECT TOP 10 * FROM dp02_dc2_catalogs.Object

Result Size: 700 KB
Peak Memory: 213 MB
Memory Increase: 10 MB
Job execution runtime: 10 seconds

For comparison the VOTable (binary2) version ran in 10 seconds and resulted in a file of size 250KB


SELECT TOP 10000 * FROM dp02_dc2_catalogs.Object
Result Size: 35 MB
Peak Memory: 176 MB
Memory Increase: 8 MB
Job execution runtime: 25 seconds

For comparison the VOTable (binary2) version ran in 25 seconds and resulted in a file of size 60MB


SELECT TOP 100000 * FROM dp02_dc2_catalogs.Object
Result Size: 360 MB 
Peak Memory: 295 MB
Memory Increase: 120 MB
Job execution runtime: 185 seconds

For comparison the VOTable (binary2) version ran in 194 seconds and resulted in a file of size 600MB


SELECT TOP 200000 * FROM dp02_dc2_catalogs.Object
Result Size: 722 MB 
Peak Memory: 346 MB
Memory Increase: 180 MB
Job execution runtime: 247 seconds

For comparison the VOTable (binary2) version ran in 374 seconds and resulted in a file of size 1.2 GB


Selecting >= 300k rows results in a QServ error (with both Parquet and binary2 VOTable):

Query results are too large to return; please narrow your query and try again: MERGE_ERROR 1470 (QI=5566616:298; cancelling the query, queryResult table result_5566616_m is too large at 3820317973 bytes, max allowed size is 3145728000 bytes) 2025-09-19T17:45:26+0000


## Benchmark Comparison 

In terms of performance, they seem to be comparable, with the VOParquet job serialization completing slightly faster in the case of the 200k rows. 
However this has not been run enough times to rule out external factors and other queries that may affect the performance in order to give a definitive conclusion on how they compare.

Regarding result size apart from the short query (10) we see close to a 40% reduction in output size.

Memory usage on the other hand is much worse in the case of the VOParquet encoder, which in the case of the binary2 VOTable is steady due to the streaming serialization.
 	

### Testing with TopCat

I've tested compatibility with VO Tools by loading results from these queries into TopCast, then exporting the data from TopCat as a VOTable, then finally doing the same with our normal binary2 encoded VOTables and comparing the output from the two. This showed consistent metadata (columns types) and data between the two.


## Current problems 

I've also noticed that in the current implementation and on a fresh deploy, upon running the 200k query the memory usage settles to around +30 to +50 MB from the baseline it was before running the query. This could be an indication of something not being properly cleaned up, though I haven't been able to track this down. However if I repeat these large-result-set queries the baseline does seem to settle at the same point after the spikes during processing.


## Links


- https://stackoverflow.com/questions/64791558/create-parquet-files-from-stream-in-python-in-memory-efficient-manner
- https://stackoverflow.com/questions/53016802/memory-leak-from-pyarrow
- https://stackoverflow.com/questions/63891231/pyarrow-incrementally-using-parquetwriter-without-keeping-entire-dataset-in-mem
- https://issues.apache.org/jira/browse/ARROW-10052
- https://github.com/apache/arrow/issues/2624
- https://stackoverflow.com/questions/68819790/read-write-parquet-files-without-reading-into-memory-using-python
- https://github.com/apache/arrow/issues/44472
- https://stackoverflow.com/questions/65885183/pyarrow-parquet-write-table-memory-usage
- https://arrow.apache.org/docs/python/memory.html
- https://stackoverflow.com/questions/79694182/memory-not-released-after-each-request-despite-cleanup-attempts
- https://stackoverflow.com/questions/56472727/difference-between-apache-parquet-and-arrow
- https://jorisvandenbossche.github.io/arrow-docs-preview/html-option-1/cpp/parquet.html
