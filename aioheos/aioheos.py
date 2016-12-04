#!/usr/bin/env python3
" Heos python lib "

import asyncio
import socket
import json
from pprint import pprint
# import aioheos.aioheosupnp as aioheosupnp

HEOS_PORT = 1255

GET_PLAYERS    = 'player/get_players'
GET_PLAYER_INFO = 'player/get_player_info'
GET_PLAY_STATE = 'player/get_play_state'
SET_PLAY_STATE = 'player/set_play_state'
GET_MUTE_STATE = 'player/get_mute'
SET_MUTE_STATE = 'player/set_mute'
GET_VOLUME     = 'player/get_volume'
SET_VOLUME     = 'player/set_volume'
GET_NOW_PLAYING_MEDIA = 'player/get_now_playing_media'

PLAYER_VOLUME_CHANGED = 'event/player_volume_changed'
PLAYER_STATE_CHANGED = 'event/player_state_changed'
PLAYER_NOW_PLAYING_CHANGED = 'event/player_now_playing_changed'
PLAYER_NOW_PLAYING_PROGRESS = 'event/player_now_playing_progress'


class AioHeosException(Exception):
    " AioHeosException class "
    # pylint: disable=super-init-not-called
    def __init__(self, message):
        self.message = message


class AioHeos(object):
    " Asynchronous Heos class "

    def __init__(self, host=None, loop=None, verbose=False):
        self._host = host
        self._loop = loop
        self._players = None
        self._play_state = None
        self._mute_state = None
        self._volume_level = 0
        self._current_position = 0
        self._duration = 0
        self._media_artist = None
        self._media_album = None
        self._media_title = None
        self._media_image_url = None
        self._media_id = None

        self._verbose = verbose
        self._player_id = None
        # self._connection = None
        # self._upnp = aioheosupnp.HeosUpnp()
        self._reader = None
        self._writer = None

        if not self._host:
            # host = self._discover_ssdp()
            # url = self._upnp.discover()
            self._host = self._url_to_addr(url)

        # self.connect()

        # try:
        #     self._player_id = self.get_players()[0]['pid']
        # except TypeError:
        #     print('[E] No player found')

        # self.register_for_change_events()

    @staticmethod
    def _url_to_addr(url):
        import re
        try:
            addr = re.search('https?://([^:/]+)[:/].*$', url)
            return addr.group(1)
        except:         # pylint: disable=bare-except
            return None

    @asyncio.coroutine
    def connect(self, port=HEOS_PORT):
        if self._verbose:
            print('[I] Connecting to {}:{}'.format(self._host, port))
        yield from self._connect(self._host, port)

    @asyncio.coroutine
    def _connect(self, host, port=HEOS_PORT):
        " connect "
        self._reader, self._writer = yield from asyncio.open_connection(self._host, HEOS_PORT, loop=self._loop)
        # self._connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self._connection.connect((host, port))

    def send_command(self, command, message=None):
        " send command "
        msg = 'heos://' + command
        if message:
            if 'pid' in message.keys() and message['pid'] is None:
                message['pid'] = self.__player_id()
            msg += '?' + '&'.join("{}={}".format(key, val) for (key, val) in message.items())
        msg += '\r\n'
        if self._verbose:
            print(msg)
        self._writer.write(msg.encode('ascii'))
        # return self._recv_reply(command)

    @staticmethod
    def _parse_message(message):
        " parse message "
        return dict(elem.split('=') for elem in message.split('&'))

    def _dispatcher(self, command, payload):
        " call parser functions "
        # if self._verbose:
        print('DISPATCHER')
        pprint((command, payload))
        callbacks = {
                GET_PLAYERS: self._parse_players,
                GET_PLAY_STATE: self._parse_play_state,
                SET_PLAY_STATE: self._parse_play_state,
                GET_MUTE_STATE: self._parse_mute_state,
                SET_MUTE_STATE: self._parse_mute_state,
                GET_VOLUME: self._parse_volume,
                SET_VOLUME: self._parse_volume,
                GET_NOW_PLAYING_MEDIA: self._parse_now_playing_media,
                PLAYER_VOLUME_CHANGED: self._parse_player_volume_changed,
                PLAYER_STATE_CHANGED: self._parse_player_state_changed,
                PLAYER_NOW_PLAYING_CHANGED: self._parse_player_now_playing_changed,
                PLAYER_NOW_PLAYING_PROGRESS: self._parse_player_now_playing_progress,
                }
        if command in callbacks.keys():
            callbacks[command](payload)
        else:
            print('[W] command "{}" is not handled.'.format(command))

    def _parse_command(self, data):
        " parse command "
        try:
            data_heos = data['heos']
            command = data_heos['command']
            if 'result' in data_heos.keys() and data_heos['result'] == 'fail':
                raise AioHeosException(data_heos['message'])
            if 'payload' in data.keys():
                self._dispatcher(command, data['payload'])
            elif 'message' in data_heos.keys():
                message = self._parse_message(data_heos['message'])
                self._dispatcher(command, message)
            else:
                raise AioHeosException('No message or payload in reply.')
        # pylint: disable=bare-except
        except:
            raise AioHeosException('Problem parsing command.')

        return None

    @asyncio.coroutine
    def event_loop(self, trigger_callback=None):
        " recv reply "
        while True:
            if self._reader is None:
                yield from asyncio.sleep(1)
                continue
            # msg = yield from self._reader.read(64*1024)
            msg = yield from self._reader.readline()
            if self._verbose:
                pprint(msg.decode())
            # simplejson doesnt need to decode from byte to ascii
            data = json.loads(msg.decode())
            pprint('DATA:')
            pprint(data)
            self._parse_command(data)
            if trigger_callback:
                print('TRIGGER CALLBACK')
                # trigger_callback()
                yield from trigger_callback()
                # self._loop.create_task(trigger_callback())

    def close(self):
        " close "
        pass

    def register_for_change_events(self):
        " register for change events "
        self.send_command('system/register_for_change_events', {'enable': 'on'})

    def register_pretty_json(self, enable=False):
        " register for pretty json "
        set_enable = 'off'
        if enable is True:
            set_enable = 'on'
        self.send_command('system/prettify_json_response', {'enable': set_enable})

    def request_players(self):
        " get players "
        self.send_command(GET_PLAYERS)

    def _parse_players(self, payload):
        self._players = payload
        self._player_id = self._players[0]['pid']

    def __player_id(self):
        return self._player_id

    def request_player_info(self):
        " get player info "
        self.send_command(GET_PLAYER_INFO, {'pid': self.__player_id()})

    def request_play_state(self):
        " get play state "
        self.send_command(GET_PLAY_STATE, {'pid': self.__player_id()})

    def _parse_play_state(self, payload):
        self._play_state = payload['state']

    def get_play_state(self):
        return self._play_state

    def request_mute_state(self):
        " get mute state "
        self.send_command(GET_MUTE_STATE, {'pid': self.__player_id()})

    def _parse_mute_state(self, payload):
        self._mute_state = payload['state']

    def get_mute_state(self):
        return self._mute_state

    def request_volume(self):
        " get volume "
        self.send_command(GET_VOLUME, {'pid': self.__player_id()})

    def set_volume(self, volume_level):
        " set volume "
        if volume_level > 100:
            volume_level = 100
        if volume_level < 0:
            volume_level = 0
        self.send_command(SET_VOLUME, {'pid': self.__player_id(),
                                       'level': volume_level})

    def _parse_volume(self, message):
        self._volume_level = message['level']

    def get_volume(self):
        return self._volume_level

    def volume_level_up(self, step=10):
        " volume level up "
        self.set_volume(self._volume_level + step)

    def volume_level_down(self, step=10):
        " volume level down "
        self.set_volume(self._volume_level - step)

    def _set_play_state(self, state):
        " set play state "
        if state not in ('play', 'pause', 'stop'):
            AioHeosException('Not an accepted play state {}.'.format(state))

        self.send_command(SET_PLAY_STATE, {'pid': self.__player_id(),
                                           'state': state})

    def stop(self):
        " stop player "
        self._set_play_state('stop')

    def play(self):
        " play "
        self._set_play_state('play')

    def pause(self):
        " pause "
        self._set_play_state('pause')

    def request_now_playing_media(self):
        " get playing media "
        self.send_command(GET_NOW_PLAYING_MEDIA, {'pid': self.__player_id()})

    def _parse_now_playing_media(self, payload):
        if 'artist' in payload.keys():
            self._media_artist = payload['artist']
        if 'album' in payload.keys():
            self._media_album = payload['album']
        if 'song' in payload.keys():
            self._media_title = payload['song']
        if 'image_url' in payload.keys():
            self._media_image_url = payload['image_url']
        if 'mid' in payload.keys():
            self._media_id = payload['mid']

    def get_media_artist(self):
        return self._media_artist

    def get_media_album(self):
        return self._media_album

    def get_media_song(self):
        return self._media_title

    def get_media_image_url(self):
        return self._media_image_url

    def get_media_id(self):
        return self._medtitle

    def get_media_image_url(self):
        return self._media_image_url

    def get_media_id(self):
        return self._media_id

    def get_duration(self):
        return (self._current_position, self._duration)

    def request_queue(self):
        " get queue "
        self.send_command('player/get_queue', {'pid': self.__player_id()})

    def clear_queue(self):
        " clear queue "
        self.send_command('player/clear_queue', {'pid': self.__player_id()})

    def request_play_next(self):
        " play next "
        self.send_command('player/play_next', {'pid': self.__player_id()})

    def _parse_play_next(self, payload):
        " parse play next "
        pass

    def request_play_previous(self):
        " play prev "
        self.send_command('player/play_previous', {'pid': self.__player_id()})

    def play_queue(self, qid):
        " play queue "
        self.send_command('player/play_queue', {'pid': self.__player_id(),
                                                'qid': qid})

    def request_groups(self):
        " get groups "
        self.send_command('group/get_groups')

    def toggle_mute(self):
        " toggle mute "
        self.send_command('player/toggle_mute', {'pid': self.__player_id()})

    def request_music_sources(self):
        " get music sources "
        self.send_command('browser/get_music_sources', {'range': '0,29'})

    def request_browse_source(self, sid):
        " browse source "
        self.send_command('browser/browse', {'sid': sid, 'range': '0,29'})

    def play_content(self, content, content_type='audio/mpeg'):
        self._upnp.play_content(content, content_type)

    def _parse_player_volume_changed(self, message):
        self._mute_state = message['mute']
        self._volume_level = int(message['level'])

    def _parse_player_state_changed(self, message):
        self._play_state = message['state']

    def _parse_player_now_playing_changed(self, message):
        " event / now playing changed, request what changed. "
        self.request_now_playing_media()

    def _parse_player_now_playing_progress(self, message):
        self._current_position = int(message['cur_pos'])
        self._duration = int(message['duration'])


def main():
    " main "
    heos = AioHeos(host='HEOS-Player.rydbrink.local', verbose=True)

    # heos.connect()
    loop = asyncio.get_event_loop()
    tasks = [loop.create_task(heos.event_loop()),
            loop.create_task(heos.worker())]
    # heos._reader, heos._writer = asyncio.open_connection(self._host, HEOS_PORT)
    # future = asyncio.Future()
    # asyncio.ensure_future(reader(future))
    loop.run_until_complete(asyncio.wait(tasks))
    loop.close()
    import sys
    sys.exit()

    # heos._player_info()
    heos.request_play_state()
    heos.request_mute_state()
    heos.request_volume()
    heos.set_volume(10)
    heos.request_groups()

    with open('hello.mp3', mode='rb') as f:
        content = f.read()
    content_type = 'audio/mpeg'
    heos.play_content(content, content_type)
    heos.close()

if __name__ == "__main__":
    main()