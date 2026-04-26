from __future__ import annotations

import sqlite3
import struct

import sqlite_vec

from src.config import get_settings


def serialize_f32(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def deserialize_f32(data: bytes) -> list[float]:
    n = len(data) // 4
    return list(struct.unpack(f"{n}f", data))


def load_vec_extension(db_connection: sqlite3.Connection) -> None:
    db_connection.enable_load_extension(True)
    sqlite_vec.load(db_connection)
    db_connection.enable_load_extension(False)


def create_vec_table(db_connection: sqlite3.Connection) -> None:
    dimensions = get_settings().embedding.dimensions
    db_connection.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks "
        f"USING vec0(chunk_id INTEGER PRIMARY KEY, embedding float[{dimensions}] distance_metric=cosine)",
    )
    db_connection.commit()


def insert_embedding(db_connection: sqlite3.Connection, chunk_id: int, vector: list[float]) -> None:
    blob = serialize_f32(vector)
    db_connection.execute(
        "INSERT INTO vec_chunks(chunk_id, embedding) VALUES (?, ?)",
        (chunk_id, blob),
    )
    db_connection.commit()


def delete_embeddings(db_connection: sqlite3.Connection, chunk_ids: list[int]) -> None:
    placeholders = ",".join("?" for _ in chunk_ids)
    db_connection.execute(
        f"DELETE FROM vec_chunks WHERE chunk_id IN ({placeholders})",
        chunk_ids,
    )
    db_connection.commit()


def search_similar(
    db_connection: sqlite3.Connection,
    query_vector: list[float],
    top_k: int = 20,
) -> list[tuple[int, float]]:
    blob = serialize_f32(query_vector)
    cursor = db_connection.execute(
        "SELECT chunk_id, distance FROM vec_chunks WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
        (blob, top_k),
    )
    return [(row[0], row[1]) for row in cursor.fetchall()]
