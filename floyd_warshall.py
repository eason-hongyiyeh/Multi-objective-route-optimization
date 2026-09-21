"""Floyd–Warshall：每次呼叫計算所有節點對的最短路徑，O(V³)。"""
from dijkstra import cost_encoder, path_result, prepare


def floyd_warshall(graph, starts, goals):
    graph, starts, goals = prepare(graph, starts, goals)
    nodes = list(graph)
    indices = {node: i for i, node in enumerate(nodes)}
    size = len(nodes)
    infinity = float('inf')
    distances = [[infinity] * size for _ in nodes]
    next_edge = [[None] * size for _ in nodes]
    encode = cost_encoder(graph)
    for node, edges in graph.items():
        i = indices[node]
        distances[i][i] = 0
        for edge in edges:
            j, weight = indices[edge.target], encode(edge.cost)
            if weight < distances[i][j]:
                distances[i][j] = weight
                next_edge[i][j] = edge
    for k in range(size):
        row_k = distances[k]
        reachable = [(j, distance) for j, distance in enumerate(row_k) if distance != infinity]
        for i in range(size):
            row_i = distances[i]
            via = row_i[k]
            if via == infinity:
                continue
            first = next_edge[i][k]
            for j, remainder in reachable:
                candidate = via + remainder
                if candidate < row_i[j]:
                    row_i[j] = candidate
                    next_edge[i][j] = first
    pairs = ((indices[s], indices[g]) for s in starts for g in nodes if g in goals)
    source, target = min(pairs, key=lambda pair: distances[pair[0]][pair[1]])
    if distances[source][target] == infinity:
        return None
    path, edges = [nodes[source]], []
    while source != target:
        edge = next_edge[source][target]
        edges.append(edge)
        path.append(edge.target)
        source = indices[edge.target]
    return path_result(path, edges)
