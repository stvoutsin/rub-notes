import os

import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Callable
from datetime import datetime


@dataclass
class Query:
    """A dataclass that represents a query run as UWS job and it's metadata."""
    job_id: str
    phase: str
    owner_id: str
    creation_time: datetime
    run_id: Optional[str] = None
    quote: Optional[datetime] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_duration: Optional[int] = None
    destruction: Optional[datetime] = None
    lang: Optional[str] = None
    query_text: Optional[str] = None
    error_message: Optional[str] = None

    def __str__(self) -> str:
        """Provides a string representation of the Query object.

        Returns
        -------
        str
            A string that describes the Query object.
        """
        start_time_str = self.start_time.strftime(
            '%Y-%m-%d %H:%M:%S') if self.start_time else 'N/A'
        query_preview = (
                    self.query_text[:50] + '...') if self.query_text and len(
            self.query_text) > 50 else self.query_text

        return (
            f"Query(job_id: {self.job_id}, phase: {self.phase}, start_time: {start_time_str})\n"
            f"Query text: {query_preview}")

    def __repr__(self) -> str:
        """Provides a detailed string representation of the Query object
        for debugging.

        Returns
        -------
        str
            A string that describes the Query object.
        """
        return self.__str__()


class QueryParser:
    """A helper class to parse XML responses from the query service.
    """

    namespace = {'uws': 'http://www.ivoa.net/xml/UWS/v1.0'}

    def parse_query_list(self, xml_content: bytes) -> List[Query]:
        """Parses a list of queries from the XML content.

        Parameters
        ----------
        xml_content : str
            The XML content to parse.

        Returns
        -------
        List[Query]
            A list of parsed Query objects.
        """
        root = ET.fromstring(xml_content)
        queries = []
        for job_ref in root.findall('.//uws:jobref', self.namespace):
            query = self.parse_query_element(job_ref)
            if query:
                queries.append(query)
        return queries

    def parse_query_element(self, job_ref: ET.Element) -> Optional[Query]:
        """Parses an XML element representing a query."""
        job_id = job_ref.attrib.get('id')
        if not job_id:
            return None

        phase_elem = job_ref.find('uws:phase', self.namespace)
        owner_id_elem = job_ref.find('uws:ownerId', self.namespace)
        creation_time_elem = job_ref.find('uws:creationTime', self.namespace)

        if phase_elem is None or owner_id_elem is None or creation_time_elem is None:
            return None

        creation_time = datetime.fromisoformat(creation_time_elem.text.rstrip('Z'))

        return Query(
            job_id=job_id,
            phase=phase_elem.text,
            owner_id=owner_id_elem.text,
            creation_time=creation_time,
        )

    def parse_query_details(self, xml_content: bytes) -> Query:
        """Parses detailed query information from an XML string.

        Parameters
        ----------
        xml_content : str
            The XML content to parse.

        Returns
        -------
        Query
            The Query object with detailed information.
        """
        root = ET.fromstring(xml_content)
        return Query(
            job_id=root.find('uws:jobId', self.namespace).text,
            phase=root.find('uws:phase', self.namespace).text,
            owner_id=root.find('uws:ownerId', self.namespace).text,
            creation_time=datetime.fromisoformat(root.find('uws:creationTime', self.namespace).text.rstrip('Z')),
            run_id=self._get_text(root, 'uws:runId'),
            quote=self._parse_datetime(root, 'uws:quote'),
            start_time=self._parse_datetime(root, 'uws:startTime'),
            end_time=self._parse_datetime(root, 'uws:endTime'),
            execution_duration=self._get_int(root, 'uws:executionDuration'),
            destruction=self._parse_datetime(root, 'uws:destruction'),
            lang=self._get_parameter(root, 'LANG'),
            query_text=self._get_parameter(root, 'QUERY'),
            error_message=self._get_error_message(root)
        )

    def _get_text(self, root: ET.Element, tag: str) -> Optional[str]:
        """Retrieves the text content of a specified XML tag."""
        element = root.find(tag, self.namespace)
        return element.text if element is not None else None

    def _parse_datetime(self, root: ET.Element, tag: str) -> Optional[datetime]:
        """Parses an ISO 8601 datetime string from a specified XML tag."""
        text = self._get_text(root, tag)
        return datetime.fromisoformat(text.rstrip('Z')) if text else None

    def _get_int(self, root: ET.Element, tag: str) -> Optional[int]:
        """Retrieves and converts text content of a specified XML tag to an integer."""
        text = self._get_text(root, tag)
        return int(text) if text else None

    def _get_parameter(self, root: ET.Element, param_id: str) -> Optional[str]:
        """Retrieves the text content of a specific parameter from the XML."""
        param = root.find(f".//uws:parameter[@id='{param_id}']", self.namespace)
        return param.text if param is not None else None

    def _get_error_message(self, root: ET.Element) -> Optional[str]:
        """Retrieves the error message from the XML if present."""
        error_summary = root.find('uws:errorSummary', self.namespace)
        if error_summary is not None:
            message = error_summary.find('uws:message', self.namespace)
            return message.text if message is not None else None
        return None


class QueryHistory:
    """A class to interact with the query history of a TAP service."""

    def __init__(self, parser: QueryParser, session: Optional[requests.Session] = None,
                 base_url: Optional[str] = None, token: Optional[str] = None):
        """Initializes the QueryHistory object with a session for making requests.
        Parameters
        ----------
        parser
            The QueryParser object to use for parsing query responses.
        session
            The requests session to use for making HTTP requests.
        base_url
            The base URL of the TAP service.
        token
            The token to use for authentication.

        Raises
        ------
        ValueError
            If base_url or token are not provided.
        """
        self.parser = parser
        self.base_url = base_url or os.getenv("TAP_BASE_URL", "")
        self.token = token or os.getenv("TOKEN", "")
        if not self.base_url or not self.token:
            raise ValueError("base_url and token must be provided.")

        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def get_queries(self, limit: Optional[int] = None, phase: Optional[str] = None,
                    recent: bool = True, filters: Optional[List[Callable[[Query], bool]]] = None) -> List[Query]:
        """Retrieves a list of queries with optional filtering by phase and ordering by recency.

        Parameters
        ----------
        limit
            The maximum number of queries to retrieve.
        phase
            The phase of the queries to filter by.
        recent
            Whether to order the queries by recency.
        filters
            A list of functions that take a Query object and return a boolean value.

        Returns
        -------
        List[Query]
            A list of Query objects that match the criteria.
        """
        jobs_url = f"{self.base_url}?PHASE={phase}" if phase else self.base_url
        response = self.session.get(jobs_url)
        response.raise_for_status()

        queries = self.parser.parse_query_list(xml_content=response.content)

        if recent:
            queries.sort(key=lambda q: q.creation_time, reverse=True)

        filtered_queries = []
        for query in queries:
            detailed_query = self.get_query_details(query.job_id)
            if filters and not all(f(detailed_query) for f in filters):
                continue
            filtered_queries.append(detailed_query)

        return filtered_queries[:limit] if limit else filtered_queries

    def get_query_details(self, job_id: str) -> Query:
        """Retrieves detailed information for a specific query."""
        job_url = f"{self.base_url}/{job_id}"
        response = self.session.get(job_url)
        response.raise_for_status()

        return self.parser.parse_query_details(response.content)

    def save_query(self, job_id: str) -> bool:
        """Saves a query by sending a PHASE=ARCHIVED request to the job endpoint.

        Parameters
        ----------
        job_id
            The ID of the job to be saved.

        Returns
        -------
        bool
            True if the job was successfully saved, False otherwise.
        """
        job_url = f"{self.base_url}/{job_id}"
        data = {"PHASE": "ARCHIVED"}

        try:
            response = self.session.post(job_url, data=data)
            response.raise_for_status()
            updated_query = self.get_query_details(job_id)
            return updated_query.phase == "ARCHIVED"

        except requests.RequestException as e:
            print(f"Error archiving job {job_id}: {e}")
            return False

    def run_query(self, job_id: str) -> None:
        """Runs a query by sending a PHASE=RUN request to the job endpoint.

        Parameters
        ----------
        job_id : str
            The ID of the job to be run.
        """
        job_url = f"{self.base_url}/{job_id}"
        data = {"PHASE": "RUN"}

        try:
            response = self.session.post(job_url, data=data)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error running job {job_id}: {e}")


if __name__ == "__main__":
    query_history = QueryHistory(
        parser=QueryParser(),
        base_url="https://data-dev.lsst.cloud/api/tap/async",
        token=""
    )
    queries = query_history.get_queries(recent=True)
    print(queries)

    """
    If we want to add filters:
    filters = [
        lambda q: q.owner_id == "username",
        lambda q: q.phase == "COMPLETED"
    ]
    queries = query_history.get_queries(limit=10, recent=True, filters=filters)
    """
