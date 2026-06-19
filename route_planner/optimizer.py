import logging

import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .config import PlannerConfig

logger = logging.getLogger(__name__)


def optimize_visit_order(
    distance_matrix_m: np.ndarray,
    config: PlannerConfig,
    start_index: int = 0,
) -> list[int]:
    """
    Return visit order as indices into distance_matrix (excluding start_index from output).
    distance_matrix includes start at start_index and all destinations.
    """
    n = distance_matrix_m.shape[0]
    if n <= 1:
        return []

    method = config.optimizer
    if method == "ortools" and n > config.max_ortools_nodes:
        logger.warning(
            "Node count %d exceeds max_ortools_nodes (%d); using nearest_neighbor.",
            n,
            config.max_ortools_nodes,
        )
        method = "nearest_neighbor"

    if method == "nearest_neighbor":
        return _nearest_neighbor_order(distance_matrix_m, start_index)

    try:
        return _ortools_open_tsp_order(distance_matrix_m, start_index)
    except Exception as exc:
        logger.warning("OR-Tools optimization failed (%s); falling back to nearest_neighbor.", exc)
        return _nearest_neighbor_order(distance_matrix_m, start_index)


def _nearest_neighbor_order(matrix: np.ndarray, start_index: int) -> list[int]:
    n = matrix.shape[0]
    unvisited = set(range(n)) - {start_index}
    order: list[int] = []
    current = start_index

    while unvisited:
        nxt = min(unvisited, key=lambda j: matrix[current, j])
        order.append(nxt)
        unvisited.remove(nxt)
        current = nxt

    return order


def _ortools_open_tsp_order(matrix: np.ndarray, start_index: int) -> list[int]:
    """
    Open TSP: start at start_index, visit all other nodes once, end anywhere.
    Implemented by adding a zero-cost dummy end node.
    """
    n = matrix.shape[0]
    int_matrix = np.rint(matrix).astype(np.int64)

    # Re-index so depot is 0 for OR-Tools
    index_map = [start_index] + [i for i in range(n) if i != start_index]
    reindexed = int_matrix[np.ix_(index_map, index_map)]

    m = reindexed.shape[0]
    dummy = m
    augmented = np.zeros((m + 1, m + 1), dtype=np.int64)
    augmented[:m, :m] = reindexed
    # Zero cost to dummy end from any node
    augmented[:m, dummy] = 0
    augmented[dummy, :] = 0

    manager = pywrapcp.RoutingIndexManager(m + 1, 1, [0], [dummy])
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(augmented[from_node, to_node])

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.FromSeconds(min(30, max(5, m // 2)))

    solution = routing.SolveWithParameters(search_params)
    if not solution:
        raise RuntimeError("OR-Tools could not find a solution.")

    order_reindexed: list[int] = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        if node != 0 and node != dummy:
            order_reindexed.append(node)
        index = solution.Value(routing.NextVar(index))

    # Map back to original indices (skip start_index in output)
    reverse_map = index_map
    return [reverse_map[i] for i in order_reindexed]
