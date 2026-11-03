# -*- coding: utf-8 -*-

# Copyright 2018 New Vector Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import re
import copy
import yaml

logger = logging.getLogger(__name__)

class Info(object):
    """Returns information from info.yaml, which contains user-specific metadata."""

    def __init__(self, syd, info_file_path):
        """
        :param syd: The global sydent object
        :type syd: Sydent

        :param info_file_path: Filepath of the info.yaml file that defines which homeservers
            users belong to
        :type info_file_path: str
        """
        self.sydent = syd

        try:
            file = open(info_file_path)
            self.config = yaml.safe_load(file)
            file.close()

            # medium:
            #   email:
            #     entries:
            #       matthew@matrix.org: { hs: 'matrix.org', shadow_hs: 'shadow-matrix.org' }
            #     patterns:
            #       - .*@matrix.org: { hs: 'matrix.org', shadow_hs: 'shadow-matrix.org' }

            # Email addresses (and the DNS hostnames they rely on) are
            # case-insensitive, so lowercase the keys of the entries to make
            # the lookups performed by match_user_id case-insensitive even if
            # the info file mixes cases.
            email_info = self.config['medium']['email']
            email_info['entries'] = {
                entry.lower(): value
                for entry, value in email_info.get('entries', {}).items()
            }

        except Exception as e:
            logger.error(e)

    def match_user_id(self, medium, address):
        """Return information for a given medium/address combination.

        Email addresses are matched case-insensitively: DNS hostnames are
        case-insensitive (and so are email addresses in practice), so e.g.
        "john.doe@Interieur.Gouv.fr" must resolve to the same homeserver as
        "john.doe@interieur.gouv.fr".

        :param medium: The medium of the address.
        :type medium: str
        :param address: The address of the 3PID.
        :type address: str
        :returns a dict containing information regarding the user, or an
            empty dict if no match was found.
        :rtype: Dict
        """
        result = {}

        # Lowercase the address before matching it against the info file so
        # that the lookup is case-insensitive (the entries' keys are
        # lowercased when loading the info file, and the patterns are
        # matched with re.IGNORECASE).
        address = address.lower()

        # Find an entry in the info file matching this user's ID
        if address in self.config['medium']['email']['entries']:
            result = self.config['medium']['email']['entries'][address]
        else:
            for pattern_group in self.config['medium']['email']['patterns']:
                for pattern in pattern_group:
                    if (re.match("^" + pattern + "$", address, re.IGNORECASE)):
                        result = pattern_group[pattern]
                        break
                if result:
                    break

        # Copy before changing elements
        return copy.deepcopy(result)
