import logging
import urllib
import urllib2
from urlparse import urlparse

from django.http import HttpResponse
from django.views.generic import View

from httpproxy.decorators import rewrite_response
from httpproxy.recorder import ProxyRecorder
from httpproxy import settings

logger = logging.getLogger(__name__)

class HttpProxy(View):

    mode = None  # Available modes are play, record, playrecord
    base_url = None
    msg = 'Response body: \n%s'
    user_agent = ''
    view_name = 'http_proxy'

    def dispatch(self, request, url, *args, **kwargs):
        self.url = urllib.unquote(url).replace('\\', '/')
        request = self.normalize_request(request)
        if self.mode == 'play':
            return self.play(request)
        elif self.mode == 'playrecord':
            response = self.play(request, True)
            if response != None:
                return response

        dispatcher = super(HttpProxy, self).dispatch
        if settings.PROXY_REWRITE_RESPONSES:
            dispatcher = rewrite_response(dispatcher, self.url, self.view_name)
        response = dispatcher(request, *args, **kwargs)
        if self.mode == 'record' or self.mode == 'playrecord':
            self.record(response)
        return response

    def normalize_request(self, request):
        """
        Updates all path-related info in the original request object with the url
        given to the proxy

        This way, any further processing of the proxy'd request can just ignore
        the url given to the proxy and use request.path safely instead.
        """
        if not self.url.startswith('/') and self.base_url:
            self.url = '/' + self.url
        request.path = self.url
        request.path_info = self.url
        request.META['PATH_INFO'] = self.url
        return request

    def play(self, request, safe=False):
        """
        Plays back the response to a request, based on a previously recorded
        request/response
        """
        return self.get_recorder().playback(request) if not safe else \
            self.get_recorder().try_playback(request)

    def record(self, response):
        """
        Records the request being made and its response
        """
        self.get_recorder().record(self.request, response)

    def get_recorder(self):
        url = urlparse(self.get_full_url(self.url))
        return ProxyRecorder(domain=url.hostname, port=(url.port or 80))

    def get(self, request, *args, **kwargs):
        request_url = self.get_full_url(self.url)
        request = self.create_request(request_url,
            headers={'User-Agent': self.user_agent})
        response = urllib2.urlopen(request)
        try:
            response_body = response.read()
            status = response.getcode()
            logger.debug(self.msg % response_body)
        except urllib2.HTTPError, e:
            response_body = e.read()
            logger.error(self.msg % response_body)
            status = e.code
        return HttpResponse(response_body, status=status,
                content_type=response.headers['content-type'])

    def get_full_url(self, url):
        """
        Constructs the full URL to be requested
        """
        param_str = self.request.GET.urlencode()
        request_url = u'%s%s' % (self.base_url if self.base_url else '', url)
        request_url += '?%s' % param_str if param_str else ''
        return request_url

    def create_request(self, url, body=None, headers={}):
        request = urllib2.Request(url, body, headers)
        logger.info('%s %s' % (request.get_method(), request.get_full_url()))
        return request
