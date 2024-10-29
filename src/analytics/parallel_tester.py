"""Parallel Request Testing module"""
import asyncio
import logging
import time
from statistics import mean, stdev
from typing import List, Dict, Optional
import click
import httpx

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


class ParallelRequestTester:
    def __init__(self, num_users: int, api_url: str, timeout: float = 30.0,
                 auth_token: Optional[str] = None):
        """Initializes the ParallelRequestTester.

        Parameters
        ----------
        num_users
            Number of concurrent users to simulate.
        api_url
            The API endpoint to test.
        timeout
            Maximum time to wait for each request (default is 30.0 seconds).
        auth_token
            Optional authentication token to include in the request headers.
        """
        self.num_users = num_users
        self.api_url = api_url
        self.timeout = timeout
        self.auth_token = auth_token

    async def _make_request(self, user_id: int) -> Dict[str, float]:
        """Makes a single asynchronous GET request to the API endpoint.

        Parameters
        ----------
        user_id
            The ID of the user making the request.

        Returns
        -------
        Dict[str, float]
            A dictionary with the user ID, status code, response time,
            and error message (if any).
        """
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            start_time = time.monotonic()
            try:
                response = await client.get(self.api_url, headers=headers)
                end_time = time.monotonic()
                response_time = end_time - start_time
                return {
                    "user_id": user_id,
                    "status_code": response.status_code,
                    "response_time": response_time,
                }
            except httpx.RequestError as exc:
                end_time = time.monotonic()
                response_time = end_time - start_time
                return {
                    "user_id": user_id,
                    "status_code": None,
                    "response_time": response_time,
                    "error": str(exc),
                }

    async def run_tests(self) -> List[Dict[str, float]]:
        """Executes the requests in parallel for all users.

        Returns
        -------
        List[Dict[str, float]]
            A list of response data for each user.
        """
        tasks = [
            self._make_request(user_id)
            for user_id in range(1, self.num_users + 1)
        ]
        return await asyncio.gather(*tasks)

    def analyze_results(self, results: List[Dict[str, float]]) -> None:
        """Analyzes the results of the parallel requests.

        Parameters
        ----------
        results
            A list of response data for each user.
        """
        times = [result["response_time"] for result in results]
        average_time = mean(times)
        std_dev_time = stdev(times) if len(times) > 1 else 0
        success_count = sum(
            1 for result in results if result["status_code"] == 200
        )

        logging.info(f"Total Users: {self.num_users}")
        logging.info(
            f"Average Response Time per Request: {average_time:.2f} seconds"
        )
        logging.info(
            f"Standard Deviation of Response Times: {std_dev_time:.2f} seconds"
        )
        logging.info(
            f"Number of Successful Requests: {success_count} / "
            f"{self.num_users}"
        )

        logging.info("\nDetailed User Response Times:")
        for result in results:
            logging.info(
                f"User {result['user_id']}: Status Code "
                f"{result['status_code']}, "
                f"Response Time {result['response_time']:.2f} seconds"
            )

    def run(self) -> None:
        """Executes the test and analyzes the results."""
        logging.info("Starting the parallel request test...")
        start_time = time.monotonic()
        results = asyncio.run(self.run_tests())
        end_time = time.monotonic()

        logging.info(
            f"\nTest Completed in {end_time - start_time:.2f} seconds"
        )
        self.analyze_results(results)


@click.command()
@click.option(
    "--num-users",
    default=10,
    show_default=True,
    help="Number of concurrent users to simulate.",
)
@click.option(
    "--api-url",
    default="https://data-dev.lsst.cloud/api/sia/dp02/query?"
            "POS=CIRCLE+55.7467+-32.2862+0.05&time=60550.31803461111+"
            "60550.3183818287",
    show_default=True,
    help="API endpoint to test.",
)
@click.option(
    "--timeout",
    default=30.0,
    show_default=True,
    help="Timeout for each request in seconds.",
)
@click.option(
    "--token",
    default=None,
    help="Authentication token to include in the request headers.",
)
def main(num_users: int, api_url: str, timeout: float,
         token: Optional[str]):
    """CLI tool to test parallel requests to a specified API endpoint."""
    tester = ParallelRequestTester(
        num_users=num_users, api_url=api_url, timeout=timeout,
        auth_token=token
    )
    tester.run()


if __name__ == "__main__":
    main()
