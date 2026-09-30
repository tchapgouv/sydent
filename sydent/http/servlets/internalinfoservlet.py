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

from twisted.web.resource import Resource

import logging
import json

from sydent.db.invite_tokens import JoinTokenStore
from sydent.db.threepid_associations import GlobalAssociationStore
from sydent.http.servlets import get_args, jsonwrap, send_cors


logger = logging.getLogger(__name__)


class InternalInfoServlet(Resource):
    """Maps a threepid to the responsible HS domain, and gives invitation status.
    For use by homeserver instances.

    :param syd: A sydent instance.
    :type syd: Sydent
    :param info: An instance of Info.
    :type info: Sydent.http.Info
    """
    isLeaf = True

    def __init__(self, syd, info):
        self.sydent = syd
        self.info = info

    @jsonwrap
    def render_GET(self, request):
        """
        Returns: { hs: ..., [shadow_hs: ...], [new_hs: ...], invited: true/false, requires_invite: true/false }
        """

        send_cors(request)
        args = get_args(request, ('medium', 'address'))

        medium = args['medium']
        address = args['address']

        # Find an entry in the info file matching this user's ID
        result = self.info.match_user_id(medium, address)

        # Check if there's a MXID associated with this address, if so use its domain as
        # the value for "hs" (so that the user can still access their account through
        # Tchap) and move the value "hs" should have had otherwise to "new_hs" if it's a
        # different one.
        store = GlobalAssociationStore(self.sydent)
        mxid = store.getMxid(medium, address)
        if mxid:
            current_hs = mxid.split(':', 1)[1]
            if current_hs != result['hs']:
                result['new_hs'] = result['hs']
                result['hs'] = current_hs

        joinTokenStore = JoinTokenStore(self.sydent)
        pendingJoinTokens = joinTokenStore.getTokens(medium, address)

        # Report whether this user has been invited to a room
        result['invited'] = True if pendingJoinTokens else False
        return result

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
