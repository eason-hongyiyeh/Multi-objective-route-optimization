"""純路徑搜尋演算法；不讀 CSV、不處理捷運規則，也不操作終端機。

共同介面：search(graph, starts, goals) -> PathResult 或 None。
graph 為「節點 -> Transition 列表」；節點可為任何可雜湊的物件。
成本是三個非負整數，以字典順序比較；捷運程式傳入
（總秒數、換車次數、行駛路段數），因此以時間最短優先。
新增演算法時沿用相同介面與成本，便能公平比較結果。
"""
from dataclasses import dataclass
import heapq
from itertools import count
from typing import Hashable, Iterable, Mapping, Optional, Tuple


Cost = Tuple[int, int, int]
ZERO_COST: Cost = (0, 0, 0)


@dataclass(frozen=True)
class Transition:
    target: Hashable
    cost: Cost
    data: object = None  # 呼叫端的路段資料；搜尋只使用 target 與 cost。


@dataclass(frozen=True)
class PathResult:
    nodes: Tuple[Hashable, ...]
    edges: Tuple[Transition, ...]
    cost: Cost


def prepare(graph, starts, goals):
    """共用輸入驗證；固定 iterator，保留節點順序。"""
    starts = tuple(dict.fromkeys(starts))
    goals = set(goals)
    if not starts or not goals:
        raise ValueError('搜尋至少需要一個起點與終點。')
    if any(node not in graph for node in starts) or any(node not in graph for node in goals):
        raise ValueError('搜尋起點或終點不存在於路網。')
    # 固定鄰接資料，也允許呼叫端提供一次性的 iterator。
    adjacency = {node: tuple(edges) for node, edges in graph.items()}
    for edges in adjacency.values():
        for edge in edges:
            if edge.target not in adjacency:
                raise ValueError('路段指向不存在的節點。')
            if len(edge.cost) != 3 or any(not isinstance(v, int) or v < 0 for v in edge.cost):
                raise ValueError('成本須為三個非負整數。')
    return adjacency, starts, goals


def path_result(nodes, edges):
    edges = tuple(edges)
    return PathResult(tuple(nodes), edges,
                      tuple(sum(edge.cost[i] for edge in edges) for i in range(3)))


def reconstruct(current, parents):
    nodes, edges = [current], []
    while current in parents:
        current, edge = parents[current]
        nodes.append(current)
        edges.append(edge)
    return path_result(reversed(nodes), reversed(edges))


def cost_encoder(graph):
    """將字典序成本轉為整數；任何簡單路徑的低位總和都不會進位。"""
    edges = [edge for items in graph.values() for edge in items]
    n = len(graph)
    base = n * max((e.cost[2] for e in edges), default=0) + 1
    time_unit = (n * max((e.cost[1] for e in edges), default=0) + 1) * base
    return lambda cost: cost[0] * time_unit + cost[1] * base + cost[2]


def dijkstra(
    graph: Mapping[Hashable, Iterable[Transition]],
    starts: Iterable[Hashable],
    goals: Iterable[Hashable],
) -> Optional[PathResult]:
    """多起點、多終點 Dijkstra；無法到達時回傳 None，成本不得為負。"""
    adjacency, starts, goals = prepare(graph, starts, goals)

    best, parents, queue = {}, {}, []
    serial = count()  # 同成本時不比較節點本身，節點不需支援排序。
    for source in starts:
        best[source] = ZERO_COST
        heapq.heappush(queue, (ZERO_COST, next(serial), source))
    while queue:
        cost, _, current = heapq.heappop(queue)
        if best[current] != cost:
            continue
        if current in goals:
            return reconstruct(current, parents)
        for edge in adjacency[current]:
            candidate = tuple(a + b for a, b in zip(cost, edge.cost))
            if edge.target not in best or candidate < best[edge.target]:
                best[edge.target] = candidate
                parents[edge.target] = (current, edge)
                heapq.heappush(queue, (candidate, next(serial), edge.target))
    return None
