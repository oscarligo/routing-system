"""Decode zero-based MiniZinc successor arrays without trusting cached routes."""


def routes_from_successors(successor: list[list[int]], used: list[bool]) -> list[list[int]]:
    if not successor or len(successor) != len(used):
        raise ValueError("Successor rows and vehicle flags must have equal nonzero length")
    size = len(successor[0])
    routes, visited = [], []
    for row, active in zip(successor, used):
        if size < 2 or len(row) != size or type(active) is not bool or any(
            type(node) is not int or not 0 <= node < size for node in row
        ):
            raise ValueError("Invalid successor indices or vehicle flags")
        route = [0]
        if active:
            current = row[0]
            while current != 0:
                if current in route:
                    raise ValueError("Invalid successor cycle: route does not return to depot")
                route.append(current)
                current = row[current]
            if len(route) == 1:
                raise ValueError("Active vehicle must visit a customer")
            visited.extend(route[1:])
            route.append(0)
        included = set(route) if active else set()
        if any(row[i] != i for i in range(size) if i not in included):
            raise ValueError("Successor contains a disconnected cycle or an inactive vehicle route")
        routes.append(route)
    if sorted(visited) != list(range(1, size)):
        raise ValueError("Every customer must be visited exactly once")
    return routes
