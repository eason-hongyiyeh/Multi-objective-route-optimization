"""Yen's K shortest loopless paths；以 Dijkstra 求各條偏離路徑。

不重複的是搜尋狀態，不是實體站名。回傳至多 k 個 PathResult。
路徑以節點序列區分；適用於同節點對只有一條邊的路網。
"""
import heapq
from itertools import count

from dijkstra import Transition, ZERO_COST, dijkstra, path_result, prepare


def k_shortest_paths(graph, starts, goals, k=3):
    if not isinstance(k, int) or k < 1:
        raise ValueError('k 必須是正整數。')
    graph, starts, goals = prepare(graph, starts, goals)
    for edges in graph.values():
        if len({edge.target for edge in edges}) != len(edges):
            raise ValueError('Yen 路網不支援相同節點對的平行邊。')
    source, target = object(), object()
    augmented = dict(graph)
    augmented[source] = tuple(Transition(node, ZERO_COST) for node in starts)
    augmented[target] = ()
    for goal in goals:
        # 到達終點即停止，不將經過終點後的繞路算成另一條答案。
        augmented[goal] = (Transition(target, ZERO_COST),)
    first = dijkstra(augmented, [source], [target])
    if first is None:
        return []
    accepted, candidates = [first], []
    seen = {first.nodes}
    serial = count()
    while len(accepted) < k:
        previous = accepted[-1]
        for i in range(len(previous.nodes) - 1):
            root = previous.nodes[:i + 1]
            blocked_nodes = set(root[:-1])
            blocked_edges = {(path.nodes[i], path.nodes[i + 1]) for path in accepted
                             if len(path.nodes) > i + 1 and path.nodes[:i + 1] == root}
            pruned = {node: tuple(edge for edge in edges
                                 if edge.target not in blocked_nodes
                                 and (node, edge.target) not in blocked_edges)
                      for node, edges in augmented.items() if node not in blocked_nodes}
            spur = dijkstra(pruned, [root[-1]], [target])
            if spur is None:
                continue
            combined = path_result(root[:-1] + spur.nodes, previous.edges[:i] + spur.edges)
            if combined.nodes not in seen:
                seen.add(combined.nodes)
                heapq.heappush(candidates, (combined.cost, next(serial), combined))
        if not candidates:
            break
        accepted.append(heapq.heappop(candidates)[2])
    return [path_result(path.nodes[1:-1], path.edges[1:-1]) for path in accepted]
