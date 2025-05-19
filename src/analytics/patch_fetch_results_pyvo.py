# Patch the fetch_result method in astropy to get detailed timing breakdown

def patch_tap_timing():
    """
    Patches the AsyncTAPJob.fetch_result method
    """
    original_fetch_result = AsyncTAPJob.fetch_result

    def timed_fetch_result(self):
        timing = [0.0]  # [http_read_time]

        try:
            connect_start = time.time()
            response = self._session.get(self.result_uri, stream=True)
            response.raise_for_status()
            connect_end = time.time()
            connect_time = connect_end - connect_start
            print(f"Connection setup time: {connect_time:.4f} seconds")

            original_read = response.raw.read

            def timed_read(*args, **kwargs):
                # When this is called, it's fetching data from the network
                start_time = time.time()
                data = original_read(*args, **kwargs)
                end_time = time.time()
                timing[0] += (end_time - start_time)
                return data

            response.raw.read = timed_read
            response.raw.read = functools.partial(response.raw.read, decode_content=True)

            parse_start = time.time()
            try:
                result = TAPResults(votableparse(response.raw.read),
                                    url=self.result_uri,
                                    session=self._session)
            except UnicodeDecodeError as e:
                print(f"Unicode error during parsing: {str(e)}")
                print("Falling back to non-streaming approach...")
                response = self._session.get(self.result_uri, stream=False)
                response.raise_for_status()
                result = TAPResults(votableparse(response.content),
                                    url=self.result_uri,
                                    session=self._session)
            except Exception as e:
                print(f"Error during parsing: {type(e).__name__}: {str(e)}")
                raise

            parse_end = time.time()

            http_read_time = timing[0]
            total_parse_time = parse_end - parse_start
            pure_parse_time = total_parse_time - http_read_time

            # Print detailed timing breakdown
            print(f"HTTP data transfer time: {http_read_time:.4f} seconds")
            print(f"Pure XML parsing time: {pure_parse_time:.4f} seconds")
            print(f"Total processing time: {total_parse_time:.4f} seconds")
            total_time = connect_time + total_parse_time
            print(f"Total execution time: {total_time:.4f} seconds")
            print(f"Connection setup: {connect_time/total_time*100:.1f}%")
            print(f"HTTP data transfer: {http_read_time/total_time*100:.1f}%")
            print(f"XML parsing: {pure_parse_time/total_time*100:.1f}%")

            return result

        except requests.RequestException as ex:
            self._update()
            self.raise_if_error()
            raise DALServiceError.from_except(ex, self.url)

    AsyncTAPJob.fetch_result = timed_fetch_result

    return original_fetch_result


def run_timed_tap_query(tap_service, query, **kwargs):
    """
    Runs a TAP query with timing measurements
  
    """
    original_method = patch_tap_timing()

    try:
        print(f"Running query: {query}")
        start_time = time.time()
        result = tap_service.run_async(query, **kwargs)
        end_time = time.time()
        print(f"Total wall clock time: {end_time - start_time:.4f} seconds")
        return result
    finally:
        AsyncTAPJob.fetch_result = original_method
