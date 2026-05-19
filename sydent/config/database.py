# Copyright 2025 New Vector Ltd.
# Copyright 2021 The Matrix.org Foundation C.I.C.
#
# SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial
# Please see LICENSE files in the repository root for full details.
#
# Originally licensed under the Apache License, Version 2.0:
# <http://www.apache.org/licenses/LICENSE-2.0>.

from configparser import ConfigParser

from sydent.config._base import BaseConfig
from sydent.config.exceptions import ConfigError


class DatabaseConfig(BaseConfig):
    def parse_config(self, cfg: "ConfigParser") -> bool:
        """
        Parse the database section of the config

        :param cfg: the configuration to be parsed
        """
        db_type = cfg.get("db", "db.type")
        if db_type == "sqlite":
            self.database_type = "sqlite"
            self.database_path = cfg.get("db", "db.file")
        elif db_type == "postgresql":
            self.database_type = "postgresql"
            self.postgresql_host = cfg.get("db", "db.postgresql.host")
            self.postgresql_port = cfg.getint("db", "db.postgresql.port")
            self.postgresql_user = cfg.get("db", "db.postgresql.user")
            self.postgresql_password = cfg.get("db", "db.postgresql.password")
            self.postgresql_database = cfg.get("db", "db.postgresql.database")
            self.postgresql_sslmode = cfg.get("db", "db.postgresql.sslmode")
        else:
            raise ConfigError(
                "Unsupported db.type %r. Expected one of: sqlite, postgresql"
                % (db_type,)
            )

        return False
