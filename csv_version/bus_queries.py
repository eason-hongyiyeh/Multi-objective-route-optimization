import csv
import heapq
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "generated_csv_260607"


@dataclass(frozen=True)
class Stop:
    stop_id: str
    stop_name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class RouteStop:
    sequence: int
    stop_id: str
    stop_name: str


@dataclass(frozen=True)
class DirectBus:
    route_name: str
    start_sequence: int
    end_sequence: int
    stop_count: int
    travel_time_min: int
    stops: list[RouteStop]


@dataclass(frozen=True)
class TransferLeg:
    route_name: str
    start_stop: RouteStop
    end_stop: RouteStop
    stop_count: int
    travel_time_min: int
    stops: list[RouteStop]


@dataclass(frozen=True)
class BusJourney:
    transfer_count: int
    travel_time_min: int
    stop_count: int
    legs: list[TransferLeg]


@dataclass(frozen=True)
class NearbyStop:
    stop_id: str
    stop_name: str
    walking_time_min: int


@dataclass(frozen=True)
class ProductPOI:
    poi_id: str
    poi_name: str
    poi_type: str
    rating: float
    item_name: str
    price: int
    service_time_min: int
    nearby_stops: list[NearbyStop]


@dataclass(frozen=True)
class PlacePOI:
    poi_id: str
    poi_name: str
    poi_type: str
    rating: float
    nearby_stops: list[NearbyStop]


@dataclass(frozen=True)
class ShoppingRoute:
    destination_stop: NearbyStop
    journey: BusJourney | None
    already_at_destination: bool

    @property
    def total_time_min(self) -> int:
        bus_time = self.journey.travel_time_min if self.journey else 0
        return bus_time + self.destination_stop.walking_time_min


@dataclass(frozen=True)
class ShoppingTrip:
    shopping_stop: NearbyStop
    inbound_journey: BusJourney | None
    outbound_journey: BusJourney | None
    starts_at_shopping_stop: bool
    ends_at_shopping_stop: bool

    @property
    def total_time_min(self) -> int:
        inbound_time = self.inbound_journey.travel_time_min if self.inbound_journey else 0
        outbound_time = self.outbound_journey.travel_time_min if self.outbound_journey else 0
        return inbound_time + self.shopping_stop.walking_time_min + outbound_time

    @property
    def total_transfer_count(self) -> int:
        inbound_transfers = (
            self.inbound_journey.transfer_count if self.inbound_journey else 0
        )
        outbound_transfers = (
            self.outbound_journey.transfer_count if self.outbound_journey else 0
        )
        return inbound_transfers + outbound_transfers


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load_stops(data_dir: Path = DATA_DIR) -> dict[str, Stop]:
    stops = {}
    for row in _read_csv(data_dir / "stops.csv"):
        stop_id = row["stop_id"].strip()
        stops[stop_id] = Stop(
            stop_id=stop_id,
            stop_name=row["stop_name"].strip(),
            lat=float(row["lat"]),
            lon=float(row["lon"]),
        )
    return stops


def list_all_stops(data_dir: Path = DATA_DIR) -> list[Stop]:
    return sorted(load_stops(data_dir).values(), key=lambda stop: stop.stop_id)


def _load_route_edges(data_dir: Path = DATA_DIR) -> dict[str, list[dict[str, str]]]:
    routes: dict[str, list[dict[str, str]]] = {}
    for row in _read_csv(data_dir / "route_edges.csv"):
        route_name = row["route_name"].strip()
        if route_name:
            routes.setdefault(route_name, []).append(row)
    return routes


def list_routes(data_dir: Path = DATA_DIR) -> list[str]:
    return sorted(_load_route_edges(data_dir).keys())


def get_route_stop_sequence(route_name: str, data_dir: Path = DATA_DIR) -> list[RouteStop]:
    stops = load_stops(data_dir)
    route_edges = _load_route_edges(data_dir).get(route_name, [])
    if not route_edges:
        return []

    from_ids = [row["from_stop_id"].strip() for row in route_edges]
    to_ids = [row["to_stop_id"].strip() for row in route_edges]
    start_candidates = [stop_id for stop_id in from_ids if stop_id not in set(to_ids)]
    current_stop_id = start_candidates[0] if start_candidates else from_ids[0]

    next_by_stop = {
        row["from_stop_id"].strip(): row["to_stop_id"].strip()
        for row in route_edges
    }

    sequence_ids = [current_stop_id]
    visited = {current_stop_id}
    while current_stop_id in next_by_stop:
        current_stop_id = next_by_stop[current_stop_id]
        if current_stop_id in visited:
            break
        sequence_ids.append(current_stop_id)
        visited.add(current_stop_id)

    return [
        RouteStop(
            sequence=index,
            stop_id=stop_id,
            stop_name=stops[stop_id].stop_name if stop_id in stops else stop_id,
        )
        for index, stop_id in enumerate(sequence_ids, start=1)
    ]


def find_stop_id(query: str, data_dir: Path = DATA_DIR) -> str | None:
    normalized = query.strip().lower()
    if not normalized:
        return None

    stops = load_stops(data_dir)
    for stop_id, stop in stops.items():
        if normalized == stop_id.lower() or normalized == stop.stop_name.lower():
            return stop_id
    return None


def find_direct_buses(start_query: str, end_query: str, data_dir: Path = DATA_DIR) -> list[DirectBus]:
    start_stop_id = find_stop_id(start_query, data_dir)
    end_stop_id = find_stop_id(end_query, data_dir)
    if not start_stop_id or not end_stop_id or start_stop_id == end_stop_id:
        return []

    edge_times_by_route = _route_edge_times(data_dir)
    direct_buses = []
    for route_name in list_routes(data_dir):
        sequence = get_route_stop_sequence(route_name, data_dir)
        sequence_ids = [stop.stop_id for stop in sequence]
        if start_stop_id not in sequence_ids or end_stop_id not in sequence_ids:
            continue

        start_index = sequence_ids.index(start_stop_id)
        end_index = sequence_ids.index(end_stop_id)
        if start_index >= end_index:
            continue

        segment = sequence[start_index : end_index + 1]
        travel_time = sum(
            edge_times_by_route.get(route_name, {}).get(
                (segment[index].stop_id, segment[index + 1].stop_id),
                0,
            )
            for index in range(len(segment) - 1)
        )
        direct_buses.append(
            DirectBus(
                route_name=route_name,
                start_sequence=start_index + 1,
                end_sequence=end_index + 1,
                stop_count=len(segment) - 1,
                travel_time_min=travel_time,
                stops=segment,
            )
        )

    return sorted(direct_buses, key=lambda bus: (bus.travel_time_min, bus.stop_count, bus.route_name))


def find_bus_journey(
    start_query: str,
    end_query: str,
    data_dir: Path = DATA_DIR,
) -> BusJourney | None:
    start_stop_id = find_stop_id(start_query, data_dir)
    end_stop_id = find_stop_id(end_query, data_dir)
    if not start_stop_id or not end_stop_id or start_stop_id == end_stop_id:
        return None

    stops = load_stops(data_dir)
    outgoing: dict[str, list[tuple[str, str, int]]] = {}
    for row in _read_csv(data_dir / "route_edges.csv"):
        from_stop_id = row["from_stop_id"].strip()
        to_stop_id = row["to_stop_id"].strip()
        route_name = row["route_name"].strip()
        travel_time = int(row["travel_time_min"])
        outgoing.setdefault(from_stop_id, []).append(
            (route_name, to_stop_id, travel_time)
        )
        # The CSV stores one ordered stop sequence per route. Model the same
        # route in the opposite direction so trips can leave terminal areas.
        outgoing.setdefault(to_stop_id, []).append(
            (route_name, from_stop_id, travel_time)
        )

    # Cost is ordered by transfers first, then travel time and number of stops.
    distances: dict[tuple[str, str], tuple[int, int, int]] = {}
    previous: dict[
        tuple[str, str],
        tuple[tuple[str, str] | None, tuple[str, str, str, int]],
    ] = {}
    queue: list[tuple[int, int, int, str, str]] = []

    for route_name, to_stop_id, travel_time in outgoing.get(start_stop_id, []):
        state = (to_stop_id, route_name)
        cost = (0, travel_time, 1)
        if cost < distances.get(state, (float("inf"), float("inf"), float("inf"))):
            distances[state] = cost
            previous[state] = (
                None,
                (route_name, start_stop_id, to_stop_id, travel_time),
            )
            heapq.heappush(queue, (*cost, to_stop_id, route_name))

    destination_state: tuple[str, str] | None = None
    while queue:
        transfers, travel_time, stop_count, stop_id, route_name = heapq.heappop(queue)
        state = (stop_id, route_name)
        if distances.get(state) != (transfers, travel_time, stop_count):
            continue
        if stop_id == end_stop_id:
            destination_state = state
            break

        for next_route, next_stop_id, edge_time in outgoing.get(stop_id, []):
            next_state = (next_stop_id, next_route)
            next_cost = (
                transfers + (next_route != route_name),
                travel_time + edge_time,
                stop_count + 1,
            )
            if next_cost >= distances.get(
                next_state,
                (float("inf"), float("inf"), float("inf")),
            ):
                continue
            distances[next_state] = next_cost
            previous[next_state] = (
                state,
                (next_route, stop_id, next_stop_id, edge_time),
            )
            heapq.heappush(queue, (*next_cost, next_stop_id, next_route))

    if destination_state is None:
        return None

    edges: list[tuple[str, str, str, int]] = []
    state: tuple[str, str] | None = destination_state
    while state is not None:
        state, edge = previous[state]
        edges.append(edge)
    edges.reverse()

    legs: list[TransferLeg] = []
    leg_route = edges[0][0]
    leg_stop_ids = [edges[0][1]]
    leg_time = 0
    for route_name, from_stop_id, to_stop_id, edge_time in edges:
        if route_name != leg_route:
            legs.append(_build_transfer_leg(leg_route, leg_stop_ids, leg_time, stops))
            leg_route = route_name
            leg_stop_ids = [from_stop_id]
            leg_time = 0
        leg_stop_ids.append(to_stop_id)
        leg_time += edge_time
    legs.append(_build_transfer_leg(leg_route, leg_stop_ids, leg_time, stops))

    transfers, travel_time, stop_count = distances[destination_state]
    return BusJourney(
        transfer_count=transfers,
        travel_time_min=travel_time,
        stop_count=stop_count,
        legs=legs,
    )


def _build_transfer_leg(
    route_name: str,
    stop_ids: list[str],
    travel_time_min: int,
    stops: dict[str, Stop],
) -> TransferLeg:
    route_stops = [
        RouteStop(
            sequence=index,
            stop_id=stop_id,
            stop_name=stops[stop_id].stop_name if stop_id in stops else stop_id,
        )
        for index, stop_id in enumerate(stop_ids, start=1)
    ]
    return TransferLeg(
        route_name=route_name,
        start_stop=route_stops[0],
        end_stop=route_stops[-1],
        stop_count=len(route_stops) - 1,
        travel_time_min=travel_time_min,
        stops=route_stops,
    )


def find_product_pois(query: str, data_dir: Path = DATA_DIR) -> list[ProductPOI]:
    normalized = query.strip().lower()
    if not normalized:
        return []

    items = {
        row["item_id"].strip(): row["item_name"].strip()
        for row in _read_csv(data_dir / "poi_items.csv")
    }
    pois = {
        row["poi_id"].strip(): row
        for row in _read_csv(data_dir / "pois.csv")
    }
    stops = load_stops(data_dir)
    nearby_stops: dict[str, list[NearbyStop]] = {}
    for row in _read_csv(data_dir / "stop_poi_mapping.csv"):
        stop_id = row["stop_id"].strip()
        poi_id = row["poi_id"].strip()
        nearby_stops.setdefault(poi_id, []).append(
            NearbyStop(
                stop_id=stop_id,
                stop_name=stops[stop_id].stop_name if stop_id in stops else stop_id,
                walking_time_min=int(row["walking_time_min"]),
            )
        )

    results = []
    for row in _read_csv(data_dir / "poi_item_mapping.csv"):
        item_name = items.get(row["item_id"].strip())
        if item_name is None:
            continue
        if normalized not in item_name.lower():
            continue
        poi_id = row["poi_id"].strip()
        poi = pois.get(poi_id)
        if poi is None:
            continue
        results.append(
            ProductPOI(
                poi_id=poi_id,
                poi_name=poi["poi_name"].strip(),
                poi_type=poi["poi_type"].strip(),
                rating=float(poi["rating"]),
                item_name=item_name,
                price=int(row["price"]),
                service_time_min=int(row["service_time_min"]),
                nearby_stops=sorted(
                    nearby_stops.get(poi_id, []),
                    key=lambda stop: stop.walking_time_min,
                ),
            )
        )

    return sorted(results, key=lambda result: (-result.rating, result.price, result.poi_name))


def find_places(query: str, data_dir: Path = DATA_DIR) -> list[PlacePOI]:
    normalized = query.strip().lower()
    if not normalized:
        return []

    stops = load_stops(data_dir)
    nearby_stops: dict[str, list[NearbyStop]] = {}
    for row in _read_csv(data_dir / "stop_poi_mapping.csv"):
        stop_id = row["stop_id"].strip()
        poi_id = row["poi_id"].strip()
        nearby_stops.setdefault(poi_id, []).append(
            NearbyStop(
                stop_id=stop_id,
                stop_name=stops[stop_id].stop_name if stop_id in stops else stop_id,
                walking_time_min=int(row["walking_time_min"]),
            )
        )

    results = []
    for row in _read_csv(data_dir / "pois.csv"):
        poi_id = row["poi_id"].strip()
        poi_name = row["poi_name"].strip()
        poi_type = row["poi_type"].strip()
        if normalized not in poi_name.lower() and normalized not in poi_type.lower():
            continue
        if poi_id not in nearby_stops:
            continue
        results.append(
            PlacePOI(
                poi_id=poi_id,
                poi_name=poi_name,
                poi_type=poi_type,
                rating=float(row["rating"]),
                nearby_stops=sorted(
                    nearby_stops[poi_id],
                    key=lambda stop: stop.walking_time_min,
                ),
            )
        )

    return sorted(results, key=lambda result: (-result.rating, result.poi_name))


def find_best_shopping_route(
    start_query: str,
    product_poi: ProductPOI,
    data_dir: Path = DATA_DIR,
) -> ShoppingRoute | None:
    start_stop_id = find_stop_id(start_query, data_dir)
    if not start_stop_id:
        return None

    candidates = []
    for nearby_stop in product_poi.nearby_stops:
        if nearby_stop.stop_id == start_stop_id:
            candidates.append(
                ShoppingRoute(
                    destination_stop=nearby_stop,
                    journey=None,
                    already_at_destination=True,
                )
            )
            continue

        journey = find_bus_journey(start_stop_id, nearby_stop.stop_id, data_dir)
        if journey is not None:
            candidates.append(
                ShoppingRoute(
                    destination_stop=nearby_stop,
                    journey=journey,
                    already_at_destination=False,
                )
            )

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda route: (
            route.journey.transfer_count if route.journey else 0,
            route.total_time_min,
            route.journey.stop_count if route.journey else 0,
        ),
    )


def find_best_shopping_trip(
    start_query: str,
    end_query: str,
    product_poi: ProductPOI | PlacePOI,
    data_dir: Path = DATA_DIR,
) -> ShoppingTrip | None:
    start_stop_id = find_stop_id(start_query, data_dir)
    end_stop_id = find_stop_id(end_query, data_dir)
    if not start_stop_id or not end_stop_id:
        return None

    candidates = []
    for nearby_stop in product_poi.nearby_stops:
        starts_at_shopping_stop = nearby_stop.stop_id == start_stop_id
        ends_at_shopping_stop = nearby_stop.stop_id == end_stop_id
        inbound_journey = (
            None
            if starts_at_shopping_stop
            else find_bus_journey(start_stop_id, nearby_stop.stop_id, data_dir)
        )
        outbound_journey = (
            None
            if ends_at_shopping_stop
            else find_bus_journey(nearby_stop.stop_id, end_stop_id, data_dir)
        )
        if not starts_at_shopping_stop and inbound_journey is None:
            continue
        if not ends_at_shopping_stop and outbound_journey is None:
            continue

        candidates.append(
            ShoppingTrip(
                shopping_stop=nearby_stop,
                inbound_journey=inbound_journey,
                outbound_journey=outbound_journey,
                starts_at_shopping_stop=starts_at_shopping_stop,
                ends_at_shopping_stop=ends_at_shopping_stop,
            )
        )

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda trip: (
            trip.total_transfer_count,
            trip.total_time_min,
            (trip.inbound_journey.stop_count if trip.inbound_journey else 0)
            + (trip.outbound_journey.stop_count if trip.outbound_journey else 0),
        ),
    )


def _route_edge_times(data_dir: Path = DATA_DIR) -> dict[str, dict[tuple[str, str], int]]:
    times: dict[str, dict[tuple[str, str], int]] = {}
    for row in _read_csv(data_dir / "route_edges.csv"):
        route_name = row["route_name"].strip()
        from_stop_id = row["from_stop_id"].strip()
        to_stop_id = row["to_stop_id"].strip()
        times.setdefault(route_name, {})[(from_stop_id, to_stop_id)] = int(row["travel_time_min"])
    return times
