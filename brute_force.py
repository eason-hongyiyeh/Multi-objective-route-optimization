"""DFS 窮舉簡單路徑，以分支限界剪枝，作為最短成本的對照組。

搜尋不呼叫其他最短路徑演算法，不快取各節點的最佳旅程成本。
每條路徑只禁止重複搜尋節點（捷運中為站碼與抵達方向的組合）。
成本非負，因此移除循環不會變差；累積成本加時間下界已不優於答案時
可安全剪枝。這是帶剪枝的窮舉，不會列出每一條完整路徑。
最壞情況仍需指數級搜尋，不適合大型密集路網。
"""
from collections import deque

from dijkstra import PathResult, ZERO_COST, prepare


def brute_force(graph, starts, goals):
    graph, starts, goals = prepare(graph, starts, goals)
    for source in starts:
        if source in goals:
            return PathResult((source,), (), ZERO_COST)

    # 反向 0–1 走訪：每條正時間邊記為 1，零時間邊記為 0。
    # 必經正時間邊數乘最小正秒數，是不高估的下界，並非真正最短時間。
    reverse = {node: [] for node in graph}
    positive = []
    for node, edges in graph.items():
        for edge in edges:
            reverse[edge.target].append((node, int(edge.cost[0] > 0)))
            if edge.cost[0] > 0:
                positive.append(edge.cost[0])
    minimum = min(positive, default=0)
    hops, pending = dict.fromkeys(goals, 0), deque(goals)
    while pending:
        current = pending.popleft()
        for node, weight in reverse[current]:
            candidate = hops[current] + weight
            if node not in hops or candidate < hops[node]:
                hops[node] = candidate
                (pending.append if weight else pending.appendleft)(node)
    lower_bound = {node: hops[node] * minimum for node in hops}
    # 只改變 DFS 分支順序，不直接採用其他演算法的答案。
    ordered = {node: tuple(sorted((edge for edge in edges if edge.target in hops),
                                 key=lambda edge: (hops[edge.target], edge.cost)))
               for node, edges in graph.items()}

    best = None
    for source in starts:
        if source not in hops:
            continue
        nodes, path_edges, visited = [source], [], {source}
        # 用堆疊代替遞迴，避免較長路徑超過 Python 的遞迴限制。
        stack = [(iter(ordered[source]), ZERO_COST)]
        while stack:
            outgoing, cost = stack[-1]
            edge = next(outgoing, None)
            if edge is None or (best is not None and cost >= best.cost):
                stack.pop()
                visited.remove(nodes.pop())
                if path_edges:
                    path_edges.pop()
                continue
            if edge.target in visited:
                continue
            candidate = (cost[0] + edge.cost[0], cost[1] + edge.cost[1],
                         cost[2] + edge.cost[2])
            bound = (candidate[0] + lower_bound[edge.target], candidate[1], candidate[2])
            if best is not None and bound >= best.cost:
                continue
            if edge.target in goals:
                best = PathResult(tuple(nodes) + (edge.target,),
                                  tuple(path_edges) + (edge,), candidate)
                continue
            visited.add(edge.target)
            nodes.append(edge.target)
            path_edges.append(edge)
            stack.append((iter(ordered[edge.target]), candidate))
    return best
