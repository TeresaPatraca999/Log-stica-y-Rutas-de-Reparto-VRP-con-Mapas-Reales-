import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from ga_vrp import genetic_algorithm, route_distance, route_load, split_routes
from map_utils import create_graph, get_distance_matrix, get_route_latlon


DEFAULT_DATA = "data/clientes.csv"
COLORS = [
    "red",
    "blue",
    "green",
    "purple",
    "orange",
    "darkred",
    "cadetblue",
    "darkgreen",
]


st.set_page_config(page_title="VRP con mapas reales", layout="wide")
st.title("VRP - Logistica y rutas de reparto")

st.sidebar.header("Vehiculos")
M = st.sidebar.number_input("Cantidad de vehiculos (M)", min_value=1, max_value=20, value=3)
Q = st.sidebar.number_input("Capacidad maxima por vehiculo (Q)", min_value=1, max_value=500, value=20)

st.sidebar.header("Punto de partida")
city = st.sidebar.text_input("Ciudad para el mapa real", "Ciudad Ixtepec, Oaxaca, Mexico")
depot_lat = st.sidebar.number_input("Latitud del deposito", value=16.560, format="%.6f")
depot_lon = st.sidebar.number_input("Longitud del deposito", value=-95.100, format="%.6f")

st.sidebar.header("Algoritmo genetico")
pop_size = st.sidebar.slider("Tamano de poblacion", 10, 300, 50, step=10)
generations = st.sidebar.slider("Numero de generaciones", 10, 700, 100, step=10)
mutation_rate = st.sidebar.slider("Tasa de mutacion", 0.0, 1.0, 0.10, step=0.01)


@st.cache_data
def load_default_data():
    return pd.read_csv(DEFAULT_DATA)


@st.cache_resource(show_spinner=False)
def load_graph(place):
    return create_graph(place)


def normalize_shipments(df):
    required = ["lat", "lon", "demanda"]
    df = df.copy()

    for column in required:
        if column not in df.columns:
            df[column] = 0.0

    df = df[required]
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["demanda"] = pd.to_numeric(df["demanda"], errors="coerce")
    df = df.dropna()
    df = df[df["demanda"] > 0]
    df = df.reset_index(drop=True)
    df.insert(0, "paquete", [f"P{i + 1}" for i in range(len(df))])

    return df


st.subheader("Gestion de envios")
uploaded_file = st.file_uploader("Sube un CSV con columnas: lat, lon, demanda", type=["csv"])

if uploaded_file:
    base_df = pd.read_csv(uploaded_file)
else:
    base_df = load_default_data()

edited_df = st.data_editor(
    normalize_shipments(base_df),
    num_rows="dynamic",
    width="stretch",
    column_config={
        "paquete": st.column_config.TextColumn("Paquete", disabled=True),
        "lat": st.column_config.NumberColumn("Latitud", format="%.6f"),
        "lon": st.column_config.NumberColumn("Longitud", format="%.6f"),
        "demanda": st.column_config.NumberColumn("Peso / demanda", min_value=0.0),
    },
)

shipments = normalize_shipments(edited_df)

left, right = st.columns([1, 1])
with left:
    run = st.button("Ejecutar Optimizacion", type="primary", width="stretch")

with right:
    st.metric("Paquetes cargados", len(shipments))


if run:
    if shipments.empty:
        st.error("Agrega al menos un paquete con latitud, longitud y demanda mayor a cero.")
        st.stop()

    if shipments["demanda"].max() > Q:
        st.warning("Hay paquetes que superan la capacidad de un vehiculo. La solucion sera penalizada.")

    depot = (depot_lon, depot_lat)
    client_coords = list(zip(shipments["lon"], shipments["lat"]))
    coords = [depot] + client_coords
    demands = [0] + shipments["demanda"].tolist()

    with st.spinner("Calculando distancias sobre calles reales..."):
        G = load_graph(city)
        dist_matrix, graph_nodes = get_distance_matrix(G, coords)

    with st.spinner("Ejecutando algoritmo genetico..."):
        best, cost, history = genetic_algorithm(
            dist_matrix,
            demands,
            Q,
            M,
            pop_size=pop_size,
            generations=generations,
            mutation_rate=mutation_rate,
        )

    routes = split_routes(best, demands, Q, M)
    feasible = len(routes) <= M and all(route_load(route, demands) <= Q for route in routes)

    st.success(f"Distancia total penalizada: {cost:,.2f} m")
    if feasible:
        st.info("La solucion respeta la cantidad de vehiculos y la capacidad maxima.")
    else:
        st.warning("La solucion tiene penalizacion por exceder vehiculos o capacidad.")

    map_center = [sum(lat for _, lat in coords) / len(coords), sum(lon for lon, _ in coords) / len(coords)]
    result_map = folium.Map(location=map_center, zoom_start=13)

    folium.Marker(
        location=[depot_lat, depot_lon],
        tooltip="Deposito",
        icon=folium.Icon(color="black", icon="home", prefix="fa"),
    ).add_to(result_map)

    for idx, row in shipments.iterrows():
        folium.Marker(
            location=[row["lat"], row["lon"]],
            tooltip=f"{row['paquete']} - demanda {row['demanda']}",
            icon=folium.Icon(color="gray", icon="box", prefix="fa"),
        ).add_to(result_map)

    summary_rows = []

    for vehicle_idx, route in enumerate(routes, start=1):
        color = COLORS[(vehicle_idx - 1) % len(COLORS)]
        route_points = get_route_latlon(G, graph_nodes, route)

        folium.PolyLine(
            route_points,
            color=color,
            weight=5,
            opacity=0.85,
            tooltip=f"Vehiculo {vehicle_idx}",
        ).add_to(result_map)

        package_ids = [shipments.iloc[node - 1]["paquete"] for node in route if node != 0]
        summary_rows.append(
            {
                "Vehiculo": vehicle_idx,
                "Paquetes": ", ".join(package_ids),
                "Carga total": route_load(route, demands),
                "Distancia (m)": round(route_distance(route, dist_matrix), 2),
                "Ruta": " -> ".join(["Deposito"] + package_ids + ["Deposito"]),
            }
        )

    st.subheader("Salida visual")
    st_folium(result_map, width=None, height=520)

    st.subheader("Resumen por vehiculo")
    st.dataframe(pd.DataFrame(summary_rows), width="stretch")

    st.subheader("Convergencia")
    convergence = pd.DataFrame(
        {"Generacion": range(1, len(history) + 1), "Mejor distancia penalizada": history}
    ).set_index("Generacion")
    st.line_chart(convergence)
else:
    preview_coords = [(depot_lon, depot_lat)] + list(zip(shipments["lon"], shipments["lat"]))
    center = [
        sum(lat for _, lat in preview_coords) / len(preview_coords),
        sum(lon for lon, _ in preview_coords) / len(preview_coords),
    ]
    preview_map = folium.Map(location=center, zoom_start=13)
    folium.Marker([depot_lat, depot_lon], tooltip="Deposito", icon=folium.Icon(color="black")).add_to(preview_map)

    for _, row in shipments.iterrows():
        folium.Marker([row["lat"], row["lon"]], tooltip=f"{row['paquete']} - demanda {row['demanda']}").add_to(preview_map)

    st.subheader("Vista previa del mapa")
    st_folium(preview_map, width=None, height=420)
