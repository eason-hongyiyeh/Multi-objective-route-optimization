"""A*：以反向 0–1 BFS 建立不高估時間的啟發式，不讀取捷運資料。"""
from collections import deque
import heapq
from itertools import count

from dijkstra import ZERO_COST, prepare, reconstruct


def time_lower_bounds(graph, goals):
    # 正時間邊至少花 min_positive 秒；零時間邊仍可免費通過。
    positive = [e.cost[0] for edges in graph.values() for e in edges if e.cost[0] > 0]
    minimum = min(positive, default=0)
    reverse = {node: [] for node in graph}
    for source, edges in graph.items():
        for edge in edges:
            reverse[edge.target].append((source, int(edge.cost[0] > 0)))
    bounds = dict.fromkeys(goals, 0)
    queue = deque(goals)
    while queue:
        node = queue.popleft()
        for previous, weight in reverse[node]:
            candidate = bounds[node] + weight
            if previous not in bounds or candidate < bounds[previous]:
                bounds[previous] = candidate
                (queue.append if weight else queue.appendleft)(previous)
    return {node: hops * minimum for node, hops in bounds.items()}


def astar(graph, starts, goals):
    graph, starts, goals = prepare(graph, starts, goals)
    heuristic = time_lower_bounds(graph, goals)
    best, parents, queue = {}, {}, []
    serial = count()
    for source in starts:
        if source in heuristic:
            best[source] = ZERO_COST
            heapq.heappush(queue, ((heuristic[source], 0, 0), next(serial), ZERO_COST, source))
    while queue:
        _, _, cost, current = heapq.heappop(queue)
        if best[current] != cost:
            continue
        if current in goals:
            return reconstruct(current, parents)
        for edge in graph[current]:
            if edge.target not in heuristic:
                continue
            candidate = tuple(a + b for a, b in zip(cost, edge.cost))
            if edge.target not in best or candidate < best[edge.target]:
                best[edge.target] = candidate
                parents[edge.target] = (current, edge)
                priority = (candidate[0] + heuristic[edge.target], *candidate[1:])
                heapq.heappush(queue, (priority, next(serial), candidate, edge.target))
    return None
