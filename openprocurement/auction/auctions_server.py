from gevent import monkey

monkey.patch_all()

import time
import logging
from collections import deque
from couchdb import Server, Session
from datetime import datetime
from design import sync_design, endDate_view
from flask import (
    Flask, render_template,
    request, abort, url_for,
    redirect, Response, jsonify
)
from json import dumps, loads
from memoize import Memoizer
from pytz import timezone as tz
from restkit.conn import Connection
from socketpool import ConnectionPool
from sse import Sse as PySse
from urlparse import urlparse, urljoin

from .utils import get_mapping
from .proxy import StreamProxy
from systemd.journal import send


logger = logging.getLogger(__name__)

LIMIT_REPLICATIONS_LIMIT_FUNCTIONS = {
    'any': any,
    'all': all
}


auctions_server = Flask(__name__)


@auctions_server.before_request
def before_request():
    auctions_server.logger.debug('Start {0.method}: {0.url}'.format(request))


@auctions_server.after_request
def after_request(response):
    auctions_server.logger.debug(
        'End {1.status_code} : {0.method} : {0.url} '.format(request, response)
    )
    return response


@auctions_server.route('/tenders/<auction_doc_id>')
def auction_url(auction_doc_id):
    url_obj = urlparse(request.url)
    request_base = u'//' + url_obj.netloc + url_obj.path + u'/'
    return render_template(
        'tender.html',
        database=auctions_server.config.get('COUCH_DB'),
        doc_id=auction_doc_id,
        request_base=request_base
    )

@auctions_server.route('/')
def auction_list_index():
    return jsonify(reversed(
        [auction.doc
             for auction in endDate_view(auctions_server.db,
                                         startkey=time.time() * 1000,
                                         include_docs=True)
        ]))


@auctions_server.route('/log', methods=['POST'])
def log():

    try:
        data = loads(request.data)
        if "MESSAGE" in data:
            msg = data.get("MESSAGE")
            del data["MESSAGE"]
        else:
            msg = ""
        data['REMOTE_ADDR'] = ','.join(
            [ip
             for ip in request.environ.get('HTTP_X_FORWARDED_FOR', '').split(',')
             if not ip.startswith('172.')]
        )
        if request.environ.get('REMOTE_ADDR', '') and data['REMOTE_ADDR'] == "":
            data['REMOTE_ADDR'] += request.environ.get('REMOTE_ADDR', '')
        data["SYSLOG_IDENTIFIER"] = "AUCTION_CLIENT"
        send(msg, **data)
        return Response('ok')
    except:
        return Response('error')



@auctions_server.route('/health')
def health():
    data = auctions_server.couch_server.tasks()
    response = Response(dumps(data))
    progress = [
        task['progress'] > auctions_server.config.get('limit_replications_progress', 99)
        for task in data if 'type' in task and task['type'] == 'replication'
    ]
    limit_replications_func = LIMIT_REPLICATIONS_LIMIT_FUNCTIONS.get(auctions_server.config.get('limit_replications_func', 'any'))
    if not(progress and limit_replications_func(progress)):
        response.status_code = 503
    return response


#@auctions_server.route('/archive')
#def archive_auction_list_index():
#    offset = int(request.args.get('offset', default=time.time() * 1000))
#    startkey_docid = request.args.get('startid', default=None)
#    documents = [auction
#                 for auction in endDate_view(auctions_server.db, startkey=offset, startkey_docid=startkey_docid,
#                                             limit=101, descending=True, include_docs=True)]
#    if len(documents) > 100:
#        offset, startid = documents[100].key, documents[100].id
#    else:
#        offset, startid = False, False
#    return render_template('archive.html', documents=documents[:-1], offset=offset, startid=startid)


@auctions_server.route('/tenders/<auction_doc_id>/<path:path>',
                       methods=['GET', 'POST'])
def auctions_proxy(auction_doc_id, path):
    auctions_server.logger.debug('Auction_doc_id: {}'.format(auction_doc_id))
    proxy_path = auctions_server.proxy_mappings.get(
        str(auction_doc_id),
        get_mapping,
        (auctions_server.config['REDIS'], str(auction_doc_id), False), max_age=60
    )
    auctions_server.logger.debug('Proxy path: {}'.format(proxy_path))
    if proxy_path:
        request.environ['PATH_INFO'] = '/' + path
        auctions_server.logger.info("proxy path {}".format(proxy_path))
        auctions_server.logger.info("path {}".format(path))
        auctions_server.logger.debug('Start proxy to path: {}'.format(path))
        return StreamProxy(
            proxy_path,
            auction_doc_id=str(auction_doc_id),
            event_sources_pool=auctions_server.event_sources_pool,
            event_source_connection_limit=auctions_server.config['event_source_connection_limit'],
            pool=auctions_server.proxy_connection_pool,
            backend="gevent"
        )
    elif path == 'login' and auction_doc_id in auctions_server.db:
        return redirect(request.url.replace('/login', ''))
        #return redirect((
        #    url_for('auction_url', auction_doc_id=auction_doc_id,
        #            wait=1, **request.args)
        #))
    elif path == 'event_source':
        events_close = PySse()
        events_close.add_message("Close", "Disable")
        return Response(
            events_close,
            mimetype='text/event-stream',
            content_type='text/event-stream'
        )

    return abort(404)


@auctions_server.route('/get_current_server_time')
def auctions_server_current_server_time():
    response = Response(datetime.now(auctions_server.config['TIMEZONE']).isoformat())
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response


def couch_server_proxy(path):
    """USED FOR DEBUG ONLY"""
    return StreamProxy(
        auctions_server.config['PROXY_COUCH_URL'],
        auctions_server.event_sources_pool,
        pool=auctions_server.proxy_connection_pool,
        backend="gevent"
    )


def auth_couch_server_proxy(path):
    """USED FOR DEBUG ONLY"""
    return StreamProxy(
        auctions_server.config['PROXY_COUCH_URL'],
        auctions_server.event_sources_pool,
        rewrite_path=(auctions_server.config['COUCH_DB'] + "_secured", auctions_server.config['COUCH_DB']),
        pool=auctions_server.proxy_connection_pool,
        backend="gevent"
    )


def make_auctions_app(global_conf,
                      redis_url='redis://localhost:9002/1',
                      redis_password='',
                      redis_database='',
                      sentinel_cluster_name='',
                      sentinels='',
                      external_couch_url='http://localhost:5000/auction',
                      internal_couch_url='http://localhost:9000/',
                      proxy_internal_couch_url='http://localhost:9000/',
                      auctions_db='auctions',
                      hash_secret_key='',
                      timezone='Europe/Kiev',
                      preferred_url_scheme='http',
                      debug=False,
                      auto_build=False,
                      event_source_connection_limit=1000,
                      limit_replications_progress=99,
                      limit_replications_func='any'
                      ):
    """
    [app:main]
    use = egg:openprocurement.auction#auctions_server
    redis_url = redis://:passwod@localhost:1111/0
    external_couch_url = http://localhost:1111/auction
    internal_couch_url = http://localhost:9011/
    auctions_db = auction
    timezone = Europe/Kiev
    """

    auctions_server.proxy_connection_pool = ConnectionPool(
        factory=Connection, max_size=20, backend="gevent"
    )
    auctions_server.proxy_mappings = Memoizer({})
    auctions_server.event_sources_pool = deque([])
    auctions_server.config['PREFERRED_URL_SCHEME'] = preferred_url_scheme
    auctions_server.config['limit_replications_progress'] = float(limit_replications_progress)
    auctions_server.config['limit_replications_func'] = limit_replications_func

    auctions_server.config['REDIS'] = {
        'redis': redis_url,
        'redis_password': redis_password,
        'redis_database': redis_database,
        'sentinel_cluster_name': sentinel_cluster_name,
        'sentinel': loads(sentinels)
    }

    auctions_server.config['event_source_connection_limit'] = int(event_source_connection_limit)
    auctions_server.config['EXT_COUCH_DB'] = urljoin(
        external_couch_url,
        auctions_db
    )
    auctions_server.add_url_rule(
        '/' + auctions_db + '/<path:path>',
        'couch_server_proxy',
        couch_server_proxy,
        methods=['GET'])
    auctions_server.add_url_rule(
        '/' + auctions_db + '/',
        'couch_server_proxy',
        couch_server_proxy,
        methods=['GET'], defaults={'path': ''})

    auctions_server.add_url_rule(
        '/' + auctions_db + '_secured/<path:path>',
        'auth_couch_server_proxy',
        auth_couch_server_proxy,
        methods=['GET'])
    auctions_server.add_url_rule(
        '/' + auctions_db + '_secured/',
        'auth_couch_server_proxy',
        auth_couch_server_proxy,
        methods=['GET'], defaults={'path': ''})

    auctions_server.config['INT_COUCH_URL'] = internal_couch_url
    auctions_server.config['PROXY_COUCH_URL'] = proxy_internal_couch_url
    auctions_server.config['COUCH_DB'] = auctions_db
    auctions_server.config['TIMEZONE'] = tz(timezone)

    auctions_server.couch_server = Server(
        auctions_server.config.get('INT_COUCH_URL'),
        session=Session(retry_delays=range(10))
    )
    if auctions_server.config['COUCH_DB'] not in auctions_server.couch_server:
        auctions_server.couch_server.create(auctions_server.config['COUCH_DB'])

    auctions_server.db = auctions_server.couch_server[auctions_server.config['COUCH_DB']]
    auctions_server.config['HASH_SECRET_KEY'] = hash_secret_key
    sync_design(auctions_server.db)
    auctions_server.config['ASSETS_DEBUG'] = True if debug else False
    return auctions_server
