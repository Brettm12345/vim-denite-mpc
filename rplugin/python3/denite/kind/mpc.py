# ============================================================================
# FILE: mpc.py
# AUTHOR: Rafael Bodill <justRafi at gmail.com>
# License: MIT license
# ============================================================================

import re
from .base import Base
from ..socket import Socket
from ..util import error

import os
import site
path_to_parent_dir = os.path.abspath(os.path.dirname(__file__) + '/../')
site.addsitedir(path_to_parent_dir)

from source.mpc import Source


class Kind(Base):

    def __init__(self, vim):
        super().__init__(vim)

        self.name = 'mpc'
        self.default_action = 'list'
        self.persist_actions = ['play', 'add', 'replace']
        self.redraw_actions = ['play']

        self.__vars = {}
        self.__sock = None

    def _kill(self):
        """ Close socket connection and clean cache """
        self.__sock.kill()
        self.__sock = None

    def action_list(self, context):
        """ Action: Open Denite mpc source with proper filters """
        self._get_vars(context)
        entity = context['source']['__entity']
        for candidate in context['targets']:
            # For tracks and playlist items, use 'play' instead of 'list'.
            if entity in ['title', 'playlist']:
                self.action_play(context)
                continue

            # Concat the candidate's command to be executed
            args = []
            for key, value in self._metadata(candidate).items():
                args.append(key)
                args.append(self._escape(value))

            if args:
                target_kind = self.__vars['targets'].get(entity)
                cmd = 'Denite mpc:{}:{}'.format(target_kind, ':'.join(args))
                self.vim.command(cmd)
                continue

            error(self.vim,
                  'Candidate is missing metadata: {}'.format(candidate))

    def action_play(self, context):
        """ Action: Add selected to playlist and start playing it,
                    or just play them if in playlist view """
        self._get_vars(context)
        if context['source']['__entity'] == 'playlist':
            play_index = context['targets'][0].get('meta__pos')
        else:
            cmds = self._get_commands('findadd', context)
            self._send(cmds, context)
            mpd_status = context['source'].get('__status', {})
            play_index = mpd_status.get('playlistlength', -1)

        self._send(['play {}'.format(play_index)], context)
        self._kill()

    def action_add(self, context):
        """ Action: Add selected to playlist """
        self._get_vars(context)
        cmds = self._get_commands('findadd', context)
        self._send(cmds, context)
        self._kill()

    def action_replace(self, context):
        """ Action: Replace playlist with selection and start playing """
        self._get_vars(context)
        cmds = ['clear'] + self._get_commands('findadd', context) + ['play']
        self._send(cmds, context)
        self._kill()

    def _get_vars(self, context):
        """ Load mpc source full vars and merge with user custom """
        # FIXME: Find a better way without importing Source
        if not self.__vars:
            custom = context['custom']['source'] \
                    .get('mpc', {}) \
                    .get('vars', {})
            self.__vars = Source(self.vim).vars.copy()
            self.__vars.update(custom)

    def _escape(self, s):
        """ Escape certain characters with backslash """
        if s:
            s = re.sub(r'(\\)', r'\\\\\\\1', s)
            s = re.sub(r'([:"\ ])', r'\\\1', s)
        return s

    def _get_commands(self, command, context):
        """ Iterate through all candidates and return list of commands """
        cmds = []
        for candidate in context['targets']:
            args = [command]
            for key, value in self._metadata(candidate).items():
                args.append(key)
                args.append('"{}"'.format(self._escape(value)))
            cmds.append(' '.join(args))

        return cmds

    def _metadata(self, candidate):
        """ Return clean metadata dict from candidate """
        return {key[6:]: value for key, value in candidate.items()
                if value and key.startswith('meta__')}

    def _send(self, commands, context):
        """ Send commands to socket and start communicating """
        self.__sock = Socket(
            self.__vars['host'],
            self.__vars['port'],
            commands,
            context,
            self.__vars['timeout'])

        return self.__sock.communicate(2.0)
