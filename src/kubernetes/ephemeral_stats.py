import subprocess
import json
from typing import List, Dict, Any, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - '
                                               '%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class KubernetesClient:
    """A client to interact with Kubernetes API.
    Uses kubectl cli through the subprocess lib"""

    @staticmethod
    def get_nodes() -> List[str]:
        """Fetch the list of node names in the Kubernetes cluster.

        Returns
        -------
        List[str]
            A list of node names.
        """
        try:
            result = subprocess.run(
                ["kubectl", "get", "nodes", "-o", "json"],
                capture_output=True,
                text=True,
                check=True
            )
            nodes = json.loads(result.stdout)
            return [node["metadata"]["name"] for node in nodes["items"]]
        except subprocess.CalledProcessError as e:
            logger.error(f"Error executing kubectl command: {e}")
            return []

    @staticmethod
    def get_node_summary(node_name: str) -> Optional[Dict[str, Any]]:
        """Fetch the summary stats for a specific node.

        Parameters
        ----------
        node_name
            The name of the node.

        Returns
        -------
        Optional[Dict[str, Any]]
            The node summary as a dictionary, or None if an error occurs.
        """
        try:
            result = subprocess.run(
                ["kubectl", "get", "--raw",
                 f"/api/v1/nodes/{node_name}/proxy/stats/summary"],
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error executing kubectl command "
                         f"for node {node_name}: {e}")
            return None


class EphemeralStorageAnalyzer:
    """Analyze ephemeral storage usage in a Kubernetes cluster."""

    def __init__(self, client: KubernetesClient):
        """
        Parameters
        ----------
        client
            An instance of KubernetesClient.
        """
        self.client = client

    @staticmethod
    def get_top_ephemeral_storage_pods(node_summary: Dict[str, Any],
                                       top_n: int = 5) -> List[Tuple[str,
    int]]:
        """Get the top N pods by ephemeral storage usage from the node summary.

        Parameters
        ----------
        node_summary
            The node summary data.
        top_n
            The number of top pods to retrieve. Defaults to 5.

        Returns
        -------
        List[Tuple[str, int]]
            A list of tuples containing pod names and their ephemeral
            storage usage.
        """
        pod_storage_usage = []

        if node_summary and "pods" in node_summary:
            for pod in node_summary["pods"]:
                pod_name = pod["podRef"]["name"]
                ephemeral_storage_used = pod["ephemeral-storage"][
                    "usedBytes"] if "ephemeral-storage" in pod else 0
                pod_storage_usage.append((pod_name, ephemeral_storage_used))

        pod_storage_usage.sort(key=lambda x: x[1], reverse=True)
        return pod_storage_usage[:top_n]

    def analyze_nodes(self, top_n: int = 5):
        """Analyze ephemeral storage usage for all nodes in the cluster."""
        nodes = self.client.get_nodes()
        if not nodes:
            logger.error("No nodes found or error retrieving nodes.")
            return
        logger.info(f"Top {top_n} Pods by Ephemeral Storage Usage on each node:")
        for node_name in nodes:
            logger.info(f"\nNode: {node_name}")
            node_summary = self.client.get_node_summary(node_name)

            if node_summary:
                top_pods = self.get_top_ephemeral_storage_pods(node_summary,
                                                               top_n=top_n)
                for pod_name, storage_used in top_pods:
                    logger.info(
                        f"Pod: {pod_name}, Ephemeral Storage Used: "
                        f"{storage_used / (1024 ** 3):.2f} GiB")
            else:
                logger.info(f"Failed to retrieve node summary for node "
                            f"{node_name}.")


def main():
    """Run the ephemeral storage analyzer."""
    client = KubernetesClient()
    analyzer = EphemeralStorageAnalyzer(client)
    analyzer.analyze_nodes(top_n=5)


if __name__ == "__main__":
    main()
