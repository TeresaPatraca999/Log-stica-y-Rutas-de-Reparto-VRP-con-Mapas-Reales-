import random


BIG_PENALTY = 1_000_000


def route_load(route, demands):
    return sum(demands[node] for node in route if node != 0)


def route_distance(route, dist_matrix):
    return sum(dist_matrix[route[i]][route[i + 1]] for i in range(len(route) - 1))


def split_routes(solution, demands, Q, M=None):
    routes = []
    route = [0]
    load = 0

    for client in solution:
        demand = demands[client]

        if route != [0] and load + demand > Q:
            route.append(0)
            routes.append(route)
            route = [0]
            load = 0

        route.append(client)
        load += demand

    route.append(0)
    routes.append(route)

    return routes


def fitness(solution, dist_matrix, demands, Q, M):
    total_distance = 0
    penalty = 0
    routes = split_routes(solution, demands, Q, M)

    if len(routes) > M:
        penalty += BIG_PENALTY * (len(routes) - M)

    for route in routes:
        load = route_load(route, demands)
        total_distance += route_distance(route, dist_matrix)

        if load > Q:
            penalty += BIG_PENALTY * (load - Q)

    return total_distance + penalty


def genetic_algorithm(
    dist_matrix,
    demands,
    Q,
    M,
    pop_size=50,
    generations=100,
    mutation_rate=0.1,
):
    n = len(demands)
    clients = list(range(1, n))

    if not clients:
        return [], 0, []

    population = [random.sample(clients, len(clients)) for _ in range(pop_size)]
    best_solution = None
    best_cost = float("inf")
    history = []

    elite_size = max(2, min(10, pop_size // 5))
    parent_pool_size = max(2, min(20, pop_size))

    for _ in range(generations):
        population.sort(key=lambda x: fitness(x, dist_matrix, demands, Q, M))
        current_cost = fitness(population[0], dist_matrix, demands, Q, M)

        if current_cost < best_cost:
            best_solution = population[0][:]
            best_cost = current_cost

        history.append(best_cost)
        new_population = [candidate[:] for candidate in population[:elite_size]]

        while len(new_population) < pop_size:
            p1, p2 = random.sample(population[:parent_pool_size], 2)#torneo
            child = crossover(p1, p2)
            child = mutate(child, mutation_rate)
            new_population.append(child)

        population = new_population

    return best_solution, best_cost, history


def crossover(p1, p2):
    return order_crossover(p1, p2)


def order_crossover(p1, p2):
    """OX: keeps a segment from p1 and completes the permutation in p2 order."""
    if len(p1) < 2:
        return p1[:]

    start = random.randint(0, len(p1) - 2)
    end = random.randint(start + 1, len(p1) - 1)
    child = [None] * len(p1)
    child[start : end + 1] = p1[start : end + 1]

    p2_index = (end + 1) % len(p2)
    child_index = (end + 1) % len(child)

    while None in child:
        candidate = p2[p2_index]
        if candidate not in child:
            child[child_index] = candidate
            child_index = (child_index + 1) % len(child)
        p2_index = (p2_index + 1) % len(p2)

    return child


def mutate(solution, mutation_rate):#como se llama
    sol = solution[:]

    if len(sol) >= 2 and random.random() < mutation_rate:
        i, j = random.sample(range(len(sol)), 2)
        sol[i], sol[j] = sol[j], sol[i]

    return sol
