import csv
import os
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import folium

from ga_vrp import genetic_algorithm, route_distance, route_load, split_routes
from map_utils import (
    create_graph,
    get_direct_route_latlon,
    get_distance_matrix,
    get_national_distance_matrix,
    get_route_latlon,
    max_pair_distance_km,
)


DEFAULT_DATA = os.path.join("data", "clientes.csv")
NATIONAL_DATA = os.path.join("data", "clientes_nacional.csv")
MAP_OUTPUT = os.path.join("output", "vrp_routes.html")
COLORS = [
    "#e53935",
    "#00a6ff",
    "#43a047",
    "#8e24aa",
    "#fb8c00",
    "#d81b60",
    "#00897b",
    "#5d4037",
]


class VRPDesktopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VRP - Logistica y rutas de reparto")
        self.geometry("1240x780")
        self.minsize(1080, 680)

        self.shipments = []
        self.history = []
        self.map_path = None
        self.worker = None
        self.solution_text = tk.StringVar(value="Solucion: aun no calculada.")

        self._build_layout()
        self.load_default_shipments()

    def _build_layout(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(self, padding=12)
        sidebar.grid(row=0, column=0, sticky="ns")

        main = ttk.Frame(self, padding=12)
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)
        main.rowconfigure(3, weight=1)

        self._build_sidebar(sidebar)
        self._build_shipments(main)
        self._build_results(main)

    def _build_sidebar(self, parent):
        ttk.Label(parent, text="Datos del vehiculo", font=("Segoe UI", 11, "bold")).pack(anchor="w")

        self.vehicle_count = self._number_entry(parent, "Vehiculos disponibles (M)", "2")
        self.vehicle_capacity = self._number_entry(parent, "Capacidad maxima (Q)", "20")

        ttk.Separator(parent).pack(fill="x", pady=12)
        ttk.Label(parent, text="Punto de partida", font=("Segoe UI", 11, "bold")).pack(anchor="w")

        ttk.Label(parent, text="Ciudad del mapa real").pack(anchor="w", pady=(8, 0))
        self.city = ttk.Entry(parent, width=34)
        self.city.insert(0, "Oaxaca de Juarez, Oaxaca, Mexico")
        self.city.pack(fill="x")

        self.depot_lat = self._number_entry(parent, "Latitud del deposito", "17.060000")
        self.depot_lon = self._number_entry(parent, "Longitud del deposito", "-96.725000")
        ttk.Label(parent, text="Tipo de ruta").pack(anchor="w", pady=(8, 0))
        self.route_mode = ttk.Combobox(
            parent,
            values=["Nacional aproximado", "Local con calles OSMnx"],
            state="readonly",
            width=28,
        )
        self.route_mode.set("Local con calles OSMnx")
        self.route_mode.pack(fill="x")
        ttk.Label(
            parent,
            text="Local usa calles reales. Nacional usa aproximacion entre estados.",
            wraplength=250,
        ).pack(anchor="w", pady=(4, 0))

        ttk.Separator(parent).pack(fill="x", pady=12)
        ttk.Label(parent, text="Parametros del algoritmo", font=("Segoe UI", 11, "bold")).pack(anchor="w")

        self.population = self._scale(parent, "Tamano de poblacion", 10, 300, 50)
        self.generations = self._scale(parent, "Numero de generaciones", 10, 700, 100)
        self.mutation = self._scale(parent, "Tasa de mutacion (%)", 0, 100, 10)
        ttk.Label(parent, text="Cruza: OX para permutaciones").pack(anchor="w", pady=(6, 0))
        ttk.Label(parent, text="Mutacion: intercambio de dos paquetes").pack(anchor="w")

        ttk.Separator(parent).pack(fill="x", pady=12)
        self.run_button = ttk.Button(parent, text="Ejecutar Optimizacion", command=self.run_optimization)
        self.run_button.pack(fill="x", pady=(4, 8))

        self.open_map_button = ttk.Button(parent, text="Abrir mapa interactivo", command=self.open_map, state="disabled")
        self.open_map_button.pack(fill="x")

        self.status = tk.StringVar(value="Listo.")
        ttk.Label(parent, textvariable=self.status, wraplength=250).pack(anchor="w", pady=16)

    def _build_shipments(self, parent):
        top = ttk.Frame(parent)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        ttk.Label(top, text="Gestion de envios", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Button(top, text="Cargar CSV", command=self.load_csv).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(top, text="Guardar CSV", command=self.save_csv).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(top, text="Ejemplo nacional", command=self.load_national_example).grid(row=0, column=3, padx=(8, 0))

        table_frame = ttk.Frame(parent)
        table_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 12))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("paquete", "destino", "lat", "lon", "demanda")
        self.shipment_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
        for column, label, width in [
            ("paquete", "Paquete", 90),
            ("destino", "Destino", 180),
            ("lat", "Latitud", 140),
            ("lon", "Longitud", 140),
            ("demanda", "Peso / demanda", 140),
        ]:
            self.shipment_table.heading(column, text=label)
            self.shipment_table.column(column, width=width, anchor="center")

        self.shipment_table.grid(row=0, column=0, sticky="nsew")
        self.shipment_table.bind("<<TreeviewSelect>>", self.fill_form_from_selection)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.shipment_table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.shipment_table.configure(yscrollcommand=scrollbar.set)

        form = ttk.Frame(parent)
        form.grid(row=2, column=0, sticky="ew", pady=(0, 12))

        self.destination_entry = self._inline_entry(form, "Destino", 0, width=18)
        self.lat_entry = self._inline_entry(form, "Latitud", 2)
        self.lon_entry = self._inline_entry(form, "Longitud", 4)
        self.demand_entry = self._inline_entry(form, "Demanda", 6)
        ttk.Button(form, text="Agregar", command=self.add_shipment).grid(row=0, column=8, padx=(8, 0))
        ttk.Button(form, text="Actualizar", command=self.update_selected_shipment).grid(row=0, column=9, padx=(8, 0))
        ttk.Button(form, text="Eliminar", command=self.delete_selected_shipment).grid(row=0, column=10, padx=(8, 0))

    def _build_results(self, parent):
        results = ttk.Frame(parent)
        results.grid(row=3, column=0, sticky="nsew")
        results.columnconfigure(0, weight=2)
        results.columnconfigure(1, weight=1)
        results.rowconfigure(2, weight=1)

        ttk.Label(results, text="Resumen por vehiculo", font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(results, text="Convergencia", font=("Segoe UI", 13, "bold")).grid(row=0, column=1, sticky="w")

        ttk.Label(results, textvariable=self.solution_text, wraplength=760).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(6, 8)
        )

        summary_columns = ("vehiculo", "color", "paquetes", "carga", "distancia", "salida", "destino", "ruta")
        self.summary_table = ttk.Treeview(results, columns=summary_columns, show="headings", height=8)
        for column, label, width in [
            ("vehiculo", "Vehiculo", 80),
            ("color", "Color", 90),
            ("paquetes", "Paquetes", 180),
            ("carga", "Carga", 90),
            ("distancia", "Distancia", 120),
            ("salida", "Sale de", 110),
            ("destino", "Termina en", 110),
            ("ruta", "Ruta", 360),
        ]:
            self.summary_table.heading(column, text=label)
            self.summary_table.column(column, width=width, anchor="center")
        self.summary_table.grid(row=2, column=0, sticky="nsew", padx=(0, 12))

        self.chart = tk.Canvas(results, height=220, background="white", highlightthickness=1, highlightbackground="#cccccc")
        self.chart.grid(row=2, column=1, sticky="nsew")

    def _number_entry(self, parent, label, value):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(8, 0))
        entry = ttk.Entry(parent, width=18)
        entry.insert(0, value)
        entry.pack(fill="x")
        return entry

    def _scale(self, parent, label, start, end, value):
        variable = tk.IntVar(value=value)
        ttk.Label(parent, text=label).pack(anchor="w", pady=(8, 0))
        scale = ttk.Scale(parent, from_=start, to=end, variable=variable, orient="horizontal")
        scale.pack(fill="x")
        value_label = ttk.Label(parent, textvariable=variable)
        value_label.pack(anchor="e")
        return variable

    def _inline_entry(self, parent, label, column, width=14):
        ttk.Label(parent, text=label).grid(row=0, column=column, padx=(0, 4))
        entry = ttk.Entry(parent, width=width)
        entry.grid(row=0, column=column + 1)
        return entry

    def load_default_shipments(self):
        if os.path.exists(DEFAULT_DATA):
            self.shipments = self.read_shipments(DEFAULT_DATA)
            self.refresh_shipment_table()

    def load_national_example(self):
        if not os.path.exists(NATIONAL_DATA):
            messagebox.showerror("No encontrado", "No existe el archivo de ejemplo nacional.")
            return
        self.shipments = self.read_shipments(NATIONAL_DATA)
        self.city.delete(0, "end")
        self.city.insert(0, "Mexico")
        self.depot_lat.delete(0, "end")
        self.depot_lat.insert(0, "16.560000")
        self.depot_lon.delete(0, "end")
        self.depot_lon.insert(0, "-95.100000")
        self.route_mode.set("Nacional aproximado")
        self.refresh_shipment_table()
        self.status.set("Ejemplo nacional cargado. Usa aproximacion, no calles reales.")

    def read_shipments(self, path):
        rows = []
        with open(path, newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    rows.append(
                        {
                            "destino": row.get("destino") or row.get("Destino") or "",
                            "lat": float(row["lat"]),
                            "lon": float(row["lon"]),
                            "demanda": float(row["demanda"]),
                        }
                    )
                except (KeyError, TypeError, ValueError):
                    continue
        return rows

    def refresh_shipment_table(self):
        self.shipment_table.delete(*self.shipment_table.get_children())
        for index, row in enumerate(self.shipments, start=1):
            self.shipment_table.insert(
                "",
                "end",
                iid=str(index - 1),
                values=(
                    f"P{index}",
                    row.get("destino") or f"Destino {index}",
                    f"{row['lat']:.6f}",
                    f"{row['lon']:.6f}",
                    row["demanda"],
                ),
            )

    def load_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        self.shipments = self.read_shipments(path)
        self.refresh_shipment_table()
        self.status.set(f"CSV cargado: {len(self.shipments)} paquetes.")

    def save_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["destino", "lat", "lon", "demanda"])
            writer.writeheader()
            writer.writerows(self.shipments)
        self.status.set("CSV guardado.")

    def fill_form_from_selection(self, _event=None):
        selected = self.selected_index()
        if selected is None:
            return
        row = self.shipments[selected]
        self.destination_entry.delete(0, "end")
        self.destination_entry.insert(0, row.get("destino") or f"Destino {selected + 1}")
        self.lat_entry.delete(0, "end")
        self.lat_entry.insert(0, str(row["lat"]))
        self.lon_entry.delete(0, "end")
        self.lon_entry.insert(0, str(row["lon"]))
        self.demand_entry.delete(0, "end")
        self.demand_entry.insert(0, str(row["demanda"]))

    def selected_index(self):
        selection = self.shipment_table.selection()
        if not selection:
            return None
        return int(selection[0])

    def read_form_shipment(self):
        return {
            "destino": self.destination_entry.get().strip(),
            "lat": float(self.lat_entry.get()),
            "lon": float(self.lon_entry.get()),
            "demanda": float(self.demand_entry.get()),
        }

    def add_shipment(self):
        try:
            row = self.read_form_shipment()
        except ValueError:
            messagebox.showerror("Dato invalido", "Ingresa latitud, longitud y demanda numericas.")
            return
        if row["demanda"] <= 0:
            messagebox.showerror("Dato invalido", "La demanda debe ser mayor a cero.")
            return
        self.shipments.append(row)
        self.refresh_shipment_table()

    def update_selected_shipment(self):
        selected = self.selected_index()
        if selected is None:
            messagebox.showinfo("Seleccion requerida", "Selecciona un paquete de la tabla.")
            return
        try:
            row = self.read_form_shipment()
        except ValueError:
            messagebox.showerror("Dato invalido", "Ingresa latitud, longitud y demanda numericas.")
            return
        self.shipments[selected] = row
        self.refresh_shipment_table()

    def delete_selected_shipment(self):
        selected = self.selected_index()
        if selected is None:
            messagebox.showinfo("Seleccion requerida", "Selecciona un paquete de la tabla.")
            return
        del self.shipments[selected]
        self.refresh_shipment_table()

    def read_settings(self):
        return {
            "M": int(float(self.vehicle_count.get())),
            "Q": float(self.vehicle_capacity.get()),
            "city": self.city.get().strip(),
            "depot_lat": float(self.depot_lat.get()),
            "depot_lon": float(self.depot_lon.get()),
            "route_mode": self.route_mode.get(),
            "pop_size": int(self.population.get()),
            "generations": int(self.generations.get()),
            "mutation_rate": self.mutation.get() / 100,
        }

    def run_optimization(self):
        if self.worker and self.worker.is_alive():
            return
        if not self.shipments:
            messagebox.showerror("Sin paquetes", "Carga o agrega al menos un paquete.")
            return
        try:
            settings = self.read_settings()
        except ValueError:
            messagebox.showerror("Dato invalido", "Revisa vehiculos, capacidad y coordenadas del deposito.")
            return
        duplicate = self.package_at_depot(settings)
        if duplicate:
            messagebox.showerror(
                "Paquete en deposito",
                f"{duplicate} tiene la misma ubicacion que el deposito. Cambia sus coordenadas.",
            )
            return

        self.run_button.configure(state="disabled")
        self.open_map_button.configure(state="disabled")
        self.status.set("Calculando rutas...")
        self.solution_text.set("Solucion: calculando cromosoma y rutas...")
        self.summary_table.delete(*self.summary_table.get_children())
        self.chart.delete("all")

        data = [row.copy() for row in self.shipments]
        self.worker = threading.Thread(target=self._optimization_worker, args=(settings, data), daemon=True)
        self.worker.start()

    def package_at_depot(self, settings):
        tolerance = 0.000001
        for index, row in enumerate(self.shipments, start=1):
            same_lat = abs(row["lat"] - settings["depot_lat"]) <= tolerance
            same_lon = abs(row["lon"] - settings["depot_lon"]) <= tolerance
            if same_lat and same_lon:
                return f"P{index}"
        return None

    def _optimization_worker(self, settings, shipments):
        try:
            result = solve_vrp(settings, shipments)
        except Exception as exc:
            self.after(0, self._show_worker_error, exc)
            return
        self.after(0, self._show_result, result)

    def _show_worker_error(self, exc):
        self.run_button.configure(state="normal")
        self.status.set("No se pudo calcular la ruta.")
        messagebox.showerror("Error", str(exc))

    def _show_result(self, result):
        self.run_button.configure(state="normal")
        self.open_map_button.configure(state="normal")
        self.map_path = result["map_path"]
        self.history = result["history"]
        self.solution_text.set(result["solution_text"])

        for index, row in enumerate(result["summary"]):
            self.summary_table.insert(
                "",
                "end",
                values=(
                    row["vehiculo"],
                    row["color"],
                    row["paquetes"],
                    row["carga"],
                    row["distancia"],
                    row["salida"],
                    row["destino"],
                    row["ruta"],
                ),
            )

        self.draw_convergence(self.history)
        self.status.set(result["message"])
        self.open_map()

    def draw_convergence(self, history):
        self.chart.delete("all")
        width = max(self.chart.winfo_width(), 320)
        height = max(self.chart.winfo_height(), 220)
        pad = 30

        if not history:
            self.chart.create_text(width / 2, height / 2, text="Sin datos de convergencia")
            return

        min_y = min(history)
        max_y = max(history)
        span = max(max_y - min_y, 1)
        points = []
        for i, value in enumerate(history):
            x = pad + (width - 2 * pad) * i / max(len(history) - 1, 1)
            y = height - pad - (height - 2 * pad) * (value - min_y) / span
            points.append((x, y))

        self.chart.create_line(pad, height - pad, width - pad, height - pad, fill="#888888")
        self.chart.create_line(pad, pad, pad, height - pad, fill="#888888")
        for i in range(len(points) - 1):
            self.chart.create_line(*points[i], *points[i + 1], fill="#2563eb", width=2)
        self.chart.create_text(width / 2, 14, text="Mejor distancia por generacion")
        self.chart.create_text(pad, height - 12, text="1")
        self.chart.create_text(width - pad, height - 12, text=str(len(history)))

    def open_map(self):
        if self.map_path and os.path.exists(self.map_path):
            webbrowser.open(os.path.abspath(self.map_path))


def solve_vrp(settings, shipments):
    depot = (settings["depot_lon"], settings["depot_lat"])
    client_coords = [(row["lon"], row["lat"]) for row in shipments]
    coords = [depot] + client_coords
    demands = [0] + [row["demanda"] for row in shipments]
    is_national = settings["route_mode"].startswith("Nacional")

    if is_national:
        graph = None
        graph_nodes = None
        dist_matrix = get_national_distance_matrix(coords)
        distance_mode = "Nacional aproximado"
    else:
        span_km = max_pair_distance_km(coords)
        if span_km > 80:
            raise ValueError(
                "Los puntos estan muy separados para una red local de OSMnx. "
                "Usa puntos dentro de la misma ciudad/region o cambia a Nacional aproximado."
            )
        graph = create_graph(settings["city"])
        dist_matrix, graph_nodes = get_distance_matrix(graph, coords)
        distance_mode = "Local con calles OSMnx"

    best, cost, history = genetic_algorithm(
        dist_matrix,
        demands,
        settings["Q"],
        settings["M"],
        pop_size=settings["pop_size"],
        generations=settings["generations"],
        mutation_rate=settings["mutation_rate"],
    )
    routes = split_routes(best, demands, settings["Q"], settings["M"])

    summary = []
    for vehicle_idx, route in enumerate(routes, start=1):
        color = COLORS[(vehicle_idx - 1) % len(COLORS)]
        package_ids = [package_label(node, shipments) for node in route if node != 0]
        summary.append(
            {
                "vehiculo": vehicle_idx,
                "color": f"Ruta {vehicle_idx} ({color})",
                "paquetes": ", ".join(package_ids),
                "carga": route_load(route, demands),
                "distancia": format_distance(route_distance(route, dist_matrix)),
                "salida": "Deposito",
                "destino": "Deposito",
                "ruta": " -> ".join(["Deposito"] + package_ids + ["Deposito"]),
            }
        )

    map_path = build_map(settings, shipments, graph, graph_nodes, routes, coords, distance_mode)
    feasible = len(routes) <= settings["M"] and all(route_load(route, demands) <= settings["Q"] for route in routes)
    if feasible:
        message = f"Listo. Distancia total: {format_distance(cost)}. La solucion respeta capacidad y vehiculos."
    else:
        message = f"Listo. Distancia penalizada: {format_distance(cost)}. Hay penalizacion por capacidad o vehiculos."

    chromosome = " - ".join(package_label(node, shipments) for node in best)
    interpreted_routes = " | ".join(row["ruta"] for row in summary)
    solution_text = (
        f"Modo de distancia: {distance_mode}. Representacion: el cromosoma es una permutacion de paquetes, "
        f"[{chromosome}]. La solucion se obtiene partiendo esa permutacion por capacidad Q: "
        f"{interpreted_routes}. Todos los carros salen del Deposito y terminan en el Deposito."
    )

    return {
        "summary": summary,
        "history": history,
        "map_path": map_path,
        "message": message,
        "solution_text": solution_text,
    }


def package_label(node, shipments):
    destination = shipments[node - 1].get("destino") or f"Destino {node}"
    return f"P{node} {destination}"


def format_distance(meters):
    if meters >= 1000:
        return f"{meters / 1000:,.2f} km"
    return f"{meters:,.0f} m"


def build_map(settings, shipments, graph, graph_nodes, routes, coords, distance_mode):
    coords = [(settings["depot_lon"], settings["depot_lat"])] + [(row["lon"], row["lat"]) for row in shipments]
    center = [
        sum(lat for _, lat in coords) / len(coords),
        sum(lon for lon, _ in coords) / len(coords),
    ]
    zoom_start = 5 if distance_mode.startswith("Nacional") else 13
    result_map = folium.Map(location=center, zoom_start=zoom_start)

    folium.CircleMarker(
        [settings["depot_lat"], settings["depot_lon"]],
        radius=12,
        color="black",
        weight=3,
        fill=True,
        fill_color="yellow",
        fill_opacity=0.9,
        tooltip="DEPOSITO: origen y destino final de todos los vehiculos",
    ).add_to(result_map)
    folium.Marker(
        [settings["depot_lat"], settings["depot_lon"]],
        tooltip="DEPOSITO: origen y destino final",
        icon=folium.Icon(color="black", icon="home", prefix="fa"),
    ).add_to(result_map)

    for index, row in enumerate(shipments, start=1):
        label = row.get("destino") or f"Destino {index}"
        folium.Marker(
            [row["lat"], row["lon"]],
            tooltip=f"P{index} {label} - ubicacion exacta - demanda {row['demanda']}",
            icon=folium.Icon(color="gray", icon="box", prefix="fa"),
        ).add_to(result_map)

    for vehicle_idx, route in enumerate(routes, start=1):
        color = COLORS[(vehicle_idx - 1) % len(COLORS)]
        if graph is None:
            route_points = get_direct_route_latlon(route, coords)
        else:
            route_points = get_route_latlon(graph, graph_nodes, route, coords)
        folium.PolyLine(
            route_points,
            color="white",
            weight=9,
            opacity=0.95,
        ).add_to(result_map)
        folium.PolyLine(
            route_points,
            color=color,
            weight=6,
            opacity=1,
            tooltip=f"Vehiculo {vehicle_idx}: sale del Deposito y regresa al Deposito",
        ).add_to(result_map)
        add_route_stop_markers(result_map, shipments, route, color, vehicle_idx)

    add_map_legend(result_map, routes)
    fit_map_to_points(result_map, coords)
    os.makedirs(os.path.dirname(MAP_OUTPUT), exist_ok=True)
    result_map.save(MAP_OUTPUT)
    return os.path.abspath(MAP_OUTPUT)


def fit_map_to_points(result_map, coords):
    lats = [lat for _lon, lat in coords]
    lons = [lon for lon, _lat in coords]
    result_map.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(30, 30))


def add_route_stop_markers(result_map, shipments, route, color, vehicle_idx):
    stop_number = 1
    for node in route:
        if node == 0:
            continue

        row = shipments[node - 1]
        destination = row.get("destino") or f"Destino {node}"
        folium.CircleMarker(
            [row["lat"], row["lon"]],
            radius=8,
            color="white",
            weight=3,
            fill=True,
            fill_color=color,
            fill_opacity=1,
            tooltip=f"Vehiculo {vehicle_idx}, parada {stop_number}: P{node} {destination}",
        ).add_to(result_map)
        folium.Marker(
            [row["lat"], row["lon"]],
            icon=folium.DivIcon(
                html=f"""
                <div style="
                    font-size: 11px;
                    font-weight: 700;
                    color: #111;
                    background: white;
                    border: 1px solid #333;
                    border-radius: 10px;
                    padding: 1px 5px;
                    transform: translate(8px, -8px);
                    white-space: nowrap;
                ">V{vehicle_idx}.{stop_number}</div>
                """
            ),
        ).add_to(result_map)
        stop_number += 1


def add_map_legend(result_map, routes):
    rows = []
    for vehicle_idx, _route in enumerate(routes, start=1):
        color = COLORS[(vehicle_idx - 1) % len(COLORS)]
        rows.append(
            f"""
            <div style="display:flex;align-items:center;gap:8px;margin:4px 0;">
                <span style="width:16px;height:16px;background:{color};display:inline-block;border:1px solid #333;"></span>
                <span>Vehiculo {vehicle_idx}: Deposito -> entregas -> Deposito</span>
            </div>
            """
        )

    legend = f"""
    <div style="
        position: fixed;
        bottom: 30px;
        left: 30px;
        z-index: 9999;
        background: white;
        padding: 12px 14px;
        border: 2px solid #333;
        border-radius: 6px;
        font-size: 13px;
        box-shadow: 0 2px 8px rgba(0,0,0,.25);
    ">
        <div style="font-weight: 700; margin-bottom: 6px;">Leyenda de rutas</div>
        <div style="display:flex;align-items:center;gap:8px;margin:4px 0;">
            <span style="width:16px;height:16px;background:yellow;display:inline-block;border:2px solid #000;"></span>
            <span>Deposito: salida y destino final</span>
        </div>
        {''.join(rows)}
    </div>
    """
    result_map.get_root().html.add_child(folium.Element(legend))


if __name__ == "__main__":
    app = VRPDesktopApp()
    app.mainloop()
