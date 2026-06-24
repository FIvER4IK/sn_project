import os
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", PROJECT_DIR / "cities.db")).expanduser()
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = PROJECT_DIR / DATABASE_PATH
CITY_COLUMN_NAMES = (
    "id",
    "name",
    "settlement",
    "region",
    "federal_district",
    "district_full",
    "population",
    "bucket",
    "kladr",
    "lat",
    "lon",
    "region_population",
    "region_city_population",
    "region_country_population",
    "source_key",
)
CITY_COLUMNS = ", ".join(CITY_COLUMN_NAMES)
TOP_CITY_METRICS = {"population"}
CITY_FILTERS = (
    ("federal_district", "lower(federal_district) = lower(?)", None),
    ("region", "lower(region) = lower(?)", None),
    ("district_full", "lower(district_full) = lower(?)", None),
    ("bucket", "lower(bucket) = lower(?)", None),
    ("population_min", "population >= ?", int),
    ("population_max", "population <= ?", int),
    ("kladr", "kladr = ?", None),
    ("source_key", "lower(source_key) = lower(?)", None),
    ("region_population_min", "region_population >= ?", int),
    ("region_population_max", "region_population <= ?", int),
    ("region_city_population_min", "region_city_population >= ?", int),
    ("region_city_population_max", "region_city_population <= ?", int),
    ("region_country_population_min", "region_country_population >= ?", int),
    ("region_country_population_max", "region_country_population <= ?", int),
)
CITY_FILTER_NAMES = tuple(name for name, _, _ in CITY_FILTERS)
REQUIRED_CITY_COLUMNS = set(CITY_COLUMN_NAMES)
INSERT_CITY_SQL = """
    INSERT INTO cities (
        name, settlement, region, federal_district, district_full,
        population, bucket, kladr, lat, lon,
        region_population, region_city_population,
        region_country_population, source_key
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SEED_CITIES = [
    ("Тверь", "город Тверь", "Тверская область", "ЦФО", "Центральный федеральный округ", 412994, "250к-500к", None, None, None, None, None, None, "seed:Тверь"),
    ("Архангельск", "город Архангельск", "Архангельская область", "СЗФО", "Северо-Западный федеральный округ", 296665, "250к-500к", None, None, None, None, None, None, "seed:Архангельск"),
    ("Кострома", "город Кострома", "Костромская область", "ЦФО", "Центральный федеральный округ", 265761, "250к-500к", None, None, None, None, None, None, "seed:Кострома"),
    ("Череповец", "город Череповец", "Вологодская область", "СЗФО", "Северо-Западный федеральный округ", 298790, "250к-500к", None, None, None, None, None, None, "seed:Череповец"),
    ("Чита", "город Чита", "Забайкальский край", "ДФО", "Дальневосточный федеральный округ", 333159, "250к-500к", None, None, None, None, None, None, "seed:Чита"),
    ("Волжский", "город Волжский", "Волгоградская область", "ЮФО", "Южный федеральный округ", 315220, "250к-500к", None, None, None, None, None, None, "seed:Волжский"),
    ("Магнитогорск", "город Магнитогорск", "Челябинская область", "УФО", "Уральский федеральный округ", 407775, "250к-500к", None, None, None, None, None, None, "seed:Магнитогорск"),
    ("Курган", "город Курган", "Курганская область", "УФО", "Уральский федеральный округ", 300000, "250к-500к", None, None, None, None, None, None, "seed:Курган"),
    ("Орёл", "город Орёл", "Орловская область", "ЦФО", "Центральный федеральный округ", 301000, "250к-500к", None, None, None, None, None, None, "seed:Орёл"),
    ("Псков", "город Псков", "Псковская область", "СЗФО", "Северо-Западный федеральный округ", 187000, "100к-250к", None, None, None, None, None, None, "seed:Псков"),
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            settlement TEXT NOT NULL,
            region TEXT,
            federal_district TEXT NOT NULL,
            district_full TEXT,
            population INTEGER NOT NULL,
            bucket TEXT NOT NULL,
            kladr TEXT,
            lat REAL,
            lon REAL,
            region_population INTEGER,
            region_city_population INTEGER,
            region_country_population INTEGER,
            source_key TEXT UNIQUE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cities_district_population
        ON cities (federal_district, population DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cities_name_population
        ON cities (name, population DESC)
        """
    )


def ensure_schema(conn: sqlite3.Connection) -> None:
    existing_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(cities)").fetchall()
    }
    if not existing_columns:
        create_schema(conn)
        return
    if not REQUIRED_CITY_COLUMNS.issubset(existing_columns):
        conn.execute("DROP TABLE cities")
        create_schema(conn)


def init_db() -> None:
    if not DATABASE_PATH.is_file():
        raise RuntimeError(
            f"Готовая база данных не найдена: {DATABASE_PATH}. "
            "Убедитесь, что файл cities.db находится в корне проекта."
        )

    with get_conn() as conn:
        existing_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(cities)").fetchall()
        }
        missing_columns = REQUIRED_CITY_COLUMNS - existing_columns
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise RuntimeError(
                f"Файл cities.db имеет неверную структуру. "
                f"Отсутствуют столбцы: {missing}."
            )

        city_count = conn.execute("SELECT COUNT(*) FROM cities").fetchone()[0]
        if city_count == 0:
            raise RuntimeError("Готовая база cities.db не содержит городов.")


def fix_limit(value: int | None, default: int) -> int:
    value = default if value is None else int(value)
    return max(1, min(value, 50))


def fetch_all(query: str, params: list[Any]) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def add_filters(
    filters: list[str],
    params: list[Any],
    values: dict[str, Any],
) -> None:
    for name, condition, coerce in CITY_FILTERS:
        value = values.get(name)
        if value is None or value == "":
            continue
        filters.append(condition)
        params.append(value if coerce is None else coerce(value))


def query_cities(
    filter_values: dict[str, Any],
    order_by: str,
    limit: int,
) -> list[dict[str, Any]]:
    query = f"SELECT {CITY_COLUMNS} FROM cities"
    filters: list[str] = []
    params: list[Any] = []

    add_filters(filters, params, filter_values)

    if filters:
        query += " WHERE " + " AND ".join(filters)

    query += f" ORDER BY {order_by} LIMIT ?"
    params.append(limit)
    return fetch_all(query, params)


def get_cities(
    federal_district: str | None = None,
    region: str | None = None,
    district_full: str | None = None,
    population_min: int | None = None,
    population_max: int | None = None,
    bucket: str | None = None,
    kladr: str | None = None,
    source_key: str | None = None,
    region_population_min: int | None = None,
    region_population_max: int | None = None,
    region_city_population_min: int | None = None,
    region_city_population_max: int | None = None,
    region_country_population_min: int | None = None,
    region_country_population_max: int | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    return query_cities(locals(), "population DESC", fix_limit(limit, 10))


def get_city_names() -> list[str]:
    query = "SELECT DISTINCT name FROM cities ORDER BY length(name) DESC, name"
    return [row["name"] for row in fetch_all(query, [])]


def get_regions() -> list[str]:
    query = "SELECT DISTINCT region FROM cities WHERE region IS NOT NULL ORDER BY length(region) DESC, region"
    return [row["region"] for row in fetch_all(query, [])]


def has_metric_data(metric: str) -> bool:
    if metric not in TOP_CITY_METRICS:
        raise ValueError(f"Unsupported metric: {metric}")

    with get_conn() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) FROM cities WHERE {metric} IS NOT NULL AND {metric} != 0"
        ).fetchone()
    return bool(row[0])


def get_city_card(name: str) -> dict[str, Any] | None:
    if not name or not name.strip():
        raise ValueError("City name is required.")

    name = name.strip()
    with get_conn() as conn:
        row = conn.execute(
            f"""
            SELECT {CITY_COLUMNS} FROM cities
            WHERE lower(name) = lower(?)
               OR lower(settlement) = lower(?)
               OR lower(source_key) = lower(?)
            ORDER BY population DESC
            LIMIT 1
            """,
            (name, name, name),
        ).fetchone()
        if row:
            return dict(row)

        rows = conn.execute(f"SELECT {CITY_COLUMNS} FROM cities").fetchall()

    name = name.casefold()
    for row in rows:
        city = dict(row)
        if city["name"].casefold() == name or city["settlement"].casefold() == name:
            return city
    return None


def get_top_cities(
    metric: str,
    limit: int = 5,
    federal_district: str | None = None,
    region: str | None = None,
    district_full: str | None = None,
    population_min: int | None = None,
    population_max: int | None = None,
    bucket: str | None = None,
    kladr: str | None = None,
    source_key: str | None = None,
    region_population_min: int | None = None,
    region_population_max: int | None = None,
    region_city_population_min: int | None = None,
    region_city_population_max: int | None = None,
    region_country_population_min: int | None = None,
    region_country_population_max: int | None = None,
) -> list[dict[str, Any]]:
    if metric not in TOP_CITY_METRICS:
        raise ValueError(f"Unsupported metric: {metric}")

    return query_cities(
        locals(),
        f"{metric} DESC, population DESC",
        fix_limit(limit, 5),
    )
