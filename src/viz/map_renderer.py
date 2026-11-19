"""Render solver successors on the original directed OSM graph with Folium."""

import hashlib
import json
import math
from html import escape
from pathlib import Path

import folium
import networkx as nx
import osmnx as ox

from ..solver.routes import routes_from_successors

COLORS = ("#b45309", "#146bba", "#a63778", "#17775d", "#7957b5", "#b93832", "#526a24", "#426575")
ROOT = Path(__file__).resolve().parents[2]


def _label(value: object) -> str:
    # Folium embeds popup/tooltip HTML in JavaScript template literals.
    return escape(str(value)).replace("`", "&#96;").replace("$", "&#36;")


def road_leg(graph: nx.MultiDiGraph, paths: dict, source: int, target: int) -> dict:
    """Use the same single-source Dijkstra and parallel-edge choice as the builder."""
    if source not in paths:
        paths[source] = nx.single_source_dijkstra(graph, source, weight="travel_time")
    seconds, node_paths = paths[source]
    if target not in node_paths:
        raise ValueError(f"No directed road path: {source} -> {target}")
    coordinates, streets, length = [], [], 0
    node_path = node_paths[target]
    for u, v in zip(node_path, node_path[1:]):
        key, edge = min(graph[u][v].items(), key=lambda item: (item[1]["travel_time"], item[1]["length"]))
        geometry = edge.get("geometry")
        points = list(geometry.coords) if geometry is not None else [
            (graph.nodes[u]["x"], graph.nodes[u]["y"]), (graph.nodes[v]["x"], graph.nodes[v]["y"])
        ]
        start = (graph.nodes[u]["x"], graph.nodes[u]["y"])
        if math.dist(points[-1], start) < math.dist(points[0], start):
            points.reverse()
        locations = [(lat, lon) for lon, lat in points]
        coordinates.extend(locations if not coordinates else locations[1:])
        streets.append({"u": u, "v": v, "key": key, "name": str(edge.get("name", "Calle sin nombre")),
                        "oneway": bool(edge.get("oneway", False)), "coordinates": locations})
        length += edge["length"]
    if not coordinates:
        coordinates = [(graph.nodes[source]["y"], graph.nodes[source]["x"])]
    return {"coordinates": coordinates, "streets": streets, "osm_path": node_path,
            "distance_m": math.ceil(length), "minutes": math.ceil(seconds[target] / 60)}


def build_plan(graph: nx.MultiDiGraph, data: dict, geo: dict, solution: dict) -> dict:
    """Validate a core solution and reconstruct a concrete, feasible visit schedule."""
    if not solution.get("has_solution"):
        raise ValueError("Cannot render a solver result without a feasible solution")
    if not graph.is_directed() or str(graph.graph.get("crs", "")).upper() != "EPSG:4326":
        raise ValueError("Expected the original directed EPSG:4326 graph")
    routes = routes_from_successors(solution["successor"], solution["used"])
    if len(routes) != data["n_vehicles"] or len(geo["nodes"]) != data["n_customers"] + 1:
        raise ValueError("Instance, geography and vehicle dimensions do not match")
    if len(solution["successor"][0]) != len(geo["nodes"]):
        raise ValueError("Successor dimensions do not match the instance")
    if [node["model_index"] for node in geo["nodes"]] != list(range(len(geo["nodes"]))):
        raise ValueError("Geography nodes must follow the model's zero-based order")
    vehicles, paths, objective = [], {}, 0
    for k, route in enumerate(routes):
        vehicle = {"number": k + 1, "active": solution["used"][k], "route": route,
                   "color": COLORS[k] if k < len(COLORS) else f"hsl({k * 137.508 % 360:.2f},65%,38%)",
                   "legs": [], "stops": []}
        vehicles.append(vehicle)
        if not vehicle["active"]:
            if any(solution[key][k] != 0 for key in ("loading_start", "departure", "return_time")):
                raise ValueError("Inactive vehicle has nonzero depot times")
            continue
        load = sum(data["demand"][i] for i in route)
        start, departure = solution["loading_start"][k], solution["departure"][k]
        if load > data["capacity"][k]:
            raise ValueError(f"Vehicle {k + 1} exceeds capacity")
        if not (data["earliest"][0] <= start and departure == start + data["loading_duration"][k]):
            raise ValueError(f"Vehicle {k + 1} has invalid loading/departure times")
        previous_end = departure
        for order, (i, j) in enumerate(zip(route, route[1:]), 1):
            leg = road_leg(graph, paths, geo["nodes"][i]["osm_node"], geo["nodes"][j]["osm_node"])
            if leg["distance_m"] != data["distance"][i][j] or leg["minutes"] != data["travel_time"][i][j]:
                raise ValueError(f"Road path does not match instance matrices: {i} -> {j}")
            leg.update(source=i, target=j, order=order)
            vehicle["legs"].append(leg)
            arrival = previous_end + leg["minutes"]
            if j == 0:
                if not arrival <= solution["return_time"][k] <= data["latest"][0]:
                    raise ValueError(f"Vehicle {k + 1} returns outside the depot window")
                vehicle["arrival_depot"] = arrival
                continue
            service = solution["start_service"][j - 1]
            if not (arrival <= service and data["earliest"][j] <= service <= data["latest"][j]):
                raise ValueError(f"Customer {j} violates travel precedence or service window")
            vehicle["stops"].append({"index": j, "id": str(geo["nodes"][j]["id"]), "order": order,
                                     "arrival": arrival, "service": service, "waiting": service - arrival,
                                     "earliest": data["earliest"][j], "latest": data["latest"][j]})
            previous_end = service + data["service"][j]
        distance = sum(leg["distance_m"] for leg in vehicle["legs"])
        vehicle.update(load=load, capacity=data["capacity"][k], loading_start=start, departure=departure,
                       distance_m=distance)
        objective += data["fixed_cost"][k] + data["distance_cost"][k] * distance
    if objective != solution["total_cost"]:
        raise ValueError("Reconstructed objective does not match the solver")

    # cumulative supplies capacity, not dock ids: color intervals into feasible lanes.
    dock_ends = [0] * data["n_docks"]
    intervals = []
    for vehicle in sorted((v for v in vehicles if v["active"]), key=lambda v: (v["loading_start"], v["number"])):
        dock = next((i for i, end in enumerate(dock_ends) if end <= vehicle["loading_start"]), None)
        if dock is None:
            raise ValueError("Loading intervals exceed depot dock capacity")
        dock_ends[dock] = vehicle["departure"]
        intervals.append({"dock": dock + 1, "vehicle": vehicle["number"], "color": vehicle["color"],
                          "start": vehicle["loading_start"], "end": vehicle["departure"]})
    events = sorted([(i["start"], 1) for i in intervals] + [(i["end"], -1) for i in intervals])
    occupancy, peak = 0, 0
    for _, delta in events:
        occupancy += delta
        peak = max(peak, occupancy)
    return {"vehicles": vehicles, "docks": intervals, "peak_docks": peak, "total_cost": objective}


def clock(minutes: int, start_minutes: int) -> str:
    total = start_minutes + minutes
    days, remainder = divmod(total, 1440)
    return f"{remainder // 60:02d}:{remainder % 60:02d}" + (f" (+{days}d)" if days else "")


def make_map(graph: nx.MultiDiGraph, data: dict, geo: dict, solution: dict, *, start_time: str = "08:00") -> folium.Map:
    try:
        hours, minutes = map(int, start_time.split(":"))
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError("start_time must be HH:MM, between 00:00 and 23:59") from None
    origin = hours * 60 + minutes
    time = lambda value: clock(value, origin)
    plan = build_plan(graph, data, geo, solution)
    depot = geo["nodes"][0]
    m = folium.Map(location=[depot["snapped_lat"], depot["snapped_lon"]], zoom_start=15,
                   tiles=None, control_scale=True)
    # A local road background stays usable when external tile services are unavailable.
    features = []
    for u, v, edge in graph.edges(data=True):
        geometry = edge.get("geometry")
        coordinates = list(geometry.coords) if geometry is not None else [
            (graph.nodes[u]["x"], graph.nodes[u]["y"]), (graph.nodes[v]["x"], graph.nodes[v]["y"])
        ]
        features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coordinates},
                         "properties": {"Calle": _label(edge.get("name", "Calle sin nombre")),
                                        "Sentido": "Único" if edge.get("oneway", False) else "Doble"}})
    folium.GeoJson({"type": "FeatureCollection", "features": features},
                   name="Calles guardadas", overlay=False,
                   style_function=lambda feature: {"color": "#aebbc7", "weight": 2, "opacity": .65},
                   tooltip=folium.GeoJsonTooltip(fields=["Calle", "Sentido"]),
                   attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>').add_to(m)
    bounds, cards = [], []
    for vehicle in plan["vehicles"]:
        number, color = vehicle["number"], vehicle["color"]
        if not vehicle["active"]:
            cards.append(f'<div class="inactive">V{number} · Inactivo</div>')
            continue
        group = folium.FeatureGroup(name=f"Vehículo {number} · {len(vehicle['stops'])} visitas").add_to(m)
        for leg in vehicle["legs"]:
            label = f"V{number} · Tramo {leg['order']}: {leg['source']} → {leg['target']} · {leg['minutes']} min"
            if len(leg["coordinates"]) > 1:
                folium.PolyLine(leg["coordinates"], color=color, weight=5, opacity=.85,
                                tooltip=label, smooth_factor=0).add_to(group)
            bounds.extend(leg["coordinates"])
            for street in leg["streets"]:
                coordinates = street["coordinates"]
                a, b = coordinates[(len(coordinates) - 1) // 2:(len(coordinates) - 1) // 2 + 2]
                angle = -math.degrees(math.atan2(b[0] - a[0], (b[1] - a[1]) * math.cos(math.radians(a[0]))))
                street_label = _label(f"{street['name']} · {'Vía de un sentido' if street['oneway'] else 'Doble sentido'} · OSM {street['u']} → {street['v']}")
                folium.Marker([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2],
                    icon=folium.DivIcon(icon_size=(18, 18), icon_anchor=(9, 9),
                        html=f'<div class="road-arrow" style="color:{color};transform:rotate({angle}deg)">➤</div>'),
                    tooltip=folium.Tooltip(street_label)).add_to(group)
        rows = []
        for stop in vehicle["stops"]:
            node = geo["nodes"][stop["index"]]
            window = f"{time(stop['earliest'])}–{time(stop['latest'])}"
            popup = (f"<b>V{number} · Visita {stop['order']} · {_label(stop['id'])}</b><br>"
                     f"Llegada estimada: {time(stop['arrival'])}<br>Inicio de servicio: {time(stop['service'])}<br>"
                     f"Ventana: {window}<br>Espera: {stop['waiting']} min<br><b>Servicio dentro de ventana ✓</b>")
            folium.Marker([node["snapped_lat"], node["snapped_lon"]],
                z_index_offset=1000,
                icon=folium.DivIcon(icon_size=(40, 26), icon_anchor=(20, 13),
                    html=f'<div class="stop" style="background:{color}">V{number}·{stop["order"]}</div>'),
                tooltip=f"{_label(stop['id'])} · Servicio {time(stop['service'])}",
                popup=folium.Popup(popup, max_width=330)).add_to(group)
            rows.append(f'<tr><td><b>{stop["order"]}. {_label(stop["id"])}</b><small>Espera {stop["waiting"]} min</small></td>'
                        f'<td>{time(stop["arrival"])}</td><td><b>{time(stop["service"])}</b><small>{window}</small></td></tr>')
        cards.append(f'<details class="vehicle" open><summary><span class="dot" style="background:{color}"></span>'
                     f'Vehículo {number}<span class="distance">{vehicle["distance_m"] / 1000:.2f} km</span></summary>'
                     f'<p>{len(vehicle["stops"])} visitas · Carga {vehicle["load"]}/{vehicle["capacity"]} · '
                     f'Salida {time(vehicle["departure"])} · Regreso {time(vehicle["arrival_depot"])}</p>'
                     '<table><thead><tr><th>Visita</th><th>Llegada</th><th>Servicio / ventana</th></tr></thead>'
                     f'<tbody>{"".join(rows)}</tbody></table></details>')

    dock_rows, depot_rows = [], []
    scale = max((interval["end"] for interval in plan["docks"]), default=1)
    for dock in range(1, data["n_docks"] + 1):
        bars = []
        for interval in (item for item in plan["docks"] if item["dock"] == dock):
            text = f'V{interval["vehicle"]} · {time(interval["start"])}–{time(interval["end"])}'
            bars.append(f'<div class="bar" title="{text}" style="left:{100 * interval["start"] / scale:.3f}%;'
                        f'width:{100 * (interval["end"] - interval["start"]) / scale:.3f}%;background:{interval["color"]}">'
                        f'V{interval["vehicle"]}</div>')
            depot_rows.append(f'<div>{text} · Muelle {dock}</div>')
        dock_rows.append(f'<div class="dock-row"><span>M{dock}</span><div class="track">{"".join(bars)}</div></div>')
    depot_html = '<b>Depósito · Muelles de carga</b>' + ''.join(depot_rows)
    folium.Marker([depot["snapped_lat"], depot["snapped_lon"]],
        z_index_offset=2000,
        icon=folium.DivIcon(icon_size=(30, 30), icon_anchor=(15, 15), html='<div class="depot">D</div>'),
        tooltip="Depósito · Consultar carga y muelles", popup=folium.Popup(depot_html, max_width=340)).add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    active = sum(vehicle["active"] for vehicle in plan["vehicles"])
    sidebar = f'''
    <aside id="operations">
      <header><div class="eyebrow">PLAN DE DISTRIBUCIÓN</div><h1>Operación de rutas</h1>
      <p>Inicio de jornada {time(0)} · Red vial OpenStreetMap</p></header>
      <div class="verified">✓ {data['n_customers']}/{data['n_customers']} servicios dentro de ventana</div>
      <div class="stats"><div><b>{active}/{data['n_vehicles']}</b><small>Vehículos activos</small></div>
      <div><b>{plan['total_cost']:,}</b><small>Costo · unidades abstractas</small></div></div>
      <section><h2>Muelles del depósito</h2><p>Máximo simultáneo: {plan['peak_docks']}/{data['n_docks']}</p>
      {''.join(dock_rows)}<div class="axis"><span>{time(0)}</span><span>{time(scale)}</span></div>
      <small>Intervalos de carga. Asignación de muelles compatible con el plan.</small></section>
      <section><h2>Secuencia de visitas</h2>{''.join(cards)}</section>
      <footer>Las flechas siguen el sentido de cada arco vial. Active o desactive vehículos en el mapa.
      Llegada estimada al salir tras el servicio anterior; la espera se realiza antes del siguiente servicio.
      Ventanas aplicadas al inicio del servicio.<br><br>
      Tiempos de flujo libre, sin tráfico en vivo. Inicio de jornada configurable.
      © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> · ODbL.</footer>
    </aside>'''
    m.get_root().header.add_child(folium.Element('''<title>Operación de rutas · HFVRPTW</title><style>
      body{margin:0;color:#1f2937;font-family:system-ui,-apple-system,sans-serif}
      .folium-map{left:390px!important;width:calc(100% - 390px)!important;height:100%!important;background:#f1f4f6!important}
      #operations{position:absolute;z-index:900;inset:0 auto 0 0;width:390px;overflow:auto;background:#f7f8fa;padding:24px;box-sizing:border-box;box-shadow:2px 0 15px #0002;font-size:12px;line-height:1.5}
      #operations h1{font-size:25px;font-weight:700;margin:6px 0} #operations h2{font-size:15px;font-weight:700;margin:0 0 8px}
      #operations p{margin:5px 0 12px;color:#5d6674}.eyebrow{letter-spacing:1.8px;font-size:10px;color:#566579;font-weight:700}
      .verified{padding:10px 12px;border-radius:6px;background:#e4f3eb;color:#17633e;font-weight:600;margin:18px 0 12px}
      .stats{display:flex;gap:24px;padding:8px 0 18px}.stats b{display:block;font-size:23px;line-height:1.2}
      #operations small{display:block;color:#667085;font-size:10px;font-weight:400} #operations section{border-top:1px solid #dce0e5;padding-top:18px;margin-bottom:22px}
      .vehicle{margin:12px 0;background:#fff;border:1px solid #e0e4e9;border-radius:8px;padding:12px}.vehicle summary{cursor:pointer;font-size:13px;font-weight:700;list-style:none}
      .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px}.distance{float:right;font-weight:400;color:#526174}
      #operations .vehicle p{font-size:10px;margin-top:7px}table{width:100%;border-collapse:collapse;font-size:11px}th{text-align:left;font-size:9px;color:#637083;font-weight:500}
      td{padding:7px 3px;border-top:1px solid #eef0f3;vertical-align:top}th{padding:0 3px 6px}.inactive{padding:9px 12px;color:#6b7280;background:#eef0f3;border-radius:6px}
      .dock-row{display:flex;align-items:center;gap:8px;margin-top:8px}.dock-row>span{width:22px;font-size:10px;color:#64748b}.track{height:28px;position:relative;flex:1;background:#e4e8ed;border-radius:4px}
      .bar{position:absolute;height:28px;line-height:28px;border-radius:4px;color:white;font-weight:700;text-align:center;overflow:hidden;font-size:11px;box-shadow:inset 0 0 0 1px #fff9}.axis{display:flex;justify-content:space-between;margin:4px 0 8px 30px;color:#64748b;font-size:10px}
      .stop{border:2px solid white;border-radius:12px;color:white;text-align:center;font:700 10px/22px system-ui;box-shadow:0 1px 5px #0006;white-space:nowrap}.depot{background:#18283c;border:2px solid white;color:white;border-radius:7px;text-align:center;font:700 16px/26px system-ui;box-shadow:0 1px 5px #0005}
      .road-arrow{font:16px/18px system-ui;text-align:center;text-shadow:0 0 2px white}footer{font-size:10px;color:#667085}
      @media(max-width:700px){.folium-map{left:0!important;width:100%!important;height:56%!important}#operations{top:56%;bottom:0;width:100%;padding:18px}}
    </style>'''))
    m.get_root().html.add_child(folium.Element(sidebar))
    if bounds:
        # Refit after stylesheet/layout loading, including narrow browser viewports.
        extent = [[min(p[0] for p in bounds), min(p[1] for p in bounds)],
                  [max(p[0] for p in bounds), max(p[1] for p in bounds)]]
        m.get_root().html.add_child(folium.Element(
            '<script>window.addEventListener("load", function(){'
            f'const map = {m.get_name()}; map.invalidateSize(); '
            f'map.fitBounds({json.dumps(extent)}, '
            '{paddingTopLeft:[30,115],paddingBottomRight:[30,30],animate:false});'
            '});</script>'
        ))
    return m


def render_map(instance_file: Path, solution_file: Path, output: Path, *, geo_file: Path | None = None,
               graph_file: Path | None = None, start_time: str = "08:00") -> Path:
    """Check provenance before drawing; never silently substitute another graph."""
    instance_file, solution_file, output = Path(instance_file), Path(solution_file), Path(output)
    geo_file = Path(geo_file) if geo_file is not None else instance_file.with_suffix(".geo.json")
    geo, solution = json.loads(geo_file.read_text()), json.loads(solution_file.read_text())
    digest = hashlib.sha256(instance_file.read_bytes()).hexdigest()
    if geo.get("instance_sha256") != digest or solution.get("instance_sha256") != digest:
        raise ValueError("Instance, solution and geography checksums do not match")
    if graph_file is None:
        graph_file = Path(geo["graph_cache"])
        if not graph_file.is_absolute() and not graph_file.exists():
            graph_file = ROOT / graph_file
    graph_file = Path(graph_file)
    if not graph_file.is_file():
        raise FileNotFoundError(f"Original GraphML required for rendering: {graph_file}")
    if hashlib.sha256(graph_file.read_bytes()).hexdigest() != geo.get("graph_sha256"):
        raise ValueError("GraphML checksum differs from the graph used to build the instance")
    graph = ox.io.load_graphml(graph_file)
    m = make_map(graph, json.loads(instance_file.read_text()), geo, solution, start_time=start_time)
    output.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output))
    return output
