using Google.OrTools.ConstraintSolver;
using RoutePlanner.Core.Configuration;

namespace RoutePlanner.Core.Routing;

public static class RouteOptimizer
{
    public static List<int> OptimizeVisitOrder(double[,] distanceMatrixM, PlannerOptions options, int startIndex = 0)
    {
        var n = distanceMatrixM.GetLength(0);
        if (n <= 1) return [];

        var useOrTools = options.Optimizer == OptimizerMode.OrTools && n <= options.MaxOrToolsNodes;
        if (!useOrTools) return NearestNeighborOrder(distanceMatrixM, startIndex);

        try
        {
            return OrToolsOpenTspOrder(distanceMatrixM, startIndex);
        }
        catch
        {
            return NearestNeighborOrder(distanceMatrixM, startIndex);
        }
    }

    private static List<int> NearestNeighborOrder(double[,] matrix, int startIndex)
    {
        var n = matrix.GetLength(0);
        var unvisited = Enumerable.Range(0, n).Where(i => i != startIndex).ToHashSet();
        var order = new List<int>();
        var current = startIndex;

        while (unvisited.Count > 0)
        {
            var next = unvisited.MinBy(j => matrix[current, j]);
            order.Add(next);
            unvisited.Remove(next);
            current = next;
        }

        return order;
    }

    private static List<int> OrToolsOpenTspOrder(double[,] matrix, int startIndex)
    {
        var n = matrix.GetLength(0);
        var indexMap = new List<int> { startIndex };
        indexMap.AddRange(Enumerable.Range(0, n).Where(i => i != startIndex));

        var m = indexMap.Count;
        var reindexed = new long[m, m];
        for (var i = 0; i < m; i++)
        for (var j = 0; j < m; j++)
            reindexed[i, j] = (long)Math.Round(matrix[indexMap[i], indexMap[j]]);

        var dummy = m;
        var augmented = new long[m + 1, m + 1];
        for (var i = 0; i < m; i++)
        for (var j = 0; j < m; j++)
            augmented[i, j] = reindexed[i, j];

        var manager = new RoutingIndexManager(m + 1, 1, new[] { 0 }, new[] { dummy });
        var routing = new RoutingModel(manager);

        var callback = routing.RegisterTransitCallback((fromIdx, toIdx) =>
        {
            var fromNode = manager.IndexToNode(fromIdx);
            var toNode = manager.IndexToNode(toIdx);
            return augmented[fromNode, toNode];
        });

        routing.SetArcCostEvaluatorOfAllVehicles(callback);

        var parameters = operations_research_constraint_solver.DefaultRoutingSearchParameters();
        parameters.FirstSolutionStrategy = FirstSolutionStrategy.Types.Value.PathCheapestArc;
        parameters.LocalSearchMetaheuristic = LocalSearchMetaheuristic.Types.Value.GuidedLocalSearch;
        parameters.TimeLimit = new Google.Protobuf.WellKnownTypes.Duration { Seconds = Math.Min(30, Math.Max(5, m / 2)) };

        var solution = routing.SolveWithParameters(parameters);
        if (solution is null) throw new InvalidOperationException("OR-Tools could not find a solution.");

        var orderReindexed = new List<int>();
        var index = routing.Start(0);
        while (!routing.IsEnd(index))
        {
            var node = manager.IndexToNode(index);
            if (node != 0 && node != dummy) orderReindexed.Add(node);
            index = solution.Value(routing.NextVar(index));
        }

        return orderReindexed.Select(i => indexMap[i]).ToList();
    }
}
