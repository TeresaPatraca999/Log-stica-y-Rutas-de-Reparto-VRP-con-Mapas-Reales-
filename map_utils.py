import networkx as nx
import osmnx as ox
from math import asin, cos, radians, sin, sqrt


def create_graph(place="Ciudad Ixtepec, Oaxaca, Mexico"):
    return ox.graph_from_place(place, network_type="drive")


def nearest_graph_nodes(G, coords):
    graph_points = [(node, data["x"], data["y"]) for node, data in G.nodes(data=True)]
    return [nearest_node_bruteforce(graph_points, lon, lat) for lon, lat in coords]


def nearest_node_bruteforce(graph_points, lon, lat):
    return min(
        graph_points,
        key=lambda item: haversine_distance(lon, lat, item[1], item[2]),
    )[0]


def haversine_distance(lon1, lat1, lon2, lat2):
    radius_m = 6_371_000
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * radius_m * asin(sqrt(a))


def get_distance_matrix(G, coords):
    nodes = nearest_graph_nodes(G, coords)
    connector_distances = [
        distance_to_node(G, coord, node) for coord, node in zip(coords, nodes)
    ]
    n = len(nodes)
    dist_matrix = [[0] * n for _ in range(n)]

    for i in range(n):
        lengths = nx.single_source_dijkstra_path_length(G, nodes[i], weight="length")

        for j in range(n):
            if i != j:
                street_distance = lengths.get(nodes[j], 1_000_000_000)
                dist_matrix[i][j] = connector_distances[i] + street_distance + connector_distances[j]

    return dist_matrix, nodes


def get_national_distance_matrix(coords, road_factor=1.25):
    n = len(coords)
    dist_matrix = [[0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i != j:
                lon1, lat1 = coords[i]
                lon2, lat2 = coords[j]
                dist_matrix[i][j] = haversine_distance(lon1, lat1, lon2, lat2) * road_factor

    return dist_matrix


def get_direct_route_latlon(route, coords):
    return [coord_to_latlon(coords[node]) for node in route]


def max_pair_distance_km(coords):
    max_distance = 0
    for i, origin in enumerate(coords):
        for destination in coords[i + 1 :]:
            max_distance = max(
                max_distance,
                haversine_distance(origin[0], origin[1], destination[0], destination[1]) / 1000,
            )
    return max_distance


def distance_to_node(G, coord, node):
    lon, lat = coord
    node_lon = G.nodes[node]["x"]
    node_lat = G.nodes[node]["y"]
    return haversine_distance(lon, lat, node_lon, node_lat)


def get_route_latlon(G, graph_nodes, route, coords=None):
    full_path = []

    for i in range(len(route) - 1):
        origin = graph_nodes[route[i]]
        destination = graph_nodes[route[i + 1]]

        try:
            path = nx.shortest_path(G, origin, destination, weight="length")
        except nx.NetworkXNoPath:
            path = [origin, destination]

        if full_path:
            path = path[1:]

        full_path.extend(path)

    street_points = [(G.nodes[node]["y"], G.nodes[node]["x"]) for node in full_path]

    if not coords or not route:
        return street_points

    precise_points = []
    for i in range(len(route) - 1):
        origin_index = route[i]
        destination_index = route[i + 1]
        origin_exact = coord_to_latlon(coords[origin_index])
        destination_exact = coord_to_latlon(coords[destination_index])
        origin_node = graph_nodes[origin_index]
        destination_node = graph_nodes[destination_index]

        try:
            path = nx.shortest_path(G, origin_node, destination_node, weight="length")
        except nx.NetworkXNoPath:
            path = [origin_node, destination_node]

        segment = [origin_exact]
        segment.extend((G.nodes[node]["y"], G.nodes[node]["x"]) for node in path)
        segment.append(destination_exact)

        if precise_points:
            segment = segment[1:]

        precise_points.extend(segment)

    return precise_points


def coord_to_latlon(coord):
    lon, lat = coord
    return lat, lon
