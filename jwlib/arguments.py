import json
import urllib.request
import argparse
from sys import stderr
from typing import Tuple
import time


def action_factory(function):
    """Create an argparse.Action that will run the argument through a function before storing it"""

    class CustomAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            result = function(values)
            setattr(namespace, self.dest, result)

    return CustomAction


def get_jwb_languages():
    url = 'https://data.jw-api.org/mediator/v1/languages/E/web?clientType=www'
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode('utf-8'))['languages']


def verify_language(code):
    if code != 'E':
        for l in get_jwb_languages():
            if l['code'] == code:
                break
        else:
            raise ValueError(code + ': invalid language code')
    return code


def print_language(x):
    print('language codes:', file=stderr)
    for l in get_jwb_languages():
        print('{:>3}  {:<}'.format(l['code'], l['name']), file=stderr)
    exit()


class Settings:
    """Global settings and defaults"""

    # General stuff
    work_dir = '.'
    quiet = 0
    list_languages = False

    # API parsing stuff
    lang = 'E'
    quality = 1080
    hard_subtitles = False
    min_date = None  # type: int
    include_categories = ('VideoOnDemand',)
    exclude_categories = ()  # type: Tuple[str]

    # Disk space check stuff
    keep_free = 0  # bytes
    # Warn if limit is set too low
    warning = True

    # Download stuff
    download = False
    download_subtitles = False
    friendly_subtitle_filenames = False
    curl_path = 'curl'
    rate_limit = '1M'
    checksums = True

    # Stream stuff
    command = None  # type: list
    stream_forever = False

    # Output stuff
    sub_dir = ''
    mode = None  # type: str
    # NTFS friendly
    safe_filenames = False
    # Prepend the codename (filesystem)
    include_keyname = False
    # Remove non-broken symlinks (filesystem)
    clean_all_symlinks = False

    def __setattr__(self, key, value):
        # This will raise an error if the attribute we are trying to set doesn't already exist
        getattr(self, key)
        super().__setattr__(key, value)


class ArgumentParser(argparse.ArgumentParser):
    """Predefined arguments can be activated with add_arguments()"""

    def add_predefined(self, *flags, **kwargs):
        self.predefined_arguments[flags[0]] = dict(flags=flags, **kwargs)

    def add_arguments(self, flags: list):
        """Activate predefined arguments found in list"""
        for flag in flags:
            keywords = self.predefined_arguments[flag]
            args = keywords.pop('flags')
            self.add_argument(*args, **keywords)

    def parse_args(self, *args, namespace=None, **kwargs):
        settings = namespace or Settings()
        super().parse_args(*args, namespace=settings, **kwargs)
        return settings

    def __init__(self, *args, argument_default=None, **kwargs):
        # Do not overwrite attributes with None
        super().__init__(*args, argument_default=argparse.SUPPRESS, **kwargs)
        self.predefined_arguments = {}
        add_predefined = self.add_predefined

        # Put all argument definitions here
        # This way, the syntax will be equal to running add_argument()
        add_predefined('--quiet', '-q', action='count',
                       help='Less info, can be used multiple times')
        add_predefined('--mode', '-m',
                       choices=['stdout', 'filesystem', 'm3u', 'm3ucompat', 'html'],
                       help='output mode')
        add_predefined('--lang', '-l', nargs='?',
                       action=action_factory(verify_language),
                       help='language code')
        add_predefined('--languages',
                       action=action_factory(print_language),
                       help='display a list of valid language codes')
        add_predefined('--quality', '-Q', type=int,
                       choices=[240, 360, 480, 720],
                       help='maximum video quality')
        add_predefined('--hard-subtitles', action='store_true',
                       help='prefer videos with hard-coded subtitles')
        add_predefined('--no-checksum', action='store_false', dest='checksum',
                       help="don't check md5 checksum")
        add_predefined('--free', type=int, metavar='MiB', dest='keep_free',
                       action=action_factory(lambda x: x * 1024 * 1024),  # MiB to B
                       help='disk space in MiB to keep free (deletes older MP4 files)')
        add_predefined('--no-warning', dest='warning', action='store_false',
                       help='do not warn when space limit seems wrong')
        add_predefined('--category', '-c', dest='include_categories', metavar='CODE',
                       action=action_factory(lambda x: tuple(x.split(','))),
                       help='comma separated list of categories to index')
        add_predefined('--exclude', metavar='CODE', dest='exclude_categories',
                       action=action_factory(lambda x: tuple(x.split(','))),
                       help='comma separated list of categories to exclude from download')
        add_predefined('--latest', action='store_const', const=['LatestVideos'],
                       dest='include_categories',
                       help='index the "Latest Videos" section')
        add_predefined('--since', metavar='YYYY-MM-DD', dest='min_date',
                       action=action_factory(lambda x: time.mktime(time.strptime(x, '%Y-%m-%d'))),
                       help='only index media newer than this date')
        add_predefined('--limit-rate', dest='rate_limit',
                       help='maximum download rate, passed to curl (0 = no limit)')
        add_predefined('--curl-path', metavar='PATH',
                       help='path to the curl binary')
        add_predefined('--no-curl', action='store_const', const=None, dest='curl_path',
                       help='use urllib instead of external curl (compatibility)')
        add_predefined('--clean-symlinks', action='store_true', dest='clean_all_symlinks',
                       help='remove all old symlinks (only valid with --mode=filesystem)')
        add_predefined('--ntfs', action='store_true', dest='safe_filenames',
                       help='remove special characters from file names (NTFS/FAT compatibility)')
        add_predefined('--download', '-d', nargs='?', const='media',
                       choices=['media', 'subtitles', 'friendly-subtitles'],
                       help='download media files or subtitles')
        add_predefined('--forever', action='store_true', dest='stream_forever',
                       help='re-run program when the last video finishes')
        add_predefined('work_dir', nargs='?', metavar='DIR',
                       help='directory to save data in')
        add_predefined('command', nargs=argparse.REMAINDER, metavar='COMMAND',
                       help='video player command')
