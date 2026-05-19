# Copyright 2026 New Vector Ltd.
#
# SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 10


class PostgresDatabase:
    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent

        try:
            import psycopg2  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "db.type is set to 'postgresql' but psycopg2 is not installed. "
                "Install it with 'pip install psycopg2-binary'."
            ) from exc

        db_config = self.sydent.config.database

        self.db = psycopg2.connect(
            host=db_config.postgresql_host,
            port=db_config.postgresql_port,
            user=db_config.postgresql_user,
            password=db_config.postgresql_password,
            dbname=db_config.postgresql_database,
            sslmode=db_config.postgresql_sslmode,
        )

        self._ensure_schema()

    def _ensure_schema(self) -> None:
        cur = self.db.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sydent_schema_version (
                singleton BOOLEAN PRIMARY KEY DEFAULT TRUE,
                version INTEGER NOT NULL
            )
            """
        )
        cur.execute(
            """
            INSERT INTO sydent_schema_version (singleton, version)
            VALUES (TRUE, 0)
            ON CONFLICT (singleton) DO NOTHING
            """
        )
        cur.execute(
            "SELECT version FROM sydent_schema_version WHERE singleton = TRUE"
        )
        version = cur.fetchone()[0]

        if version == 0:
            self._create_schema()
            self._set_schema_version(CURRENT_SCHEMA_VERSION)
            self.db.commit()
            logger.info("PostgreSQL schema initialized at version %d", CURRENT_SCHEMA_VERSION)
            return

        if version != CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                "Unsupported PostgreSQL schema version %d. Expected %d. "
                "Migrations are not implemented yet for PostgreSQL."
                % (version, CURRENT_SCHEMA_VERSION)
            )

    def _set_schema_version(self, version: int) -> None:
        cur = self.db.cursor()
        cur.execute(
            "UPDATE sydent_schema_version SET version = %s WHERE singleton = TRUE",
            (version,),
        )

    def _create_schema(self) -> None:
        cur = self.db.cursor()

        statements = [
            """
            CREATE TABLE IF NOT EXISTS invite_tokens (
                id BIGSERIAL PRIMARY KEY,
                medium VARCHAR(16) NOT NULL,
                address VARCHAR(256) NOT NULL,
                room_id VARCHAR(256) NOT NULL,
                sender VARCHAR(256) NOT NULL,
                token VARCHAR(256) NOT NULL,
                received_ts BIGINT,
                sent_ts BIGINT,
                origin_id INTEGER,
                origin_server TEXT,
                valid_until_ts INTEGER
            )
            """,
            "CREATE INDEX IF NOT EXISTS invite_token_medium_address ON invite_tokens(medium, address)",
            "CREATE INDEX IF NOT EXISTS invite_token_token ON invite_tokens(token)",
            """
            CREATE TABLE IF NOT EXISTS ephemeral_public_keys (
                id BIGSERIAL PRIMARY KEY,
                public_key VARCHAR(256) NOT NULL,
                verify_count BIGINT DEFAULT 0,
                persistence_ts BIGINT,
                origin_server TEXT,
                origin_id INTEGER
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS ephemeral_public_keys_index ON ephemeral_public_keys(public_key)",
            """
            CREATE TABLE IF NOT EXISTS peers (
                id BIGSERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                port INTEGER DEFAULT NULL,
                lastSentAssocsId INTEGER DEFAULT 0,
                lastSentInviteTokensId INTEGER DEFAULT 0,
                lastSentInviteUpdatesId INTEGER DEFAULT 0,
                lastSentEphemeralKeysId INTEGER DEFAULT 0,
                lastPokeSucceededAt INTEGER,
                active INTEGER NOT NULL DEFAULT 0,
                shadow INTEGER NOT NULL DEFAULT 0
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS name ON peers(name)",
            """
            CREATE TABLE IF NOT EXISTS peer_pubkeys (
                id BIGSERIAL PRIMARY KEY,
                peername VARCHAR(255) NOT NULL,
                alg VARCHAR(16) NOT NULL,
                key TEXT NOT NULL,
                FOREIGN KEY (peername) REFERENCES peers(name)
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS peername_alg ON peer_pubkeys(peername, alg)",
            """
            CREATE TABLE IF NOT EXISTS profiles (
                user_id TEXT PRIMARY KEY,
                display_name TEXT DEFAULT NULL,
                avatar_url TEXT DEFAULT NULL,
                origin_server TEXT NOT NULL,
                batch BIGINT NOT NULL,
                active BOOLEAN DEFAULT TRUE NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS profiles_lower_displayname ON profiles(LOWER(display_name))",
            "CREATE INDEX IF NOT EXISTS profiles_origin_server_batch ON profiles(origin_server, batch)",
            """
            CREATE TABLE IF NOT EXISTS local_threepid_associations (
                id BIGSERIAL PRIMARY KEY,
                medium VARCHAR(16) NOT NULL,
                address VARCHAR(256) NOT NULL,
                mxid VARCHAR(256),
                ts INTEGER,
                notBefore BIGINT,
                notAfter BIGINT,
                lookup_hash VARCHAR(256)
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS local_threepid_medium_address ON local_threepid_associations(medium, address)",
            """
            CREATE TABLE IF NOT EXISTS global_threepid_associations (
                id BIGSERIAL PRIMARY KEY,
                medium VARCHAR(16) NOT NULL,
                address VARCHAR(256) NOT NULL,
                mxid VARCHAR(256) NOT NULL,
                ts INTEGER NOT NULL,
                notBefore BIGINT NOT NULL,
                notAfter INTEGER NOT NULL,
                originServer VARCHAR(255) NOT NULL,
                originId INTEGER NOT NULL,
                sgAssoc TEXT NOT NULL,
                lookup_hash VARCHAR(256)
            )
            """,
            "CREATE INDEX IF NOT EXISTS global_threepid_medium_address ON global_threepid_associations(medium, address)",
            "CREATE INDEX IF NOT EXISTS global_threepid_medium_lower_address ON global_threepid_associations(medium, LOWER(address))",
            "CREATE UNIQUE INDEX IF NOT EXISTS global_threepid_originServer_originId ON global_threepid_associations(originServer, originId)",
            "CREATE INDEX IF NOT EXISTS global_threepid_lookup_hash ON global_threepid_associations(lookup_hash)",
            """
            CREATE TABLE IF NOT EXISTS threepid_validation_sessions (
                id BIGSERIAL PRIMARY KEY,
                medium VARCHAR(16) NOT NULL,
                address VARCHAR(256) NOT NULL,
                clientSecret VARCHAR(32) NOT NULL,
                validated INTEGER DEFAULT 0,
                mtime BIGINT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS threepid_validation_sessions_mtime ON threepid_validation_sessions(mtime)",
            """
            CREATE TABLE IF NOT EXISTS threepid_token_auths (
                id BIGSERIAL PRIMARY KEY,
                validationSession INTEGER NOT NULL,
                token VARCHAR(32) NOT NULL,
                sendAttemptNumber INTEGER NOT NULL,
                next_link_used TEXT,
                FOREIGN KEY (validationSession) REFERENCES threepid_validation_sessions(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS updated_invites (
                id BIGSERIAL PRIMARY KEY,
                invite_id INTEGER NOT NULL,
                origin_server VARCHAR(256),
                origin_id VARCHAR(256)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS hashing_metadata (
                id INTEGER PRIMARY KEY,
                lookup_pepper VARCHAR(256)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS accounts (
                user_id TEXT NOT NULL PRIMARY KEY,
                created_ts BIGINT NOT NULL,
                consent_version TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT NOT NULL PRIMARY KEY,
                user_id TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS accepted_terms_urls (
                user_id TEXT NOT NULL,
                url TEXT NOT NULL
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS accepted_terms_urls_idx ON accepted_terms_urls (user_id, url)",
        ]

        for statement in statements:
            cur.execute(statement)
