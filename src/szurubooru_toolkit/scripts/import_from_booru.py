import argparse
import sys
import urllib
from math import ceil
from pathlib import Path

from loguru import logger
from pybooru.danbooru import Danbooru
from pybooru.moebooru import Moebooru
from syncer import sync
from tqdm import tqdm

from szurubooru_toolkit import Gelbooru
from szurubooru_toolkit import config
from szurubooru_toolkit.scripts import upload_media
from szurubooru_toolkit.utils import convert_rating


sys.tracebacklimit = 0


def parse_args() -> tuple:
    """
    Parse the input args to the script auto_tagger.py and set the object attributes accordingly.
    """

    parser = argparse.ArgumentParser(
        description='This script downloads and tags posts from various Boorus based on your input query.',
    )

    parser.add_argument(
        'booru',
        choices=['danbooru', 'gelbooru', 'konachan', 'yandere', 'all'],
        help='Specify the Booru which you want to query. Use all to query all Boorus.',
    )
    parser.add_argument(
        'query',
        help='Specify the query for the posts you want to download and tag',
    )

    args = parser.parse_args()

    booru = args.booru
    logger.debug(f'booru = {booru}')

    query = args.query
    logger.debug(f'query = {query}')
    if '\'' in query:
        logger.warning(
            'Your query contains single quotes (\'). '
            'Consider using double quotes (") if the script doesn\'t behave as intended.',
        )

    return booru, query


def get_posts_from_booru(booru, query: str):
    """Placeholder"""

    exclude_tags = ' -pixel-perfect-duplicate -duplicate'

    if isinstance(booru, Gelbooru):
        results = sync(booru.client.search_posts(tags=query.split()))
    elif isinstance(booru, Danbooru):
        total = booru.count_posts(tags=query + exclude_tags)['counts']['posts']
        pages = ceil(int(total) / 100)  # Max posts per pages is 100
        results = []

        if pages > 1:
            for page in range(1, pages + 1):
                results.append(booru.post_list(limit=100, page=page, raw=True, tags=query + exclude_tags))

        results = [result for result in results for result in result]
    else:
        results = booru.post_list(limit=100, tags=query + exclude_tags)

    yield len(results)
    yield from results


def import_post(booru, post) -> None:
    """Placeholder"""

    try:
        file_url = post.file_url if booru == 'gelbooru' else post['file_url']
    except KeyError:
        logger.warning('Could not find file url for post. It got probably removed from the site.')
        return

    filename = file_url.split('/')[-1]
    file_path = Path(config.auto_tagger['tmp_path']) / filename  # Where the file gets temporarily saved to

    try:
        urllib.request.urlretrieve(file_url, file_path)
    except Exception as e:
        logger.warning(e)
        return

    if booru == 'gelbooru':
        tags = post.tags
        safety = convert_rating(post.rating)
        source = 'https://gelbooru.com/index.php?page=post&s=view&id=' + str(post.id)
    elif booru == 'danbooru':
        tags = post['tag_string'].split()
        source = 'https://danbooru.donmai.us/posts/' + str(post['id'])
    elif booru == 'yandere':
        tags = post['tags'].split()
        source = 'https://yande.re/post/show/' + str(post['id'])
    elif booru == 'konachan':
        tags = post['tags'].split()
        source = 'https://konachan.com/post/show/' + str(post['id'])

    if not booru == 'gelbooru':
        safety = convert_rating(post['rating'])

    metadata = {'tags': tags, 'safety': safety, 'source': source}

    upload_media.main(file_path, metadata)


@logger.catch
def main() -> None:
    """Call respective functions to retrieve and upload posts based on user input."""

    logger.info('Initializing script...')

    booru, query = parse_args()

    if config.import_from_booru['deepbooru_enabled']:
        config.upload_media['auto_tag'] = True
        config.auto_tagger['saucenao_enabled'] = False
        config.auto_tagger['deepbooru_enabled'] = True
    else:
        config.upload_media['auto_tag'] = False

    if booru == 'all':
        boorus = ['danbooru', 'gelbooru', 'yandere', 'konachan']
    else:
        boorus = [booru]

    for booru in boorus:
        logger.info(f'Retrieving posts from {booru} with query "{query}"...')

        if booru == 'danbooru':
            booru_client = Danbooru('danbooru', config.danbooru['user'], config.danbooru['api_key'])
        elif booru == 'gelbooru':
            booru_client = Gelbooru(config.gelbooru['user'], config.gelbooru['api_key'])
        elif booru == 'konachan':
            booru_client = Moebooru('konachan', config.konachan['user'], config.konachan['password'])
        elif booru == 'yandere':
            booru_client = Moebooru('yandere', config.yandere['user'], config.yandere['password'])

        posts = get_posts_from_booru(booru_client, query)

        total_posts = next(posts)
        logger.info(f'Found {total_posts} posts. Start importing...')

        for post in tqdm(
            posts,
            ncols=80,
            position=0,
            leave=False,
            total=int(total_posts),
            disable=config.auto_tagger['hide_progress'],
        ):
            import_post(booru, post)

    logger.success('Script finished importing!')


if __name__ == '__main__':
    main()
