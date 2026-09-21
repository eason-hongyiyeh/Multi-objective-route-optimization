"""BFS：最少搜尋邊數（行車邊與轉乘邊各算一條），不保證時間最短。"""
from collections import deque

from dijkstra import prepare, reconstruct


def bfs(graph, starts, goals):
    graph, starts, goals = prepare(graph, starts, goals)
    queue, seen, parents = deque(starts), set(starts), {}
    while queue:
        current = queue.popleft()
        if current in goals:
            return reconstruct(current, parents)
        for edge in graph[current]:
            if edge.target not in seen:
                seen.add(edge.target)
                parents[edge.target] = (current, edge)
                queue.append(edge.target)
    return None
