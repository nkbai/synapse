# -*- coding: utf-8 -*-
""" Contains events to do with rooms. """
from twisted.internet import defer

from events import (EventStreamMixin, PutEventMixin, GetEventMixin, BaseEvent,
                    InvalidHttpRequestError)
from auth import AccessTokenAuth
from synapse.api.dbobjects import Message, RoomMembership, RoomData

import json
import re

# TODO: Can on_PUTs which just check keys > dump in db be factored out somehow?


class RoomTopicEvent(EventStreamMixin, PutEventMixin, GetEventMixin, BaseEvent):

    @classmethod
    def get_pattern(cls):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/topic$")

    def get_event_type(self):
        return "sy.room.topic"

    @AccessTokenAuth.defer_authenticate
    @defer.inlineCallbacks
    def on_GET(self, request, room_id, auth_user_id=None):
        # TODO check they are invited/joined in the room if private. If
        # public, anyone can view the topic.

        # pull out topic from db
        result = yield RoomData.find(where=["path=?", request.path],
                                     limit=1, orderby="id DESC")
        if not result:
            defer.returnValue((404, BaseEvent.error("Topic not found.")))
        defer.returnValue((200, json.loads(result.content)))

    @AccessTokenAuth.defer_authenticate
    @defer.inlineCallbacks
    def on_PUT(self, request, room_id, auth_user_id=None):
        try:
            # TODO check they are joined in the room

            # validate JSON
            content = BaseEvent.get_valid_json(request.content.read(),
                                     [("topic", unicode)])

            # store in db
            yield RoomData(room_id=room_id, path=request.path,
                    content=json.dumps(content)).save()

            # TODO poke notifier
            # TODO send to s2s layer
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))
        defer.returnValue((200, ""))


class RoomMemberEvent(EventStreamMixin, PutEventMixin, GetEventMixin,
                      BaseEvent):

    @classmethod
    def get_pattern(cls):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/members/" +
                          "(?P<userid>[^/]*)/state$")

    def get_event_type(self):
        return "sy.room.members.state"

    @AccessTokenAuth.defer_authenticate
    @defer.inlineCallbacks
    def on_GET(self, request, roomid, userid, auth_user_id=None):
        # TODO check they are joined in the room

        # Pull out the membership from the db
        result = yield RoomMembership.find(where=["sender_id=? AND room_id=?",
                                userid, roomid], limit=1, orderby="id DESC")
        if not result:
            defer.returnValue((404, BaseEvent.error("Member not found.")))
        defer.returnValue((200, json.loads(result.content)))

    @AccessTokenAuth.defer_authenticate
    @defer.inlineCallbacks
    def on_PUT(self, request, roomid, userid, auth_user_id=None):
        # TODO
        # invites = they != userid & they are currently joined
        # joins = they == userid & they are invited or it's a new room by them
        # leaves = they == userid & they are currently joined
        # store membership
        # poke notifier
        # send to s2s layer
        try:
            content = BaseEvent.get_valid_json(request.content.read(),
                                           [("membership", unicode)])
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))

        member = RoomMembership(sender_id=userid, room_id=roomid,
                                content=json.dumps(content))
        yield member.save()
        defer.returnValue((200, ""))


class MessageEvent(EventStreamMixin, PutEventMixin, GetEventMixin,
                      BaseEvent):

    @classmethod
    def get_pattern(cls):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/messages/" +
                          "(?P<from>[^/]*)/(?P<msgid>[^/]*)$")

    def get_event_type(self):
        return "sy.room.message"

    @AccessTokenAuth.defer_authenticate
    @defer.inlineCallbacks
    def on_GET(self, request, room_id, msg_sender_id, msg_id,
               auth_user_id=None):
        # TODO check they are joined in the room

        # Pull out the message from the db
        results = yield Message.find(where=["room_id=? AND msg_id=? AND " +
                          "sender_id=?", room_id, msg_id, msg_sender_id])
        if len(results) == 0:
            defer.returnValue((404, BaseEvent.error("Message not found.")))
        defer.returnValue((200, json.loads(results[0].content)))

    @AccessTokenAuth.defer_authenticate
    @defer.inlineCallbacks
    def on_PUT(self, request, room_id, sender_id, msg_id,
               auth_user_id=None):
        try:
            # verify they are sending msgs under their own user id
            if sender_id != auth_user_id:
                raise InvalidHttpRequestError(403,
                          BaseEvent.error("Invalid userid."))
            # check the json
            req = BaseEvent.get_valid_json(request.content.read(),
                                           [("msgtype", unicode)])
            # TODO Check if sender_id is in room room_id

            # store message in db
            yield Message(sender_id=sender_id, room_id=room_id,
                          msg_id=msg_id, content=json.dumps(req)).save()

            # TODO poke notifier to send message to online users
            # TODO send to s2s layer

        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))

        defer.returnValue((200, ""))